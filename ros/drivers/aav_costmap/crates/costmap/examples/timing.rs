//! How long an update takes: `cargo run --release -p costmap --example timing`.
//!
//! The local costmap (20 m x 20 m at 0.1 m, the lidar layer, a 720-ray scan with a wall
//! and posts in it), and a global one on a 500 m x 500 m map at 0.25 m (the campus's size).

use std::time::Instant;

use costmap::obstacle::scan_points;
use costmap::{footprint, Costmap, Observation, ObstacleLayer, Pose2, Settings, Source, StaticMap};

fn main() {
    let car = footprint::padded(
        &footprint::parse("[[1.8, 0.5], [1.8, -0.5], [-0.2, -0.5], [-0.2, 0.5]]").unwrap(),
        0.05,
    );
    let settings = Settings {
        rolling: true,
        width: 20.0,
        height: 20.0,
        resolution: 0.1,
        track_unknown: false,
        footprint: car.clone(),
        inflation: Some((2.0, 3.0)),
        static_layer: true,
    };
    let probe = Costmap::new(settings.clone(), Vec::new());
    let source = Source {
        clearing: true,
        min_obstacle_height: -0.5,
        max_obstacle_height: 0.5,
        obstacle_max_range: 12.0,
        raytrace_max_range: 15.0,
        inf_is_valid: true,
        ..Source::named("lidar")
    };
    let layer = ObstacleLayer::new("lidar_layer", vec![source], probe.grid(), false);
    let mut local = Costmap::new(settings, vec![layer]);
    // A wall 4 m to the left, posts every 30 degrees ahead at 6 m, inf elsewhere.
    let n = 720;
    let step = std::f64::consts::TAU / n as f64;
    let ranges: Vec<f32> = (0..n)
        .map(|i| {
            let a = -std::f64::consts::PI + i as f64 * step;
            if a.sin() > 0.3 {
                (4.0 / a.sin()) as f32
            } else if a.cos() > 0.5 && (i % 60) < 4 {
                6.0
            } else {
                f32::INFINITY
            }
        })
        .collect();
    let points = scan_points(-std::f64::consts::PI, step, 0.2, 30.0, &ranges, true);
    let runs = 200;
    let t = Instant::now();
    for k in 0..runs {
        let pose = Pose2::new(k as f64 * 0.02, 0.0, 0.0);
        let obs = Observation {
            origin: [pose.x, pose.y, 0.0],
            points: points.iter().map(|&[x, y, z]| [x + pose.x, y, z]).collect(),
        };
        local.update(&pose, None, &[vec![vec![&obs]]]);
    }
    let local_ms = t.elapsed().as_secs_f64() * 1e3 / runs as f64;
    println!("local, 200 x 200 cells, a 720-ray scan: {local_ms:.2} ms an update");

    let (w, h) = (2000usize, 2000usize);
    let values: Vec<i8> = (0..w * h)
        .map(|i| {
            if (i / w) % 200 == 0 || (i % w) % 300 == 0 {
                100
            } else {
                0
            }
        })
        .collect();
    let mut global = Costmap::new(
        Settings {
            rolling: false,
            width: 0.0,
            height: 0.0,
            resolution: 0.25,
            track_unknown: true,
            footprint: car,
            inflation: Some((3.0, 1.0)),
            static_layer: true,
        },
        Vec::new(),
    );
    global.set_map(StaticMap::from_occupancy((-250.0, -250.0), 0.25, w, h, &values, true).unwrap());
    let runs = 5;
    let t = Instant::now();
    for _ in 0..runs {
        global.update(&Pose2::IDENTITY, None, &[]);
    }
    let global_ms = t.elapsed().as_secs_f64() * 1e3 / runs as f64;
    println!("global, 2000 x 2000 cells (500 m square), walls: {global_ms:.1} ms an update");
}
