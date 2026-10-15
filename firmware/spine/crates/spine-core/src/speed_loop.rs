//! Speed controller: target and measured speed in, throttle, brake and
//! direction out. The gains are starting points to tune on the car.

use crate::limits::abs;

#[derive(Debug, Clone, Copy)]
pub struct SpeedLoopConfig {
    /// Throttle (0..1) per m/s of speed error.
    pub kp: f32,
    /// Throttle per (m/s x s) of accumulated error.
    pub ki: f32,
    /// Largest throttle the integral term may contribute.
    pub integral_limit: f32,
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
            brake_gain: 0.5,
            coast_band: 0.2,
            stopped_speed: 0.05,
            hold_brake: 0.3,
        }
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

        let error = t.max(0.0) - m;
        self.integral = (self.integral + c.ki * error * dt).clamp(0.0, c.integral_limit);
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
            throttle: clamp01(c.kp * error + self.integral),
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
