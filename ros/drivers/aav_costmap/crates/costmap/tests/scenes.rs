//! Hand-made scenes: the local costmap (rolling, odom) and the global one (the map), with
//! nav2.yaml's settings, against what Nav2 would make of them.

use costmap::cost::{FREE, INSCRIBED, LETHAL, NO_INFORMATION};
use costmap::footprint;
use costmap::obstacle::scan_points;
use costmap::{Costmap, Observation, ObstacleLayer, Pose2, Settings, Source, StaticMap};

/// nav2.yaml's outline (the launch file writes the car's) and padding.
fn car() -> Vec<(f64, f64)> {
    let outline = footprint::parse("[[1.8, 0.5], [1.8, -0.5], [-0.2, -0.5], [-0.2, 0.5]]");
    footprint::padded(&outline.unwrap(), 0.05)
}

/// nav2.yaml's lidar_layer: the flat scan, marks to 12 m, clears to 15 m.
fn lidar_layer(like: &costmap::Grid) -> ObstacleLayer {
    let source = Source {
        clearing: true,
        min_obstacle_height: -0.5,
        max_obstacle_height: 0.5,
        obstacle_max_range: 12.0,
        raytrace_max_range: 15.0,
        inf_is_valid: true,
        ..Source::named("lidar")
    };
    let mut layer = ObstacleLayer::new("lidar_layer", vec![source], like, false);
    layer.min_obstacle_height = -0.5;
    layer.max_obstacle_height = 0.5;
    layer
}

fn local() -> Costmap {
    let settings = Settings {
        rolling: true,
        width: 20.0,
        height: 20.0,
        resolution: 0.1,
        track_unknown: false,
        footprint: car(),
        inflation: Some((2.0, 3.0)),
        static_layer: true,
    };
    let probe = Costmap::new(settings.clone(), Vec::new());
    let layer = lidar_layer(probe.grid());
    Costmap::new(settings, vec![layer])
}

/// A scan round the car (720 rays, 0.5 degrees) that sees a post `ahead` m in front, or
/// nothing (all inf) without one. In base_link.
fn scan(post: Option<(f64, f64, f64)>) -> Vec<[f64; 3]> {
    let n = 720;
    let step = std::f64::consts::TAU / n as f64;
    let ranges: Vec<f32> = (0..n)
        .map(|i| {
            let a = -std::f64::consts::PI + i as f64 * step;
            match post {
                // A round post of radius r at (x, y): the near side along each ray.
                Some((x, y, r)) => {
                    let (c, s) = (a.cos(), a.sin());
                    let along = x * c + y * s;
                    let off2 = (x * x + y * y) - along * along;
                    if along > 0.0 && off2 <= r * r {
                        (along - (r * r - off2).sqrt()) as f32
                    } else {
                        f32::INFINITY
                    }
                }
                None => f32::INFINITY,
            }
        })
        .collect();
    scan_points(-std::f64::consts::PI, step, 0.2, 30.0, &ranges, true)
}

/// The scan seen from `pose`, in odom.
fn seen_from(pose: &Pose2, points: Vec<[f64; 3]>) -> Observation {
    Observation {
        origin: [pose.x, pose.y, 0.0],
        points: points
            .into_iter()
            .map(|[x, y, z]| {
                let (ox, oy) = pose.apply((x, y));
                [ox, oy, z]
            })
            .collect(),
    }
}

#[test]
fn a_post_ahead_is_lethal_and_inflated() {
    let mut c = local();
    let car = Pose2::new(3.0, 1.0, 0.0);
    let obs = seen_from(&car, scan(Some((6.0, 0.0, 0.25))));
    c.update(&car, None, &[vec![vec![&obs]]]);
    let g = c.grid();
    // The post's near side, 5.75 m ahead.
    assert_eq!(g.cost_at(3.0 + 5.76, 1.0, 0), LETHAL);
    // Within the inscribed radius (0.25 m) of it: inscribed.
    assert!(g.cost_at(3.0 + 5.55, 1.0, 0) >= INSCRIBED);
    // 1 m short of it: Nav2's curve, 252 exp(-3 x 0.75) = 26.
    let one_m = g.cost_at(3.0 + 4.75, 1.0, 0);
    assert!((24..=28).contains(&one_m), "{one_m}");
    // The car's own cells and the open road: free.
    assert_eq!(g.cost_at(3.5, 1.0, 255), FREE);
    assert_eq!(g.cost_at(3.0, 6.0, 255), FREE);
    // The window is centred on the car, 200 x 200 cells of 0.1 m.
    assert_eq!((g.width, g.height), (200, 200));
    assert!((g.origin_x - (3.0 - 9.95)).abs() < 0.1 && (g.origin_y - (1.0 - 9.95)).abs() < 0.1);
}

