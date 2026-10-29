//! Pretend data for `--demo`: a walled lot with boxes, a car driving a loop, a 16-beam
//! lidar ray-cast against it, and the localizers a little apart. No ROS.
//!
//! `--bench-cubes N` swaps the lidar for N cubes spread round the car: the drawing test.

use std::{
    f64::consts::{PI, TAU},
    time::{Duration, Instant},
};

use debug_core::{
    cubes::{self, Cube, CubeScan, CubeSettings},
    frames::{Stamp, Transform3},
    state::{Localizer, Source, Update},
    track::TrackStatus,
};
use hud_core::{
    units::{Fraction, MetresPerSecond, Radians},
    vehicle::{Faults, Mode, VehicleStatus},
};
use map_core::geom::{Point, Pose};

use crate::source::DataSource;

/// The loop the car drives: a circle, metres and m/s.
const CENTRE: Point = Point::new(12.0, 0.0);
const RADIUS: f64 = 9.0;
const SPEED: f64 = 2.5;
/// The lidar on the roof, in base_link.
const LIDAR: [f64; 3] = [0.6, 0.0, 1.8];
/// Where odom sits on the map (map -> odom).
const ODOM_IN_MAP: Pose = Pose::new(3.0, -2.0, 0.08);

/// An axis-aligned box: min and max corners, odom.
#[derive(Clone, Copy)]
struct Aabb {
    min: [f64; 3],
    max: [f64; 3],
}

impl Aabb {
    const fn new(min: [f64; 3], max: [f64; 3]) -> Self {
        Self { min, max }
    }

    /// The distance along the ray to the box, if it hits (slab method).
    fn hit(&self, o: [f64; 3], d: [f64; 3]) -> Option<f64> {
        let (mut near, mut far) = (0.0_f64, f64::INFINITY);
        for i in 0..3 {
            if d[i].abs() < 1e-12 {
                if o[i] < self.min[i] || o[i] > self.max[i] {
                    return None;
                }
                continue;
            }
            let (a, b) = ((self.min[i] - o[i]) / d[i], (self.max[i] - o[i]) / d[i]);
            near = near.max(a.min(b));
            far = far.min(a.max(b));
            if near > far {
                return None;
            }
        }
        Some(near)
    }
}

/// The lot: four walls, boxes, a post, a parked van.
const WORLD: [Aabb; 10] = [
    Aabb::new([-10.0, -16.0, 0.0], [34.0, -15.6, 2.4]),
    Aabb::new([-10.0, 15.6, 0.0], [34.0, 16.0, 2.4]),
    Aabb::new([-10.4, -16.0, 0.0], [-10.0, 16.0, 2.4]),
    Aabb::new([34.0, -16.0, 0.0], [34.4, 16.0, 2.4]),
    Aabb::new([11.0, -1.0, 0.0], [13.0, 1.0, 1.0]),
    Aabb::new([24.0, 6.0, 0.0], [25.0, 7.0, 0.6]),
    Aabb::new([0.0, 8.0, 0.0], [5.0, 10.0, 2.1]),
    Aabb::new([20.0, -12.0, 0.0], [20.3, -11.7, 3.5]),
    Aabb::new([-4.0, -6.0, 0.0], [-3.0, -5.0, 1.6]),
    Aabb::new([26.0, -4.0, 0.0], [27.0, -3.0, 1.2]),
];

/// The lidar's beams: 16, from -15 to +15 degrees, as a VLP-16.
const BEAMS: usize = 16;
const AZIMUTHS: usize = 900;
const RANGE: f64 = 60.0;

