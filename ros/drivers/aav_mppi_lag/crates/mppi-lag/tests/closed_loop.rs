//! Closed loop, no ROS: MPPI drives a pretend car around a circle and an S-curve.
//!
//! The pretend car is ego plus the lag model, stepped every 0.01 s (the truth). MPPI ticks
//! at 20 Hz, sees the car's pose, speed and measured actuators (as Gazebo gives them), and
//! plans with either the same lag model (lag-aware) or the lag-free one Nav2 assumes.
//! Each run prints its numbers: `cargo test -p mppi-lag --test closed_loop -- --nocapture`.

use mppi_lag::lag::Actuators;
use mppi_lag::{
    CarModel, Command, Critic, Driven, Ego, Follower, FollowerSettings, GlobalPath, IdealModel,
    LagModel, Observation, Pose, Settings, Tick,
};

const PERIOD: f64 = 0.05;
const PHYSICS: f64 = 0.01;

fn critics() -> Vec<Critic> {
    // nav2.yaml's list and its two changes from Nav2's defaults.
    mppi_lag::critics::NAMES
        .iter()
        .filter_map(|n| Critic::by_name(n))
        .map(|c| match c {
            Critic::GoalAngle(mut g) => {
                g.threshold = 2.5;
                Critic::GoalAngle(g)
            }
            Critic::PathAlign(mut p) => {
                p.use_path_orientations = true;
                Critic::PathAlign(p)
            }
            other => other,
        })
        .collect()
}

fn settings(speed: f64) -> Settings {
    Settings {
        batch_size: 1000,
        vx_max: speed,
        seed: 7,
        noise_correlation: std::env::var("CORR")
            .ok()
            .and_then(|c| c.parse().ok())
            .unwrap_or(Settings::default().noise_correlation),
        ..Settings::default()
    }
}

/// A path through `points` (x, y), headings along it, every ~0.05 m (as the planner's).
fn path_through(f: impl Fn(f64) -> (f64, f64), length: f64) -> Vec<Pose> {
    let n = (length / 0.05) as usize;
    let pts: Vec<(f64, f64)> = (0..=n).map(|i| f(i as f64 / n as f64)).collect();
    pts.iter()
        .enumerate()
        .map(|(i, &(x, y))| {
            let (a, b) = if i + 1 < pts.len() {
                (pts[i], pts[i + 1])
            } else {
                (pts[i - 1], pts[i])
            };
            Pose::new(x, y, (b.1 - a.1).atan2(b.0 - a.0))
        })
        .collect()
}

/// Three quarters of a circle of radius `r`, anticlockwise from (0, 0) facing east.
fn circle(r: f64) -> Vec<Pose> {
    let sweep = 1.5 * std::f64::consts::PI;
    path_through(
        |t| ((t * sweep).sin() * r, r - (t * sweep).cos() * r),
        sweep * r,
    )
}

/// An S: y = a sin(2 pi x / wavelength) for one and a half waves.
fn s_curve(a: f64, wavelength: f64) -> Vec<Pose> {
    let length = 1.5 * wavelength;
    path_through(
        |t| {
            let x = t * length;
            (x, a * (std::f64::consts::TAU * x / wavelength).sin())
        },
        length * 1.1,
    )
}

/// 10 m east, a quarter turn left of radius `r`, 10 m north.
fn corner(r: f64) -> Vec<Pose> {
    let arc = std::f64::consts::FRAC_PI_2 * r;
    let total = 20.0 + arc;
    path_through(
        |t| {
            let d = t * total;
            if d < 10.0 {
                (d, 0.0)
            } else if d < 10.0 + arc {
                let a = (d - 10.0) / r;
                (10.0 + r * a.sin(), r - r * a.cos())
            } else {
                (10.0 + r, r + d - 10.0 - arc)
            }
        },
        total,
    )
}

#[derive(Debug)]
struct Run {
    reached: bool,
    time: f64,
    mean_cross: f64,
    max_cross: f64,
}

