//! The cases of aav_spine's test_spine_bridge.py: the DRIVE_CMD stream (the arming edge,
//! going quiet with ego, the e-stop) and the odometry from the wheel nodes.

use std::time::Duration;

use spine_bridge::{
    ArmError, Arming, Bridge, Command, Drive, Geometry, Motion, Reading, Settings, Update,
};
use spine_core::protocol::{
    VehicleFeedback, Wheel, WheelSpeed, VEHICLE_FEEDBACK_ID, VEHICLE_STATUS_ID,
};

const SETTINGS: Settings = Settings {
    geometry: Geometry {
        wheelbase: 1.57,
        track: 0.77,
    },
    cmd_timeout: Duration::from_millis(100),
    wheel_timeout: Duration::from_millis(100),
};

fn ms(t: u64) -> Duration {
    Duration::from_millis(t)
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-6
}

/// A bridge with a fresh command from ego at t = 0.
fn commanded(speed: f32) -> Bridge {
    let mut bridge = Bridge::new(SETTINGS);
    bridge.command(
        Command {
            speed,
            ..Command::default()
        },
        ms(0),
    );
    bridge
}

/// The armed flags of the next `frames` DRIVE_CMD ticks, at t = 0.
fn armed_flags(bridge: &mut Bridge, frames: usize) -> Vec<bool> {
    (0..frames)
        .filter_map(|_| match bridge.drive(ms(0)) {
            Drive::Send(cmd) => Some(cmd.armed),
            Drive::NoCommand | Drive::Stale => None,
        })
        .collect()
}

#[test]
fn arming_sends_the_edge() {
    let mut bridge = commanded(1.0);
    assert_eq!(armed_flags(&mut bridge, 2), [false, false]);
    assert_eq!(bridge.arm(true), Ok(Arming::Armed));
    assert_eq!(
        armed_flags(&mut bridge, 5),
        [false, false, false, true, true]
    );
}

#[test]
fn arming_again_sends_the_edge_again() {
    // The spine may have latched without the bridge knowing: a hardware e-stop, a
    // timeout, a driver fault or a reboot. Arming again has to clear that.
    let mut bridge = commanded(1.0);
    bridge.arm(true).ok();
    armed_flags(&mut bridge, 5);
    bridge.arm(true).ok();
    assert_eq!(
        armed_flags(&mut bridge, 5),
        [false, false, false, true, true]
    );
}

#[test]
fn estop_disarms_and_refuses_arming() {
    let mut bridge = commanded(1.0);
    bridge.arm(true).ok();
    let sent = bridge.set_estop(true);
    assert!(sent.is_some_and(|f| f.estop_request), "sent at once");
    assert_eq!(bridge.arm(true), Err(ArmError::EstopActive));
    assert_eq!(armed_flags(&mut bridge, 5), [false; 5]);
    // The same request again changes nothing: it waits for the heartbeat.
    assert_eq!(bridge.set_estop(true), None);
    assert!(bridge.estop_frame().estop_request);
}

#[test]
fn disarming_works_even_in_an_estop() {
    let mut bridge = commanded(1.0);
    bridge.set_estop(true);
    assert_eq!(bridge.arm(false), Ok(Arming::Disarmed));
}

#[test]
fn stale_command_stops_the_stream() {
    let mut bridge = commanded(1.0);
    bridge.arm(true).ok();
    assert_eq!(bridge.drive(ms(150)), Drive::Stale);
    assert_eq!(Bridge::new(SETTINGS).drive(ms(0)), Drive::NoCommand);
}

#[test]
fn drive_frames_carry_the_command_and_count() {
    let mut bridge = Bridge::new(SETTINGS);
    bridge.command(
        Command {
            speed: -0.5,
            steering_angle: 0.2,
            acceleration: -1.5,
            steering_angle_velocity: -0.4,
        },
        ms(0),
    );
    let counters: Vec<u8> = (0..17)
        .filter_map(|_| match bridge.drive(ms(50)) {
            Drive::Send(cmd) => {
                assert_eq!(cmd.target_speed, -0.5);
                assert_eq!(cmd.steering_angle, 0.2);
                assert_eq!(cmd.accel_limit, 1.5); // limits are magnitudes
                assert_eq!(cmd.steer_rate_limit, 0.4);
                Some(cmd.counter)
            }
            _ => None,
        })
        .collect();
    assert_eq!(counters[..2], [1, 2]);
    assert_eq!(counters[14..], [15, 0, 1]); // 4 bits, wrapping
    assert_eq!(bridge.estop_frame().counter, 1); // each ID counts on its own
}

fn feedback(speed: f32, steer: f32) -> [u8; 8] {
    VehicleFeedback {
        measured_speed: speed,
        measured_steering_angle: steer,
        wheel_ticks: 0,
        counter: 0,
    }
    .encode()
}

fn wheel(side: Wheel, speed: f32) -> (u16, [u8; 8]) {
    let frame = WheelSpeed {
        wheel: side,
        wheel_speed: speed,
        pulse_count: 3,
        direction_known: false,
        counter: 0,
    };
    (side.id(), frame.encode())
}

