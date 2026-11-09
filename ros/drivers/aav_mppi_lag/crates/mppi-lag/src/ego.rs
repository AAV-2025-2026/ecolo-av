//! Ego between the driver and the car: its ramps, as a stage in front of any car model.
//!
//! A driver's command doesn't reach the actuators as sent: ego (aav_ego `ackermann.py`)
//! slews the speed at max_acceleration / max_deceleration, turns the steering at most
//! max_steering_rate, and holds the steering while the commanded speed is under
//! min_speed_for_steering. [`Driven`] puts that in front of a [`CarModel`], so MPPI's
//! samples carry ego's state as well as the car's.
//!
//! Why a stage and not limits on the samples (Nav2 clips each sample's steps to ax_max
//! and ax_min): clipped noise with a slower rise than fall drifts every sample slower,
//! the creep nav2.yaml's MPPI block worked around with ax_max 3.0. Here the samples are
//! free within the speed range and full lock; ego's ramps act on them as they would on
//! the car. Not modelled: ego's jerk limit and its sideways-acceleration slow-down (off
//! at our speeds: 0.35 m/s² at 1 m/s and full lock, against its 2.0).

use crate::model::{CarModel, Command, Observation, Pose};

/// ego.yaml's limits on what reaches the car.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Ego {
    /// m/s² while speeding up.
    pub max_acceleration: f64,
    /// m/s² while slowing down (positive).
    pub max_deceleration: f64,
    /// rad/s.
    pub max_steering_rate: f64,
    /// m/s: below this commanded speed the steering holds.
    pub min_speed_for_steering: f64,
    /// rad: full lock.
    pub max_steering_angle: f64,
}

impl Default for Ego {
    /// ego.yaml (7 Nov) and vehicle.yaml's full lock.
    fn default() -> Self {
        Self {
            max_acceleration: 1.0,
            max_deceleration: 2.0,
            max_steering_rate: 0.6,
            min_speed_for_steering: 0.05,
            max_steering_angle: 0.5,
        }
    }
}

impl Ego {
    /// Move ego's output `out` on by `dt` toward the driver's `command`.
    pub fn step(&self, out: &mut Command, command: Command, dt: f64) {
        out.speed += (command.speed - out.speed)
            .clamp(-self.max_deceleration * dt, self.max_acceleration * dt);
        if command.speed.abs() >= self.min_speed_for_steering {
            let full = self.max_steering_angle;
            let most = self.max_steering_rate * dt;
            out.steer += (command.steer.clamp(-full, full) - out.steer).clamp(-most, most);
        }
    }
}

/// A car model with ego in front of it.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Driven<M> {
    /// Ego's limits.
    pub ego: Ego,
    /// The car behind ego.
    pub car: M,
}

/// Ego's output so far, and the car's state.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DrivenState<S> {
    /// What ego sends the car now.
    pub ego: Command,
    /// The car.
    pub car: S,
}

impl<M: CarModel> Driven<M> {
    /// Ego's output set to the car as it is: its speed and the wheels' angle (taking over
    /// from another driver, or at the start).
    pub fn resync(&self, state: &mut DrivenState<M::State>) {
        state.ego = Command::new(self.car.speed(&state.car), self.car.steering(&state.car));
    }
}

impl<M: CarModel> CarModel for Driven<M> {
    type State = DrivenState<M::State>;

    fn at_rest(&self, pose: Pose, speed: f64) -> Self::State {
        let car = self.car.at_rest(pose, speed);
        DrivenState {
            ego: Command::new(speed, self.car.steering(&car)),
            car,
        }
    }

    fn step(&self, state: &mut Self::State, command: Command, dt: f64) {
        self.ego.step(&mut state.ego, command, dt);
        self.car.step(&mut state.car, state.ego, dt);
    }

    fn observe(&self, state: &mut Self::State, seen: &Observation) {
        self.car.observe(&mut state.car, seen);
    }

    fn pose(&self, state: &Self::State) -> Pose {
        self.car.pose(&state.car)
    }

    fn speed(&self, state: &Self::State) -> f64 {
        self.car.speed(&state.car)
    }

    fn steering(&self, state: &Self::State) -> f64 {
        self.car.steering(&state.car)
    }

    fn wheelbase(&self) -> f64 {
        self.car.wheelbase()
    }

    fn lag_aware(&self) -> bool {
        self.car.lag_aware()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ideal::IdealModel;

    #[test]
    fn ego_ramps_speed_and_steering() {
        let ego = Ego::default();
        let mut out = Command::default();
        ego.step(&mut out, Command::new(1.0, 0.5), 0.1);
        assert!((out.speed - 0.1).abs() < 1e-12);
        assert!((out.steer - 0.06).abs() < 1e-12);
        ego.step(&mut out, Command::new(0.0, 0.5), 0.1);
        assert!(out.speed.abs() < 1e-12, "slows at 2 m/s²");
        assert!(
            (out.steer - 0.06).abs() < 1e-12,
            "holds while the command is a stop"
        );
    }

    #[test]
    fn driven_feeds_ego_output_to_the_car() {
        let m = Driven {
            ego: Ego::default(),
            car: IdealModel {
                accel: 100.0,
                decel: 100.0,
                ..IdealModel::default()
            },
        };
        let mut s = m.at_rest(Pose::default(), 0.0);
        m.step(&mut s, Command::new(1.0, 0.3), 0.05);
        assert!(
            (m.speed(&s) - 0.05).abs() < 1e-12,
            "ego's ramp, not the car's"
        );
        assert!((m.steering(&s) - 0.03).abs() < 1e-12);
        s.car.speed = 0.7;
        m.resync(&mut s);
        assert_eq!(s.ego.speed, 0.7);
    }
}
