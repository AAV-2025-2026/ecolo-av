//! Speed controller: target and measured speed in, throttle, brake and
//! direction out. The gains are starting points to tune on the car.
//!
//! While it uses the throttle, the loop is a PI with a setpoint weight `b`:
//!
//! ```text
//! throttle = kp·(b·target − speed) + integral,    integral += ki·(target − speed)·dt
//! ```
//!
//! `b` = 1 is the textbook PI: today's [`SpeedLoopConfig::default`]. A `b` below 1 moves
//! the PI's zero away from the slow pole, which is what made the loop overshoot about 15%
//! (TODO 27, `docs/vehicle-model.md`, "Tuning the speed loop"). [`SpeedLoopProfile`] names
//! the parameter sets the simulators and the car-day tests can switch between.

use core::fmt;
use core::str::FromStr;

use crate::limits::abs;

/// How the integral is kept from winding up.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AntiWindup {
    /// Only its bounds: 0 to `integral_limit`. Today's loop.
    #[default]
    Bounds,
    /// Its bounds, and no integrating while the throttle is pinned (full, or none) in the
    /// error's direction: conditional integration ("clamping").
    Clamp,
}

#[derive(Debug, Clone, Copy)]
pub struct SpeedLoopConfig {
    /// Throttle (0..1) per m/s of speed error.
    pub kp: f32,
    /// Throttle per (m/s x s) of accumulated error.
    pub ki: f32,
    /// Largest throttle the integral term may contribute, beyond the share of the target
    /// the P term leaves to it, `(1 − setpoint_weight)·kp·target` (none at weight 1).
    pub integral_limit: f32,
    /// The share of the target the P term sees, `b` (0..1): 1 is a plain PI.
    pub setpoint_weight: f32,
    /// How the integral is kept from winding up.
    pub anti_windup: AntiWindup,
    /// Brake (0..1) per m/s of overspeed beyond `coast_band`.
    pub brake_gain: f32,
    /// Overspeed (m/s) handled by coasting before the brake is used.
    pub coast_band: f32,
    /// Below this |speed| (m/s) the car counts as stopped.
    pub stopped_speed: f32,
    /// Brake held while stopped with a zero target, so the car can't roll.
    pub hold_brake: f32,
}

impl Default for SpeedLoopConfig {
    fn default() -> Self {
        SpeedLoopConfig {
            kp: 0.3,
            ki: 0.1,
            integral_limit: 0.3,
            setpoint_weight: 1.0,
            anti_windup: AntiWindup::Bounds,
            brake_gain: 0.5,
            coast_band: 0.2,
            stopped_speed: 0.05,
            hold_brake: 0.3,
        }
    }
}

impl SpeedLoopConfig {
    /// The `smooth` profile (TODO 27, proposed for the car day, not the default): no
    /// overshoot on the model, robust to the throttle's 5x uncertainty (TODO 52b).
    ///
    /// - kp 1.0, ki 0.25: real poles at −0.28 and −1.32 /s on the model (ζ 1.3).
    /// - setpoint weight 0.75: the zero moves to −ki/(b·kp) = −0.33, past the slow pole.
    /// - integral limit 1.0 and clamping: the integral may hold up to full throttle (a weak
    ///   throttle needs it), but never winds up while the throttle is pinned.
    pub fn smooth() -> Self {
        SpeedLoopConfig {
            kp: 1.0,
            ki: 0.25,
            integral_limit: 1.0,
            setpoint_weight: 0.75,
            anti_windup: AntiWindup::Clamp,
            ..SpeedLoopConfig::default()
        }
    }
}

/// The named parameter sets: the simulators' `speed_loop` parameter, the car-day tests.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum SpeedLoopProfile {
    /// [`SpeedLoopConfig::default`]: today's guessed gains (overshoots about 15%).
    #[default]
    Default,
    /// [`SpeedLoopConfig::smooth`]: TODO 27's design, to try on stands.
    Smooth,
}

