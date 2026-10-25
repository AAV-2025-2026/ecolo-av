//! The speed loop against the examples Gazebo's Python port checks too
//! (`firmware/spine/speed_loop_vectors.txt`, from `gen_speed_loop_vectors.py`). The two
//! copies must give the same throttle, brake and gear, profile by profile (TODO 27).

use spine_core::speed_loop::{SpeedLoop, SpeedLoopProfile};

const VECTORS: &str = include_str!("../../../speed_loop_vectors.txt");

/// f32 here, f64 in Python: the integral drifts apart by about 1e-7 a tick at most.
const TOLERANCE: f32 = 1e-4;

struct Tick {
    target: f32,
    measured: f32,
    dt: f32,
    throttle: f32,
    brake: f32,
    reverse: bool,
}

struct Case {
    name: String,
    profile: SpeedLoopProfile,
    ticks: Vec<Tick>,
}

fn number(field: Option<&str>, line: &str) -> f32 {
    field
        .and_then(|f| f.parse().ok())
        .unwrap_or_else(|| panic!("a number in {line:?}"))
}

fn cases() -> Vec<Case> {
    let mut cases: Vec<Case> = Vec::new();
    for line in VECTORS
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
    {
        let mut fields = line.split_whitespace();
        if let Some(rest) = line.strip_prefix("case ") {
            let (name, profile) = rest.split_once(' ').expect("case <name> <profile>");
            cases.push(Case {
                name: name.to_owned(),
                profile: profile.parse().expect("a known profile"),
                ticks: Vec::new(),
            });
            continue;
        }
        let tick = Tick {
            target: number(fields.next(), line),
            measured: number(fields.next(), line),
            dt: number(fields.next(), line),
            throttle: number(fields.next(), line),
            brake: number(fields.next(), line),
            reverse: fields.next() == Some("1"),
        };
        cases
            .last_mut()
            .expect("a case line first")
            .ticks
            .push(tick);
    }
    cases
}

#[test]
fn the_speed_loop_matches_the_shared_examples() {
    let cases = cases();
    for profile in SpeedLoopProfile::ALL {
        assert!(
            cases.iter().filter(|c| c.profile == profile).count() >= 4,
            "too few cases for {}",
            profile.name()
        );
    }
    for case in &cases {
        let mut speed_loop = SpeedLoop::new(case.profile.config());
        for (k, t) in case.ticks.iter().enumerate() {
            let d = speed_loop.update(t.target, t.measured, t.dt);
            let at = format!("{} {} tick {k}", case.name, case.profile.name());
            assert!(
                (d.throttle - t.throttle).abs() < TOLERANCE,
                "{at}: throttle {d:?}"
            );
            assert!((d.brake - t.brake).abs() < TOLERANCE, "{at}: brake {d:?}");
            assert_eq!(d.reverse, t.reverse, "{at}: gear");
        }
    }
}
