//! The car, as a simple model: the steering motor, throttle, brake, wheel encoder and
//! where the car is.
//!
//! Good enough to close the loops above it (the spine's speed loop, the EKFs, Nav2), not
//! a vehicle-dynamics model. Every number in `PlantConfig::default` is a guess until the
//! car is measured (Q1-Q5).

use spine_core::Outputs;

#[derive(Debug, Clone, Copy)]
pub struct PlantConfig {
    /// Rear axle to front axle (m). vehicle.yaml overrides it.
    pub wheelbase: f32,
    /// The steering's mechanical stop (rad).
    pub max_steering: f32,
    /// How fast the steering motor turns the wheels (rad/s).
    pub steer_rate: f32,
    /// Acceleration at full throttle, on flat ground (m/s^2).
    pub max_accel: f32,
    /// Deceleration at full brake (m/s^2).
    pub max_brake: f32,
    /// Rolling resistance and air, as a speed decay (1/s).
    pub drag: f32,
    /// Wheel encoder counts per metre driven.
    pub ticks_per_metre: f32,
}

impl Default for PlantConfig {
    fn default() -> Self {
        PlantConfig {
            wheelbase: 1.57,
            max_steering: 0.5,
            steer_rate: 0.8,
            max_accel: 2.0,
            max_brake: 4.0,
            drag: 0.1,
            ticks_per_metre: 100.0,
        }
    }
}

/// Where the car is and how it moves: the ground truth the pretend sensors read.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct Pose {
    /// m, in the map frame: x east, y north.
    pub x: f64,
    pub y: f64,
    /// rad, from east, positive left (counter-clockwise).
    pub yaw: f64,
    /// m/s along the car, negative in reverse.
    pub speed: f32,
    /// rad/s.
    pub yaw_rate: f32,
    /// m/s^2 along the car.
    pub accel: f32,
    /// rad, the front wheels' angle, positive left.
    pub steering: f32,
}

pub struct Plant {
    cfg: PlantConfig,
    pose: Pose,
    ticks: f64,
}

impl Plant {
    pub fn new(cfg: PlantConfig, start: Pose) -> Self {
        Plant {
            cfg,
            pose: start,
            ticks: 0.0,
        }
    }

    pub fn pose(&self) -> Pose {
        self.pose
    }

    /// The encoder's 16-bit counter, as the spine sends it in VEHICLE_FEEDBACK.
    pub fn wheel_ticks(&self) -> u16 {
        (self.ticks as u64 & 0xFFFF) as u16
    }

    /// Move the model on by `dt` seconds under the spine's outputs.
    pub fn step(&mut self, out: &Outputs, dt: f32) {
        if dt <= 0.0 {
            return;
        }
        let c = self.cfg;
        let p = &mut self.pose;

        // The steering motor moves toward its target at a limited rate.
        let target = out.steering_target.clamp(-c.max_steering, c.max_steering);
        let step = c.steer_rate * dt;
        p.steering += (target - p.steering).clamp(-step, step);

        // The throttle pushes in the chosen direction. The brake and drag oppose the
        // motion, and never reverse it: they can only stop the car.
        let push =
            out.throttle.clamp(0.0, 1.0) * c.max_accel * if out.reverse { -1.0 } else { 1.0 };
        let before = p.speed;
        let mut v = before + push * dt;
        let resist = (out.brake.clamp(0.0, 1.0) * c.max_brake + c.drag * v.abs()) * dt;
        v = if v > 0.0 {
            (v - resist).max(0.0)
        } else {
            (v + resist).min(0.0)
        };
        p.accel = (v - before) / dt;
        p.speed = v;

        // The bicycle model about the rear axle: the same model ego uses.
        p.yaw_rate = v * p.steering.tan() / c.wheelbase;
        let (v, dt64) = (v as f64, dt as f64);
        p.x += v * p.yaw.cos() * dt64;
        p.y += v * p.yaw.sin() * dt64;
        p.yaw = wrap(p.yaw + p.yaw_rate as f64 * dt64);
        self.ticks += v.abs() * dt64 * c.ticks_per_metre as f64;
    }
}