impl SpeedLoopProfile {
    /// Every profile, in the order the docs list them.
    pub const ALL: [SpeedLoopProfile; 2] = [SpeedLoopProfile::Default, SpeedLoopProfile::Smooth];

    /// The profile's name, as the parameter and the docs spell it.
    pub fn name(self) -> &'static str {
        match self {
            SpeedLoopProfile::Default => "default",
            SpeedLoopProfile::Smooth => "smooth",
        }
    }

    /// The profile's parameters.
    pub fn config(self) -> SpeedLoopConfig {
        match self {
            SpeedLoopProfile::Default => SpeedLoopConfig::default(),
            SpeedLoopProfile::Smooth => SpeedLoopConfig::smooth(),
        }
    }
}

/// A profile name that isn't one of [`SpeedLoopProfile::ALL`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UnknownProfile;

impl fmt::Display for UnknownProfile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("no such speed loop profile: pick default or smooth")
    }
}

impl FromStr for SpeedLoopProfile {
    type Err = UnknownProfile;

    fn from_str(name: &str) -> Result<Self, Self::Err> {
        SpeedLoopProfile::ALL
            .into_iter()
            .find(|p| p.name() == name)
            .ok_or(UnknownProfile)
    }
}

/// Actuator demand. Throttle and brake are never both above zero.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Drive {
    pub throttle: f32,
    pub brake: f32,
    pub reverse: bool,
}

pub struct SpeedLoop {
    cfg: SpeedLoopConfig,
    integral: f32,
    reverse: bool,
}

fn clamp01(x: f32) -> f32 {
    x.clamp(0.0, 1.0)
}

impl SpeedLoop {
    pub fn new(cfg: SpeedLoopConfig) -> Self {
        SpeedLoop {
            cfg,
            integral: 0.0,
            reverse: false,
        }
    }

    pub fn reset(&mut self) {
        self.integral = 0.0;
    }

    pub fn update(&mut self, target: f32, measured: f32, dt: f32) -> Drive {
        let c = self.cfg;
        let stopped = abs(measured) < c.stopped_speed;
        let want_reverse = target < 0.0;

        // The gear only changes while stopped; until then, brake.
        if target != 0.0 && want_reverse != self.reverse {
            if stopped {
                self.reverse = want_reverse;
                self.integral = 0.0;
            } else {
                self.integral = 0.0;
                let brake = clamp01(c.hold_brake.max(c.brake_gain * abs(measured)));
                return Drive {
                    throttle: 0.0,
                    brake,
                    reverse: self.reverse,
                };
            }
        }

        // Work along the direction of travel, so both directions use one law.
        let sign = if self.reverse { -1.0 } else { 1.0 };
        let t = target * sign;
        let m = measured * sign;

        // A stop: brake until stopped, then hold. Never coast here: below the coast band
        // the car would only slow by rolling resistance, and on a slope it might never
        // stop (found on the bench: it crept on at 0.2 m/s).
        if t <= 0.0 {
            self.integral = 0.0;
            let brake = if stopped {
                c.hold_brake
            } else {
                clamp01(c.hold_brake.max(c.brake_gain * (m - c.coast_band)))
            };
            return Drive {
                throttle: 0.0,
                brake,
                reverse: self.reverse,
            };
        }

        let error = t - m;
        // The P term sees b·target; the integral holds the rest, (1 − b)·kp·target, on top
        // of its own limit. With b = 1 both are today's loop exactly.
        let proportional = c.kp * (c.setpoint_weight * t - m);
        let ceiling = c.integral_limit + (1.0 - c.setpoint_weight) * c.kp * t;
        let integral = (self.integral + c.ki * error * dt).clamp(0.0, ceiling.max(0.0));
        let pinned = match c.anti_windup {
            AntiWindup::Bounds => false,
            AntiWindup::Clamp => {
                let demand = proportional + integral;
                (demand > 1.0 && error > 0.0) || (demand < 0.0 && error < 0.0)
            }
        };
        if !pinned {
            self.integral = integral;
        }
        let overspeed = -error - c.coast_band;
        if overspeed > 0.0 {
            self.integral = 0.0;
            return Drive {
                throttle: 0.0,
                brake: clamp01(c.brake_gain * overspeed),
                reverse: self.reverse,
            };
        }
        Drive {
            throttle: clamp01(proportional + self.integral),
            brake: 0.0,
            reverse: self.reverse,
        }
    }
}