#[test]
fn a_post_taken_away_is_cleared_by_the_next_scan() {
    let mut c = local();
    let car = Pose2::IDENTITY;
    let with = seen_from(&car, scan(Some((6.0, 0.0, 0.25))));
    c.update(&car, None, &[vec![vec![&with]]]);
    assert_eq!(c.grid().cost_at(5.8, 0.0, 0), LETHAL);
    let without = seen_from(&car, scan(None));
    c.update(&car, None, &[vec![vec![&without]]]);
    assert!(c.grid().data.iter().all(|&v| v == FREE));
}

#[test]
fn a_mark_stays_on_the_ground_as_the_window_rolls() {
    let mut c = local();
    let start = Pose2::IDENTITY;
    let obs = seen_from(&start, scan(Some((6.0, 2.0, 0.25))));
    c.update(&start, None, &[vec![vec![&obs]]]);
    // The car drives 3 m on, and its sensor is silent: the mark stays where it was.
    let on = Pose2::new(3.0, 0.0, 0.0);
    c.update(&on, None, &[vec![vec![]]]);
    let lethal: Vec<(f64, f64)> = (0..c.grid().data.len())
        .filter(|&i| c.grid().data[i] == LETHAL)
        .map(|i| c.grid().centre(i % c.grid().width, i / c.grid().width))
        .collect();
    assert!(!lethal.is_empty());
    assert!(
        lethal.iter().all(|&(x, y)| (x - 6.0).hypot(y - 2.0) < 0.4),
        "{lethal:?}"
    );
}

#[test]
fn the_map_is_written_into_the_window_through_map_to_odom() {
    let mut c = local();
    // A wall along y = 4 in the map, 40 m long.
    let (w, h) = (400usize, 200usize);
    let mut values = vec![0i8; w * h];
    let row = 140; // y = -10 + 14 = 4 m
    for x in 0..w {
        values[row * w + x] = 100;
    }
    c.set_map(StaticMap::from_occupancy((-20.0, -10.0), 0.1, w, h, &values, false).unwrap());
    // odom sits 1 m east and 1 m south of map's origin.
    let map_from_odom = Pose2::new(1.0, -1.0, 0.0);
    let car = Pose2::IDENTITY;
    c.update(&car, Some(&map_from_odom), &[vec![vec![]]]);
    // y = 4 in map is y = 5 in odom.
    assert_eq!(c.grid().cost_at(0.0, 5.05, 0), LETHAL);
    assert_eq!(c.grid().cost_at(0.0, 2.5, 0), FREE);
}

#[test]
fn the_global_costmap_takes_the_maps_cells_and_keeps_unknown() {
    let settings = Settings {
        rolling: false,
        width: 0.0,
        height: 0.0,
        resolution: 0.25,
        track_unknown: true,
        footprint: car(),
        inflation: Some((3.0, 1.0)),
        static_layer: true,
    };
    let mut c = Costmap::new(settings, Vec::new());
    assert!(!c.ready());
    let (w, h) = (80usize, 40usize);
    let mut values = vec![0i8; w * h];
    values[20 * w + 40] = 100;
    values[0] = -1;
    c.set_map(StaticMap::from_occupancy((-10.0, -5.0), 0.25, w, h, &values, true).unwrap());
    c.update(&Pose2::IDENTITY, None, &[]);
    let g = c.grid();
    assert_eq!((g.width, g.height, g.resolution), (80, 40, 0.25));
    assert_eq!(g.data[0], NO_INFORMATION);
    assert_eq!(g.get(40, 20), LETHAL);
    // 3 m (12 cells) round it, a gentle fall: 1 m out, 252 exp(-1 x 0.75) = 119.
    assert_eq!(g.get(44, 20), 119);
    assert_eq!(g.get(40 + 13, 20), FREE);
}