/// One sweep from base_link's pose `car`: the points in the lidar's own frame.
fn sweep(car: Pose) -> Vec<[f32; 3]> {
    let lidar = Transform3::from_planar(car).apply(LIDAR);
    let mut points = Vec::with_capacity(BEAMS * AZIMUTHS);
    for b in 0..BEAMS {
        let elevation = (-15.0 + 2.0 * b as f64).to_radians();
        for a in 0..AZIMUTHS {
            let azimuth = TAU * a as f64 / AZIMUTHS as f64;
            // In the lidar's frame, then turned onto the ground with the car.
            let local = [
                elevation.cos() * azimuth.cos(),
                elevation.cos() * azimuth.sin(),
                elevation.sin(),
            ];
            let (s, c) = car.yaw.sin_cos();
            let d = [
                c * local[0] - s * local[1],
                s * local[0] + c * local[1],
                local[2],
            ];
            let ground = (d[2] < 0.0).then(|| -lidar[2] / d[2]);
            let t = WORLD
                .iter()
                .filter_map(|w| w.hit(lidar, d))
                .chain(ground)
                .filter(|&t| t > 0.3)
                .fold(f64::INFINITY, f64::min);
            if t <= RANGE {
                points.push(local.map(|v| (v * t) as f32));
            } else {
                // As Gazebo's: inf where a ray hit nothing.
                points.push([f32::INFINITY; 3]);
            }
        }
    }
    points
}

/// The car on its loop at `t` seconds: base_link in odom.
fn car_at(t: f64) -> Pose {
    let angle = SPEED * t / RADIUS;
    let p = CENTRE + Point::new(angle.cos(), angle.sin()) * RADIUS;
    Pose::new(p.x, p.y, angle + PI / 2.0)
}

/// odom to map.
fn in_map(p: Pose) -> Pose {
    Pose {
        position: ODOM_IN_MAP.transform(p.position),
        yaw: p.yaw + ODOM_IN_MAP.yaw,
    }
}

/// `--bench-cubes`: `n` cubes over a 100 m square round the origin, five layers high.
pub fn bench_scan(n: usize, size: f32) -> CubeScan {
    let side = ((n / 5) as f64).sqrt().ceil().max(1.0) as usize;
    let cubes = (0..n)
        .map(|i| {
            let (layer, cell) = (i % 5, i / 5);
            let (gx, gy) = (cell % side, cell / side);
            let step = 100.0 / side as f32;
            Cube {
                centre: [
                    gx as f32 * step - 50.0,
                    gy as f32 * step - 50.0,
                    0.1 + layer as f32 * 0.6,
                ],
                band: cubes::Band::ALL[layer % cubes::Band::ALL.len()],
            }
        })
        .collect();
    CubeScan {
        cubes,
        size,
        points: n,
        ..CubeScan::default()
    }
}

/// The demo's clock and its news.
pub struct Demo {
    start: Instant,
    last_scan: Option<Instant>,
    last_news: Option<Instant>,
    settings: CubeSettings,
    bench: Option<CubeScan>,
}

impl Demo {
    pub fn new(start: Instant, settings: CubeSettings, bench_cubes: Option<usize>) -> Self {
        let size = settings.size.0 as f32;
        Self {
            start,
            last_scan: None,
            last_news: None,
            settings,
            bench: bench_cubes.map(|n| bench_scan(n, size)),
        }
    }

    fn t(&self, now: Instant) -> f64 {
        now.duration_since(self.start).as_secs_f64()
    }
}

/// True every `period` since `last`, which it moves on.
fn due(last: &mut Option<Instant>, now: Instant, period: Duration) -> bool {
    if last.is_some_and(|l| now.duration_since(l) < period) {
        return false;
    }
    *last = Some(now);
    true
}