impl SpeedLoop {
    /// Open loop, for a board with no wheel speed: throttle in proportion to the target,
    /// `full_throttle_speed` (m/s) being full throttle, as the 2025-26 firmware drove.
    ///
    /// - Below `stopped_speed`: no throttle, and the hold brake, as a stop does closed loop.
    /// - The gear changes only on a tick with no throttle: the first tick past zero.
    pub fn open_loop(&mut self, target: f32, full_throttle_speed: f32) -> Drive {
        let c = self.cfg;
        self.integral = 0.0;
        if abs(target) < c.stopped_speed || target.is_nan() {
            return Drive {
                throttle: 0.0,
                brake: c.hold_brake,
                reverse: self.reverse,
            };
        }
        let want_reverse = target < 0.0;
        if want_reverse != self.reverse {
            self.reverse = want_reverse;
            return Drive {
                throttle: 0.0,
                brake: 0.0,
                reverse: self.reverse,
            };
        }
        let throttle = if full_throttle_speed > 0.0 {
            clamp01(abs(target) / full_throttle_speed)
        } else {
            0.0
        };
        Drive {
            throttle,
            brake: 0.0,
            reverse: self.reverse,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lp() -> SpeedLoop {
        SpeedLoop::new(SpeedLoopConfig::default())
    }

    #[test]
    fn accelerates_from_rest() {
        let d = lp().update(1.0, 0.0, 0.02);
        assert!(d.throttle > 0.0);
        assert_eq!(d.brake, 0.0);
        assert!(!d.reverse);
    }

    #[test]
    fn brakes_when_too_fast() {
        let d = lp().update(1.0, 2.0, 0.02);
        assert_eq!(d.throttle, 0.0);
        assert!(d.brake > 0.0);
    }

    #[test]
    fn a_stop_brakes_all_the_way_instead_of_coasting() {
        for speed in [0.1, 0.19, 0.5, 2.0] {
            let d = lp().update(0.0, speed, 0.02);
            assert_eq!(d.throttle, 0.0);
            assert!(
                d.brake >= SpeedLoopConfig::default().hold_brake,
                "at {speed} m/s"
            );
        }
    }

    #[test]
    fn coasts_when_slightly_fast() {
        let d = lp().update(1.0, 1.1, 0.02);
        assert_eq!(d.brake, 0.0);
    }

    #[test]
    fn holds_brake_when_stopped() {
        let d = lp().update(0.0, 0.0, 0.02);
        assert_eq!(d.throttle, 0.0);
        assert_eq!(d.brake, SpeedLoopConfig::default().hold_brake);
    }

    #[test]
    fn reverses_only_after_stopping() {
        let mut l = lp();
        let d = l.update(-0.5, 1.0, 0.02);
        assert!(!d.reverse);
        assert!(d.brake > 0.0);
        let d = l.update(-0.5, 0.0, 0.02);
        assert!(d.reverse);
        assert!(d.throttle > 0.0);
    }

    #[test]
    fn integral_is_bounded() {
        let mut l = lp();
        for _ in 0..10_000 {
            l.update(5.0, 0.0, 0.02);
        }
        let d = l.update(5.0, 4.99, 0.02);
        assert!(d.throttle <= 0.3 + 0.3 * 0.01 + 1e-6);
    }

    /// Today's update, as it was before the setpoint weight and the clamping (22 Oct).
    fn old_update(integral: &mut f32, c: &SpeedLoopConfig, t: f32, m: f32, dt: f32) -> f32 {
        let error = t.max(0.0) - m;
        *integral = (*integral + c.ki * error * dt).clamp(0.0, c.integral_limit);
        clamp01(c.kp * error + *integral)
    }

    #[test]
    fn the_default_is_todays_loop_to_the_bit() {
        let c = SpeedLoopConfig::default();
        let mut l = lp();
        let mut integral = 0.0;
        for k in 0..3000 {
            let t = 1.0 + 0.5 * libm_free_wave(k);
            let m = 0.9 * t + 0.2 * libm_free_wave(k + 7);
            let d = l.update(t, m, 0.01);
            if d.brake == 0.0 {
                assert_eq!(
                    d.throttle,
                    old_update(&mut integral, &c, t, m, 0.01),
                    "tick {k}"
                );
            } else {
                integral = 0.0;
            }
        }
    }

    /// A triangle wave in -1..1 with no maths library (no_std).
    fn libm_free_wave(k: u32) -> f32 {
        let x = (k % 400) as f32 / 100.0;
        if x < 2.0 {
            x - 1.0
        } else {
            3.0 - x
        }
    }

    #[test]
    fn profiles_go_by_name() {
        for p in SpeedLoopProfile::ALL {
            assert_eq!(p.name().parse::<SpeedLoopProfile>(), Ok(p));
        }
        assert_eq!("fast".parse::<SpeedLoopProfile>(), Err(UnknownProfile));
        assert_eq!(SpeedLoopProfile::default(), SpeedLoopProfile::Default);
        assert_eq!(SpeedLoopProfile::Default.config().setpoint_weight, 1.0);
        assert_eq!(
            SpeedLoopProfile::Default.config().anti_windup,
            AntiWindup::Bounds
        );
        let s = SpeedLoopProfile::Smooth.config();
        assert_eq!((s.kp, s.ki, s.setpoint_weight), (1.0, 0.25, 0.75));
        assert_eq!(s.anti_windup, AntiWindup::Clamp);
    }

    #[test]
    fn the_p_term_sees_the_weighted_target() {
        let mut l = SpeedLoop::new(SpeedLoopConfig::smooth());
        let d = l.update(1.0, 0.0, 0.01);
        // kp (b·1 − 0) + ki·1·dt
        assert!(
            (d.throttle - (0.75 + 0.25 * 0.01)).abs() < 1e-6,
            "{}",
            d.throttle
        );
    }

    /// The model car of docs/vehicle-model.md (vehicle.yaml's guesses): the throttle's lag,
    /// full throttle 1.5 m/s², drag 0.1 /s, full brake 3 m/s². Returns the peak and the
    /// final speed for a target ramped at ego's 1 m/s².
    fn drive(cfg: SpeedLoopConfig, max_accel: f32, target: f32) -> (f32, f32) {
        let dt = 0.01;
        let mut l = SpeedLoop::new(cfg);
        let (mut v, mut throttle, mut brake, mut set, mut peak) =
            (0.0f32, 0.0f32, 0.0f32, 0.0f32, 0.0f32);
        for _ in 0..4000 {
            set = (set + dt).min(target);
            let d = l.update(set, v, dt);
            throttle += (d.throttle - throttle) * dt / 0.1;
            brake += (d.brake - brake) * dt / 0.2;
            let pushed = v + throttle * max_accel * dt;
            v = (pushed - (brake * 3.0 + 0.1 * pushed) * dt).max(0.0);
            peak = peak.max(v);
        }
        (peak, v)
    }

    #[test]
    fn today_overshoots_and_smooth_does_not() {
        for target in [0.5, 1.0, 2.0] {
            let (peak, end) = drive(SpeedLoopConfig::default(), 1.5, target);
            assert!(peak > 1.09 * target, "today at {target}: peak {peak}");
            assert!((end - target).abs() < 0.02 * target);
            let (peak, end) = drive(SpeedLoopConfig::smooth(), 1.5, target);
            assert!(peak < 1.01 * target, "smooth at {target}: peak {peak}");
            assert!(
                (end - target).abs() < 0.01 * target,
                "smooth at {target}: {end}"
            );
        }
    }

    #[test]
    fn a_weak_throttle_still_reaches_the_target_with_smooth() {
        // Full throttle 5x weaker (TODO 52b): 2 m/s needs 2/3 throttle, more than today's
        // integral may give (0.3).
        let (_, end) = drive(SpeedLoopConfig::default(), 0.3, 2.0);
        assert!(end < 1.6, "today stops short: {end}");
        let (peak, end) = drive(SpeedLoopConfig::smooth(), 0.3, 2.0);
        assert!((end - 2.0).abs() < 0.05, "smooth: {end}");
        assert!(peak < 2.2, "smooth: peak {peak}");
    }

    #[test]
    fn clamping_stops_the_integral_while_the_throttle_is_full() {
        let clamped = SpeedLoopConfig::smooth();
        let bounded = SpeedLoopConfig {
            anti_windup: AntiWindup::Bounds,
            ..clamped
        };
        let mut a = SpeedLoop::new(clamped);
        let mut b = SpeedLoop::new(bounded);
        for _ in 0..2000 {
            // Held back (a hill, the brake): full throttle for 20 s.
            assert_eq!(a.update(3.0, 0.0, 0.01).throttle, 1.0);
            b.update(3.0, 0.0, 0.01);
        }
        // Let go, the car nearly there: the clamped integral never grew, the other did.
        assert_eq!(a.update(3.0, 2.9, 0.01).throttle, 0.0);
        assert!(b.update(3.0, 2.9, 0.01).throttle > 0.9);
    }

    #[test]
    fn the_integral_may_hold_the_targets_share_on_top_of_its_limit() {
        // Smooth, at 2 m/s on a weak throttle: the integral holds (1 − b)·kp·2 = 0.5 plus up
        // to 1.0 of its own; the throttle never goes past full.
        let mut l = SpeedLoop::new(SpeedLoopConfig::smooth());
        for _ in 0..100_000 {
            let d = l.update(2.0, 1.9, 0.01);
            assert!(d.throttle <= 1.0);
        }
        // kp (b·2 − 1.9) + integral = −0.4 + integral: (nearly) full throttle needs an
        // integral of 1.4, past today's 0.3; clamping stops it at full.
        let t = l.update(2.0, 1.9, 0.01).throttle;
        assert!(t > 0.999 && t <= 1.0, "{t}");
    }

    #[test]
    fn open_loop_throttle_follows_the_target() {
        let mut l = lp();
        let d = l.open_loop(1.5, 3.0);
        assert_eq!((d.throttle, d.brake, d.reverse), (0.5, 0.0, false));
        assert_eq!(l.open_loop(6.0, 3.0).throttle, 1.0); // never past full
        assert_eq!(l.open_loop(1.0, 0.0).throttle, 0.0); // no scale, no throttle
    }

    #[test]
    fn open_loop_holds_the_brake_at_zero() {
        let mut l = lp();
        let d = l.open_loop(0.0, 3.0);
        assert_eq!(d.throttle, 0.0);
        assert_eq!(d.brake, SpeedLoopConfig::default().hold_brake);
        assert_eq!(l.open_loop(f32::NAN, 3.0).throttle, 0.0);
    }

    #[test]
    fn open_loop_changes_gear_with_no_throttle() {
        let mut l = lp();
        assert!(!l.open_loop(1.0, 3.0).reverse);
        let d = l.open_loop(-1.0, 3.0);
        assert_eq!((d.throttle, d.reverse), (0.0, true)); // the gear first
        let d = l.open_loop(-1.0, 3.0);
        assert!(d.throttle > 0.0 && d.reverse); // then the throttle
    }
}