fn drive<M: CarModel + Clone>(controller: M, truth: LagModel, poses: &[Pose], speed: f64) -> Run {
    let ego = Ego::default();
    let plant = Driven { ego, car: truth };
    let mut follower = Follower::new(
        controller,
        ego,
        settings(speed),
        critics(),
        FollowerSettings::default(),
        Vec::new(),
    );
    let start = poses[0];
    let mut car = plant.at_rest(start, 0.0);
    let path = GlobalPath::new(poses.to_vec()).expect("a path");
    let judge = path.clone();
    let mut command = Command::default();
    let mut crosses = Vec::new();
    let mut t = 0.0;
    let mut first = true;
    while t < 120.0 {
        follower.observe(&Observation {
            pose: plant.pose(&car),
            speed: plant.speed(&car),
            steering: Some(plant.steering(&car)),
            throttle: Some(car.car.throttle),
            brake: Some(car.car.brake),
        });
        if first {
            follower.follow(path.clone(), false);
            first = false;
        }
        match follower.tick(t, None) {
            Some(Tick::Drive(report)) => command = report.command,
            Some(Tick::Done(outcome)) => {
                return finish(outcome == mppi_lag::Outcome::Succeeded, t, &crosses);
            }
            None => {}
        }
        for _ in 0..(PERIOD / PHYSICS).round() as usize {
            plant.step(&mut car, command, PHYSICS);
        }
        t += PERIOD;
        if t > 2.0 {
            crosses.push(judge.foot(&plant.pose(&car)).cross_track.abs());
        }
    }
    finish(false, t, &crosses)
}

fn finish(reached: bool, time: f64, crosses: &[f64]) -> Run {
    let n = crosses.len().max(1) as f64;
    Run {
        reached,
        time,
        mean_cross: crosses.iter().sum::<f64>() / n,
        max_cross: crosses.iter().copied().fold(0.0, f64::max),
    }
}

fn ideal_of(truth: &LagModel) -> IdealModel {
    IdealModel {
        wheelbase: truth.wheelbase,
        max_steering_angle: truth.max_steering_angle,
        // Ego's ramps are already in front of it (Driven); the car itself is instant.
        accel: 100.0,
        decel: 100.0,
    }
}

/// The car with slow actuators: a sluggish linkage and dead times (a stand-in for a car
/// whose real numbers come in worse than vehicle.yaml's guesses).
fn slow_car() -> LagModel {
    LagModel {
        actuators: Actuators {
            steer_rate: 0.5,
            steer_lag: 0.3,
            steer_dead_time: 0.2,
            throttle_dead_time: 0.1,
            brake_dead_time: 0.1,
            ..Actuators::default()
        },
        ..LagModel::default()
    }
}

fn compare(name: &str, truth: LagModel, poses: &[Pose], speed: f64) -> (Run, Run) {
    let aware = drive(truth, truth, poses, speed);
    let free = drive(ideal_of(&truth), truth, poses, speed);
    println!(
        "{name} at {speed} m/s: lag-aware {:.3} m mean, {:.3} m worst, {:.1} s, reached {} | \
         lag-free {:.3} m mean, {:.3} m worst, {:.1} s, reached {}",
        aware.mean_cross,
        aware.max_cross,
        aware.time,
        aware.reached,
        free.mean_cross,
        free.max_cross,
        free.time,
        free.reached
    );
    (aware, free)
}

/// Much slower than vehicle.yaml's guesses: where the lag decides who stays on the path.
fn very_slow_car() -> LagModel {
    LagModel {
        actuators: Actuators {
            steer_rate: 0.3,
            steer_lag: 0.5,
            steer_dead_time: 0.3,
            throttle_dead_time: 0.2,
            brake_dead_time: 0.2,
            ..Actuators::default()
        },
        ..LagModel::default()
    }
}