impl DataSource for Demo {
    fn label(&self) -> &'static str {
        "DEMO"
    }

    fn drain(&mut self, now: Instant) -> Vec<Update> {
        if !due(&mut self.last_news, now, Duration::from_millis(50)) {
            return Vec::new();
        }
        let t = self.t(now);
        let car = car_at(t);
        let truth = in_map(car);
        // The global EKF wanders round the truth; AMCL jitters.
        let global = Pose::new(
            truth.position.x + 0.35 * (t * 0.3).sin(),
            truth.position.y + 0.25 * (t * 0.23).cos(),
            truth.yaw + 0.02,
        );
        let amcl = Pose::new(
            truth.position.x - 0.15 + 0.1 * (t * 3.1).sin(),
            truth.position.y + 0.1 * (t * 2.3).cos(),
            truth.yaw - 0.01,
        );
        let pose = |who, pose, frame: &str| Update::Pose {
            who,
            pose,
            frame: frame.into(),
            speed: Some(SPEED),
        };
        let angle = SPEED * t / RADIUS;
        let plan: Vec<Point> = (0..80)
            .map(|i| {
                let a = angle + f64::from(i) * 0.04;
                ODOM_IN_MAP.transform(CENTRE + Point::new(a.cos(), a.sin()) * (RADIUS + 0.1))
            })
            .collect();
        let steer = (1.57 / RADIUS).atan() as f32;
        let heard = |source, detail: &str| Update::Heard {
            source,
            detail: detail.into(),
        };
        vec![
            Update::MapToOdom(ODOM_IN_MAP),
            pose(Localizer::Local, car, "odom"),
            pose(Localizer::Global, global, "map"),
            pose(Localizer::Truth, truth, "map"),
            pose(Localizer::Amcl, amcl, "map"),
            Update::Plan {
                points: plan,
                frame: "map".into(),
            },
            heard(
                Source::Imu,
                &format!("yaw rate {:+.1} deg/s", (SPEED / RADIUS).to_degrees()),
            ),
            heard(Source::Gps, "fix, 3 m"),
            heard(Source::Wheels, &format!("{SPEED:.2} m/s")),
            heard(Source::WheelOdom, &format!("{SPEED:.2} m/s")),
            Update::Vehicle(VehicleStatus {
                mode: Mode::Computer,
                armed: true,
                estop_active: false,
                speed: MetresPerSecond(SPEED as f32),
                steering_angle: Radians(steer),
                throttle: Fraction::new(0.2),
                brake: Fraction::new(0.0),
                faults: Faults(0),
            }),
            Update::Track(TrackStatus {
                tracker: "pure_pursuit".into(),
                cross_track: Some(0.04 * (t * 0.7).sin()),
                loop_ms: Some(0.3),
                missed_ticks: Some(0),
                steer: Some(f64::from(steer)),
                left: None,
            }),
        ]
    }

    fn take_scan(&mut self) -> Option<CubeScan> {
        let now = Instant::now();
        if let Some(bench) = &self.bench {
            return due(&mut self.last_scan, now, Duration::from_millis(100))
                .then(|| bench.clone());
        }
        if !due(&mut self.last_scan, now, Duration::from_millis(100)) {
            return None;
        }
        let t = self.t(now);
        let car = car_at(t);
        let lidar = Transform3 {
            translation: LIDAR,
            ..Transform3::IDENTITY
        };
        let stamp = Stamp((t * 1e9) as i64);
        Some(cubes::build(sweep(car), &lidar, car, stamp, &self.settings))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use debug_core::cubes::Metres;

    #[test]
    fn a_ray_hits_the_box_in_front() {
        let b = Aabb::new([5.0, -1.0, 0.0], [6.0, 1.0, 2.0]);
        assert_eq!(b.hit([0.0, 0.0, 1.0], [1.0, 0.0, 0.0]), Some(5.0));
        assert_eq!(b.hit([0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]), None);
        assert_eq!(b.hit([0.0, 0.0, 3.0], [1.0, 0.0, 0.0]), None);
    }

    #[test]
    fn the_sweep_sees_walls_and_ground() {
        let settings = CubeSettings {
            size: Metres(0.2),
            max_cubes: 100_000,
            ground_height: Metres(0.25),
        };
        let car = car_at(0.0);
        let lidar = Transform3 {
            translation: LIDAR,
            ..Transform3::IDENTITY
        };
        let scan = cubes::build(sweep(car), &lidar, car, Stamp(0), &settings);
        assert!(scan.cubes.len() > 1000, "{}", scan.cubes.len());
        assert!(scan.cubes.iter().any(|c| c.band == cubes::Band::Ground));
        assert!(scan.cubes.iter().any(|c| c.band != cubes::Band::Ground));
    }

    #[test]
    fn the_drawing_test_makes_n_cubes() {
        assert_eq!(bench_scan(20_000, 0.2).cubes.len(), 20_000);
    }
}
