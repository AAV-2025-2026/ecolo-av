//! The shared CAN test vectors (firmware/can/test_vectors.json, from the Python codec),
//! through the whole bridge: the frames it sends must be those bytes, and the frames it
//! receives must come out as the decoded values, in ROS's units.

use std::{fs, path::PathBuf, time::Duration};

use serde_json::Value;
use spine_bridge::{Bridge, Command, Drive, Geometry, Role, Settings, Update};
use spine_core::protocol::{
    DRIVE_CMD_ID, ESTOP_CMD_ID, VEHICLE_FEEDBACK_ID, VEHICLE_STATUS_ID, WHEEL_SPEED_L_ID,
    WHEEL_SPEED_R_ID,
};

const SETTINGS: Settings = Settings {
    role: Role::Spine,
    geometry: Geometry {
        wheelbase: 1.57,
        track: 0.77,
    },
    cmd_timeout: Duration::from_millis(100),
    wheel_timeout: Duration::from_millis(100),
};
const NOW: Duration = Duration::ZERO;

struct Vector {
    name: String,
    id: u16,
    values: Value,
    decoded: Value,
    data: Vec<u8>,
}

fn vectors() -> Vec<Vector> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../../../../firmware/can/test_vectors.json");
    let text = fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let json: Value = serde_json::from_str(&text).expect("test_vectors.json is JSON");
    json["vectors"]
        .as_array()
        .expect("a list of vectors")
        .iter()
        .map(|v| Vector {
            name: v["name"].as_str().unwrap_or_default().to_owned(),
            id: v["id"]
                .as_u64()
                .and_then(|id| u16::try_from(id).ok())
                .expect("an id"),
            values: v["values"].clone(),
            decoded: v["decoded"].clone(),
            data: hex(v["data_hex"].as_str().expect("data_hex")),
        })
        .collect()
}

fn hex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).expect("hex"))
        .collect()
}

fn num(v: &Value, name: &str) -> f64 {
    v[name].as_f64().unwrap_or(0.0)
}

fn flag(v: &Value, name: &str) -> bool {
    num(v, name) != 0.0
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-4
}

/// Ticks DRIVE_CMD until the frame has the vector's counter and armed flag.
fn drive_bytes(v: &Vector) -> Vec<u8> {
    let mut bridge = Bridge::new(SETTINGS);
    bridge.command(
        Command {
            speed: num(&v.values, "target_speed") as f32,
            steering_angle: num(&v.values, "steering_angle") as f32,
            acceleration: num(&v.values, "accel_limit") as f32,
            steering_angle_velocity: num(&v.values, "steer_rate_limit") as f32,
        },
        NOW,
    );
    let armed = flag(&v.values, "armed");
    if armed {
        bridge.arm(true).ok();
    }
    let counter = num(&v.values, "counter") as u8;
    (0..40)
        .find_map(|_| match bridge.drive(NOW) {
            Drive::Send(cmd) if cmd.counter == counter && cmd.armed == armed => {
                Some(cmd.encode().to_vec())
            }
            _ => None,
        })
        .unwrap_or_else(|| panic!("{}: no such frame", v.name))
}

fn estop_bytes(v: &Vector) -> Vec<u8> {
    let mut bridge = Bridge::new(SETTINGS);
    bridge.set_estop(flag(&v.values, "estop_request"));
    let counter = num(&v.values, "counter") as u8;
    (0..20)
        .map(|_| bridge.estop_frame())
        .find(|f| f.counter == counter)
        .map(|f| f.encode().to_vec())
        .unwrap_or_else(|| panic!("{}: no such frame", v.name))
}

#[test]
fn sent_frames_match_the_vectors() {
    let sent: Vec<Vector> = vectors()
        .into_iter()
        .filter(|v| [DRIVE_CMD_ID, ESTOP_CMD_ID].contains(&v.id))
        .collect();
    assert!(sent.len() >= 4);
    for v in sent {
        let bytes = if v.id == DRIVE_CMD_ID {
            drive_bytes(&v)
        } else {
            estop_bytes(&v)
        };
        assert_eq!(bytes, v.data, "{}", v.name);
    }
}

#[test]
fn received_frames_decode_as_the_vectors() {
    let mut checked = 0;
    for v in vectors() {
        let mut bridge = Bridge::new(SETTINGS);
        let d = &v.decoded;
        match bridge.receive(v.id, &v.data, NOW) {
            Ok(Some(Update::Motion(m))) => {
                assert_eq!(v.id, VEHICLE_FEEDBACK_ID, "{}", v.name);
                assert!(close(m.speed, num(d, "measured_speed")), "{}", v.name);
                let steer = num(d, "measured_steering_angle");
                assert!(close(m.steering_angle, steer), "{}", v.name);
            }
            Ok(Some(Update::Status(s))) => {
                assert_eq!(v.id, VEHICLE_STATUS_ID, "{}", v.name);
                assert_eq!(f64::from(s.mode as u8), num(d, "mode"), "{}", v.name);
                assert_eq!(s.armed, flag(d, "armed"), "{}", v.name);
                assert_eq!(s.estop_active, flag(d, "estop_active"), "{}", v.name);
                assert!(close(s.throttle.into(), num(d, "throttle") / 100.0));
                assert!(close(s.brake.into(), num(d, "brake") / 100.0));
                assert_eq!(f64::from(s.faults), num(d, "faults"), "{}", v.name);
            }
            Ok(Some(Update::Wheels(r))) => {
                let side = match v.id {
                    WHEEL_SPEED_L_ID => r.left,
                    WHEEL_SPEED_R_ID => r.right,
                    other => panic!("{}: wheels from 0x{other:03X}", v.name),
                };
                // Nothing says which way the car goes yet: a magnitude counts as forward.
                let speed = num(d, "wheel_speed");
                let expected = if flag(d, "direction_known") {
                    speed
                } else {
                    speed.abs()
                };
                assert!(side.fresh && close(side.speed, expected), "{}", v.name);
                assert_eq!(f64::from(side.pulses), num(d, "pulse_count"), "{}", v.name);
                assert_eq!(r.direction_measured, flag(d, "direction_known"));
            }
            Ok(None) => {
                assert!([DRIVE_CMD_ID, ESTOP_CMD_ID].contains(&v.id), "{}", v.name);
                continue;
            }
            Err(e) => panic!("{}: {e}", v.name),
        }
        checked += 1;
    }
    assert!(checked >= 7, "only {checked} received vectors");
}