/// Open loop: from the same state, predict 2.8 s of a weaving command with each model.
/// Returns the worst miss (m) of the lag model and of the lag-free one.
fn prediction_miss(truth: LagModel) -> (f64, f64) {
    let ego = Ego::default();
    let plant = Driven { ego, car: truth };
    let cmd = |t: f64| Command::new(1.5, 0.4 * (t * 1.5).sin());
    let mut car = plant.at_rest(Pose::default(), 0.0);
    let mut t = 0.0;
    for _ in 0..100 {
        for _ in 0..5 {
            plant.step(&mut car, cmd(t), PHYSICS);
        }
        t += PERIOD;
    }
    let mut lagged = car;
    let free_model = Driven {
        ego,
        car: ideal_of(&truth),
    };
    let mut free = free_model.at_rest(plant.pose(&car), plant.speed(&car));
    free.ego = car.ego;
    let mut worst = (0.0f64, 0.0f64);
    for _ in 0..56 {
        let c = cmd(t);
        for _ in 0..5 {
            plant.step(&mut car, c, PHYSICS);
        }
        plant.step(&mut lagged, c, PERIOD);
        free_model.step(&mut free, c, PERIOD);
        t += PERIOD;
        let p = plant.pose(&car);
        worst.0 = worst.0.max(p.distance(&plant.pose(&lagged)));
        worst.1 = worst.1.max(p.distance(&free_model.pose(&free)));
    }
    worst
}

/// Every case, printed: `cargo test --release -p mppi-lag --test closed_loop explore --
/// --ignored --nocapture` (CORR=0.0 for Nav2's white noise).
#[test]
#[ignore]
fn explore() {
    for (name, truth) in [
        ("vehicle.yaml", LagModel::default()),
        ("slow", slow_car()),
        ("very slow", very_slow_car()),
    ] {
        let (lag, free) = prediction_miss(truth);
        println!(
            "{name}: 2.8 s prediction misses by {lag:.3} m (lag model), {free:.3} m (lag-free)"
        );
        for speed in [1.0, 2.0, 3.0] {
            compare(&format!("{name}, circle r 5"), truth, &circle(5.0), speed);
            compare(
                &format!("{name}, S 2 x 16"),
                truth,
                &s_curve(2.0, 16.0),
                speed,
            );
            compare(&format!("{name}, corner r 4"), truth, &corner(4.0), speed);
        }
    }
}

#[test]
fn the_lag_model_predicts_the_car() {
    let (lag, free) = prediction_miss(slow_car());
    assert!(lag < 0.03, "{lag}");
    assert!(free > 0.3, "{free}");
}

#[test]
fn circle_at_vehicle_yaml_lags() {
    let (aware, free) = compare("circle r 5", LagModel::default(), &circle(5.0), 1.0);
    assert!(aware.reached && free.reached);
    assert!(aware.mean_cross < 0.05, "{aware:?}");
    assert!(aware.max_cross < 0.15, "{aware:?}");
}

#[test]
fn s_curve_at_vehicle_yaml_lags() {
    let (aware, free) = compare("S 2 x 16", LagModel::default(), &s_curve(2.0, 16.0), 2.0);
    assert!(aware.reached && free.reached);
    assert!(aware.mean_cross < 0.08, "{aware:?}");
    assert!(aware.max_cross < 0.2, "{aware:?}");
}

#[test]
fn very_slow_actuators_corner_only_lag_aware_holds_the_path() {
    let (aware, free) = compare("corner r 4, very slow", very_slow_car(), &corner(4.0), 2.0);
    assert!(aware.reached, "{aware:?}");
    assert!(aware.max_cross < 0.2, "{aware:?}");
    assert!(
        aware.mean_cross < 0.2 * free.mean_cross,
        "{aware:?} vs {free:?}"
    );
}

#[test]
fn very_slow_actuators_s_curve_only_lag_aware_holds_the_path() {
    let (aware, free) = compare(
        "S 2 x 16, very slow",
        very_slow_car(),
        &s_curve(2.0, 16.0),
        2.0,
    );
    assert!(aware.reached, "{aware:?}");
    assert!(aware.max_cross < 0.2, "{aware:?}");
    assert!(
        aware.mean_cross < 0.2 * free.mean_cross,
        "{aware:?} vs {free:?}"
    );
}