fn motion(bridge: &mut Bridge, data: &[u8], now: Duration) -> Motion {
    match bridge.receive(VEHICLE_FEEDBACK_ID, data, now) {
        Ok(Some(Update::Motion(m))) => m,
        other => panic!("expected motion, got {other:?}"),
    }
}

fn wheels(bridge: &mut Bridge, side: Wheel, speed: f32, now: Duration) -> Option<Reading> {
    let (id, data) = wheel(side, speed);
    match bridge.receive(id, &data, now) {
        Ok(Some(Update::Wheels(r))) => Some(r),
        Ok(None) => None,
        other => panic!("expected wheels, got {other:?}"),
    }
}

#[test]
fn odometry_uses_fresh_wheel_speeds() {
    let mut bridge = Bridge::new(SETTINGS);
    let fb = feedback(-0.5, 0.0);
    assert!(close(motion(&mut bridge, &fb, ms(0)).speed, -0.5)); // no wheel frames yet

    // The first left frame goes out alone; then they pair up.
    let mut last = None;
    for _ in 0..2 {
        for (side, v) in [(Wheel::Left, 1.0), (Wheel::Right, 1.2)] {
            last = wheels(&mut bridge, side, v, ms(0)).or(last);
        }
    }
    let r = last.expect("a wheel reading");
    assert!(close(r.left.speed, -1.0)); // signed by the spine's reverse
    assert!(close(r.right.speed, -1.2));
    assert!(r.left.fresh && r.right.fresh);
    assert!(!r.direction_measured);
    assert!(close(motion(&mut bridge, &fb, ms(0)).speed, -1.1));
}

#[test]
fn odometry_falls_back_when_the_wheels_go_quiet() {
    let mut bridge = Bridge::new(SETTINGS);
    wheels(&mut bridge, Wheel::Left, 2.0, ms(0));
    wheels(&mut bridge, Wheel::Right, 2.0, ms(0));
    assert!(close(
        motion(&mut bridge, &feedback(0.7, 0.0), ms(1000)).speed,
        0.7
    ));
}

#[test]
fn a_quiet_wheel_reads_stale() {
    let mut bridge = Bridge::new(SETTINGS);
    let r = wheels(&mut bridge, Wheel::Left, 1.0, ms(0)).expect("published alone");
    assert_eq!(r.left.fresh_speed(), Some(1.0));
    assert_eq!(r.right.fresh_speed(), None); // never heard from: NaN on the topic
}

#[test]
fn turning_odometry_and_wheel_angles() {
    let mut bridge = commanded(1.0);
    let m = motion(&mut bridge, &feedback(2.0, 0.3), ms(0));
    let steer = f64::from(0.3_f32);
    assert!(close(m.speed, 2.0));
    assert!(close(m.yaw_rate, 2.0 * steer.tan() / 1.57));
    // The inside (left) wheel turns more than the centre, the outside one less.
    let [left, right] = m.wheel_angles;
    assert!(left > steer && steer > right && right > 0.0);
    assert_eq!(m.steering_command, Some(0.0));
}

#[test]
fn status_in_ros_units_with_the_last_feedback() {
    let mut bridge = Bridge::new(SETTINGS);
    let status = spine_core::protocol::VehicleStatus {
        mode: spine_core::protocol::Mode::Computer,
        armed: true,
        estop_active: false,
        throttle: 25.0,
        brake: 50.0,
        faults: 0x0101,
        counter: 0,
    }
    .encode();
    let Ok(Some(Update::Status(s))) = bridge.receive(VEHICLE_STATUS_ID, &status, ms(0)) else {
        panic!("expected a status");
    };
    assert_eq!((s.throttle, s.brake, s.faults), (0.25, 0.5, 0x0101));
    assert_eq!(s.speed, None);
    motion(&mut bridge, &feedback(1.5, -0.1), ms(0));
    let Ok(Some(Update::Status(s))) = bridge.receive(VEHICLE_STATUS_ID, &status, ms(0)) else {
        panic!("expected a status");
    };
    assert_eq!(s.speed, Some(1.5));
}

#[test]
fn bad_frames_are_counted_and_others_ignored() {
    let mut bridge = Bridge::new(SETTINGS);
    let mut fb = feedback(1.0, 0.0);
    fb[0] ^= 1;
    let bad = bridge.receive(VEHICLE_FEEDBACK_ID, &fb, ms(0));
    assert!(bad.is_err_and(|e| e.so_far == 1));
    assert!(bridge
        .receive(VEHICLE_FEEDBACK_ID, &fb[..7], ms(0))
        .is_err());
    assert_eq!(bridge.bad_frames(), 2);
    // Someone else's frame on the bus is not an error.
    assert_eq!(bridge.receive(0x123, &[1, 2, 3], ms(0)), Ok(None));
    assert_eq!(bridge.bad_frames(), 2);
}
