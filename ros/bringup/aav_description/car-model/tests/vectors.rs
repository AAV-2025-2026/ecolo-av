//! The shared vectors: this crate must give the states car_model.py gave
//! (vectors.json, written by gen_vectors.py).

use car_model::{ActuatorConfig, CarState, Command, Drive, SpeedLoop, SpeedLoopProfile};
use serde_json::Value;

const PEDALS_TOLERANCE: f64 = 1e-9;
// The Rust runs spine-core's speed loop in f32; the Python port runs it in f64.
const SPEED_TOLERANCE: f64 = 1e-3;

fn vectors() -> Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/vectors.json");
    let text = std::fs::read_to_string(path).expect("vectors.json: run gen_vectors.py");
    serde_json::from_str(&text).expect("vectors.json is JSON")
}

fn num(v: &Value) -> f64 {
    v.as_f64().expect("a number")
}

fn config(v: &Value) -> ActuatorConfig {
    serde_json::from_value(v.clone()).expect("an ActuatorConfig")
}

fn command(v: &Value) -> Command {
    let steer = num(&v["steer"]);
    let drive = match v.get("speed") {
        Some(speed) => Drive::Speed(num(speed)),
        None => Drive::Pedals {
            throttle: num(&v["throttle"]),
            brake: num(&v["brake"]),
            reverse: v["reverse"].as_bool().expect("a bool"),
        },
    };
    Command { drive, steer }
}

fn speed_loop(v: &Value) -> Option<SpeedLoop> {
    v.as_str().map(|name| {
        let profile: SpeedLoopProfile = name.parse().expect("a profile");
        SpeedLoop::new(profile.config())
    })
}

fn fields(s: &CarState) -> [f64; 7] {
    [
        s.x,
        s.y,
        s.yaw,
        s.v,
        s.steer,
        s.throttle_level,
        s.brake_level,
    ]
}

fn check(name: &str, step: usize, got: &CarState, want: &[Value], tolerance: f64) {
    for (i, (g, w)) in fields(got).iter().zip(want).enumerate() {
        let w = num(w);
        assert!(
            (g - w).abs() <= tolerance,
            "{name}, step {step}, field {i}: got {g}, want {w}"
        );
    }
}

#[test]
fn every_case_matches_the_python_model() {
    let doc = vectors();
    let cases = doc["cases"].as_array().expect("cases");
    assert!(cases.len() >= 11);
    for case in cases {
        let name = case["name"].as_str().expect("a name");
        let cfg = config(&case["config"]);
        let dt = num(&case["dt"]);
        let mut lp = speed_loop(&case["speed_loop"]);
        let tolerance = if lp.is_some() {
            SPEED_TOLERANCE
        } else {
            PEDALS_TOLERANCE
        };
        let every: Vec<Command> = case["commands"]
            .as_array()
            .expect("commands")
            .iter()
            .flat_map(|seg| {
                let steps = seg[0].as_u64().expect("steps") as usize;
                std::iter::repeat_n(command(&seg[1]), steps)
            })
            .collect();
        let mut wanted = case["states"].as_array().expect("states").iter().peekable();
        let mut state = CarState::default();
        for (i, c) in every.iter().enumerate() {
            state = cfg.step(&state, *c, dt, lp.as_mut()).expect("a step");
            let n = i + 1;
            if let Some(want) = wanted.next_if(|w| w[0].as_u64() == Some(n as u64)) {
                check(
                    name,
                    n,
                    &state,
                    &want.as_array().expect("a row")[1..],
                    tolerance,
                );
            }
        }
        assert!(wanted.next().is_none(), "{name}: states left unchecked");
    }
}

#[test]
fn predict_matches_the_python_trace() {
    let doc = vectors();
    let p = &doc["predict"];
    let cfg = config(&p["config"]);
    let s = &p["start"];
    let line = |key: &str| s[key].as_array().expect("a line").iter().map(num).collect();
    let start = CarState {
        x: num(&s["x"]),
        y: num(&s["y"]),
        yaw: num(&s["yaw"]),
        v: num(&s["v"]),
        steer: num(&s["steer"]),
        throttle_level: num(&s["throttle_level"]),
        brake_level: num(&s["brake_level"]),
        steer_motor: num(&s["steer_motor"]),
        steer_setpoint: num(&s["steer_setpoint"]),
        steer_linkage: num(&s["steer_linkage"]),
        throttle_delay: line("throttle_delay"),
        brake_delay: line("brake_delay"),
        steer_delay: line("steer_delay"),
    };
    let lp = speed_loop(&p["speed_loop"]);
    let trace = cfg
        .predict(
            &start,
            &[command(&p["command"])],
            num(&p["dt"]),
            num(&p["horizon"]),
            lp.as_ref(),
        )
        .expect("a trace");
    let want = p["states"].as_array().expect("states");
    assert_eq!(trace.len(), want.len());
    for (i, (got, w)) in trace.iter().zip(want).enumerate() {
        check(
            "predict",
            i + 1,
            got,
            w.as_array().expect("a row"),
            SPEED_TOLERANCE,
        );
    }
}