/// An angle in -pi..pi.
fn wrap(a: f64) -> f64 {
    let t = core::f64::consts::TAU;
    let a = a % t;
    if a > t / 2.0 {
        a - t
    } else if a < -t / 2.0 {
        a + t
    } else {
        a
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use spine_core::protocol::Mode;

    fn outputs(throttle: f32, brake: f32, reverse: bool, steering: f32) -> Outputs {
        Outputs {
            mode: Mode::Computer,
            throttle,
            brake,
            reverse,
            steering_target: steering,
            armed: true,
            estop_active: false,
            faults: 0,
        }
    }

    fn run(plant: &mut Plant, out: Outputs, seconds: f32) {
        for _ in 0..(seconds * 100.0) as usize {
            plant.step(&out, 0.01);
        }
    }

    fn car() -> Plant {
        Plant::new(PlantConfig::default(), Pose::default())
    }

    #[test]
    fn steering_moves_at_the_motor_rate_and_stops_at_the_target() {
        let mut p = car();
        run(&mut p, outputs(0.0, 0.0, false, 0.4), 0.25);
        assert!(
            (p.pose().steering - 0.2).abs() < 1e-3,
            "0.8 rad/s for 0.25 s"
        );
        run(&mut p, outputs(0.0, 0.0, false, 0.4), 1.0);
        assert!((p.pose().steering - 0.4).abs() < 1e-6);
        run(&mut p, outputs(0.0, 0.0, false, 2.0), 2.0);
        assert!(
            (p.pose().steering - 0.5).abs() < 1e-6,
            "the mechanical stop"
        );
    }

    #[test]
    fn full_throttle_accelerates_then_drag_balances_it() {
        let mut p = car();
        run(&mut p, outputs(1.0, 0.0, false, 0.0), 1.0);
        let v = p.pose().speed;
        assert!(v > 1.7 && v < 2.0, "about 2 m/s^2 less a little drag: {v}");
        assert!(p.pose().x > 0.8 && p.pose().y.abs() < 1e-9, "straight east");
    }

    #[test]
    fn the_brake_stops_the_car_and_never_reverses_it() {
        let mut p = car();
        run(&mut p, outputs(1.0, 0.0, false, 0.0), 1.0);
        run(&mut p, outputs(0.0, 1.0, false, 0.0), 2.0);
        assert_eq!(p.pose().speed, 0.0);
    }

    #[test]
    fn reverse_drives_backwards() {
        let mut p = car();
        run(&mut p, outputs(0.5, 0.0, true, 0.0), 1.0);
        assert!(p.pose().speed < 0.0 && p.pose().x < 0.0);
    }

    #[test]
    fn a_steady_turn_is_a_circle_of_radius_wheelbase_over_tan_steering() {
        let mut p = Plant::new(PlantConfig::default(), Pose::default());
        // Lock the steering first, then drive at a steady speed by setting it directly.
        run(&mut p, outputs(0.0, 0.0, false, 0.3), 1.0);
        p.pose.speed = 1.0;
        let radius = 1.57 / 0.3f32.tan();
        let lap = 2.0 * core::f32::consts::PI * radius / 1.0;
        let c = PlantConfig {
            drag: 0.0,
            ..PlantConfig::default()
        };
        p.cfg = c;
        run(&mut p, outputs(0.0, 0.0, false, 0.3), lap);
        let (x, y) = (p.pose().x, p.pose().y);
        assert!(
            (x * x + y * y).sqrt() < 0.1,
            "back near the start after one lap: {x}, {y}"
        );
        assert!((p.pose().yaw_rate - 1.0 / radius).abs() < 1e-4);
    }

    #[test]
    fn the_encoder_counts_distance_and_wraps() {
        let mut p = car();
        p.pose.speed = 2.0;
        let c = PlantConfig {
            drag: 0.0,
            ..PlantConfig::default()
        };
        p.cfg = c;
        run(&mut p, outputs(0.0, 0.0, false, 0.0), 1.0);
        assert!(
            (p.wheel_ticks() as i32 - 200).abs() <= 1,
            "2 m at 100 counts per metre"
        );
        p.ticks = 65_535.5;
        assert_eq!(p.wheel_ticks(), 65_535);
        p.ticks = 65_536.2;
        assert_eq!(p.wheel_ticks(), 0);
    }

    #[test]
    fn yaw_stays_between_minus_pi_and_pi() {
        assert!((wrap(4.0) - (4.0 - core::f64::consts::TAU)).abs() < 1e-12);
        assert!((wrap(-4.0) - (-4.0 + core::f64::consts::TAU)).abs() < 1e-12);
        assert_eq!(wrap(1.0), 1.0);
    }
}
