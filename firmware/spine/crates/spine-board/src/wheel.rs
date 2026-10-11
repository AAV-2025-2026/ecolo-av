//! The car's speed, from the wheel encoder's counter.
//!
//! `spine_core::encoder::SpeedEstimator` works from the time between counts, so it
//! stays smooth at walking pace. It wants to hear about every count. The board gives
//! a counter and the time of its latest count instead; when several counts arrive
//! between two ticks, they are spread evenly over the time since the last one.

use crate::board::WheelCount;
use aav_inputs::{Edge, Lockout};
use spine_core::encoder::SpeedEstimator;

#[derive(Debug, Clone, Copy)]
pub struct WheelSpeed {
    estimator: SpeedEstimator,
    last: Option<WheelCount>,
}

impl WheelSpeed {
    pub fn new(metres_per_count: f32, timeout_ms: u32) -> Self {
        WheelSpeed {
            estimator: SpeedEstimator::new(metres_per_count, timeout_ms.saturating_mul(1000)),
            last: None,
        }
    }

    /// Feed the counter as read at `now_ms`. Returns the speed in m/s, positive
    /// forward.
    pub fn update(&mut self, wheel: WheelCount, now_ms: u32) -> f32 {
        if let Some(last) = self.last {
            let counts = wheel.count.wrapping_sub(last.count);
            if counts != 0 {
                let step = if counts > 0 { 1 } else { -1 };
                let n = counts.unsigned_abs();
                let at_us = us(wheel.at_ms);
                if n > 1 {
                    // The count before the latest one, one average period earlier.
                    let period_us = us(wheel.at_ms.wrapping_sub(last.at_ms)) / n;
                    self.estimator.on_count(at_us.wrapping_sub(period_us), step);
                }
                self.estimator.on_count(at_us, step);
            }
        }
        self.last = Some(wheel);
        self.estimator.speed(us(now_ms))
    }
}

/// Two spoke sensors, A and B, for a board that reads them itself, about every millisecond.
///
/// The rule of the 2025-26 encoder Pico 2 (`firmware/legacy/wheel_encoder_pico2/wiznet.ino`,
/// `sensor_callback()`): one count on A's rising edge, and backwards if B rose in the 20 ms
/// before and is still high. Each sensor is cleaned by an `aav_inputs::Lockout` of 10 ms, the
/// 2025-26 debounce, so a flicker at the edge of a spoke counts once.
///
/// TODO(Q5): which wheel, how far apart the sensors are, and which way is forward. Turning
/// slowly backwards, with B more than 20 ms ahead of A, counts as forward, as it did before.
#[derive(Debug, Clone, Copy)]
pub struct SpokeSensors {
    a: Lockout,
    b: Lockout,
    b_rose_ms: Option<u32>,
    direction_window_ms: u32,
    count: WheelCount,
}

impl SpokeSensors {
    /// The 2025-26 numbers: 10 ms of lockout on each sensor, a 20 ms window for B.
    pub const TODAY: SpokeSensors = SpokeSensors::new(10, 20);

    pub const fn new(lockout_ms: u32, direction_window_ms: u32) -> Self {
        SpokeSensors {
            a: Lockout::new(false, lockout_ms),
            b: Lockout::new(false, lockout_ms),
            b_rose_ms: None,
            direction_window_ms,
            count: WheelCount { count: 0, at_ms: 0 },
        }
    }

    /// Feed both sensors' raw levels, read at `now_ms`. Returns the counter.
    pub fn update(&mut self, a: bool, b: bool, now_ms: u32) -> WheelCount {
        if self.b.update(b, now_ms) == Some(Edge::Rising) {
            self.b_rose_ms = Some(now_ms);
        }
        if self.a.update(a, now_ms) == Some(Edge::Rising) {
            let b_ahead = self.b.level()
                && self
                    .b_rose_ms
                    .is_some_and(|t| now_ms.wrapping_sub(t) < self.direction_window_ms);
            self.count = WheelCount {
                count: self.count.count.wrapping_add(if b_ahead { -1 } else { 1 }),
                at_ms: now_ms,
            };
        }
        self.count
    }

    /// The counter, and the clock at its latest count.
    pub fn count(&self) -> WheelCount {
        self.count
    }
}

/// Milliseconds to the estimator's microseconds. Both wrap, and only differences
/// matter, so the wrap is harmless.
fn us(ms: u32) -> u32 {
    ms.wrapping_mul(1000)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 0.1 m a count, stopped after 1 s without a count.
    fn wheel() -> WheelSpeed {
        WheelSpeed::new(0.1, 1000)
    }

    fn at(count: i32, at_ms: u32) -> WheelCount {
        WheelCount { count, at_ms }
    }

    #[test]
    fn stopped_until_it_moves() {
        let mut w = wheel();
        assert_eq!(w.update(at(0, 0), 0), 0.0);
        assert_eq!(w.update(at(0, 0), 500), 0.0);
    }

    #[test]
    fn one_count_a_tick() {
        // A count every 50 ms at 0.1 m a count: 2 m/s.
        let mut w = wheel();
        w.update(at(0, 0), 0);
        let mut v = 0.0;
        for i in 1..=5 {
            v = w.update(at(i, i as u32 * 50), i as u32 * 50);
        }
        assert!((v - 2.0).abs() < 1e-4, "{v}");
    }

    #[test]
    fn several_counts_a_tick() {
        // 5 counts every 10 ms: 50 m/s, far too fast for the car, but simple maths.
        let mut w = wheel();
        w.update(at(0, 0), 0);
        w.update(at(5, 10), 10);
        let v = w.update(at(10, 20), 20);
        assert!((v - 50.0).abs() < 1e-3, "{v}");
    }

    #[test]
    fn reverse_is_negative() {
        let mut w = wheel();
        w.update(at(100, 0), 0);
        w.update(at(99, 100), 100);
        let v = w.update(at(98, 200), 200);
        assert!((v + 1.0).abs() < 1e-4, "{v}");
    }

    #[test]
    fn slows_then_stops_without_counts() {
        let mut w = wheel();
        w.update(at(0, 0), 0);
        w.update(at(1, 100), 100);
        w.update(at(2, 200), 200); // 1 m/s
        assert!(w.update(at(2, 200), 400) < 0.6); // 200 ms since the last count
        assert_eq!(w.update(at(2, 200), 1300), 0.0); // over the 1 s timeout
    }

    /// One spoke every 40 ms for 400 ms, sampled every millisecond. `a` and `b` say when, in
    /// each 40 ms, each sensor sees the spoke.
    fn spokes(a: core::ops::Range<u32>, b: core::ops::Range<u32>) -> WheelCount {
        let mut sensors = SpokeSensors::TODAY;
        (0..400)
            .map(|ms| sensors.update(a.contains(&(ms % 40)), b.contains(&(ms % 40)), ms))
            .last()
            .unwrap()
    }

    #[test]
    fn spokes_forward_count_up() {
        // A sees each spoke first: ten spokes, the last at 360 ms.
        assert_eq!(spokes(0..15, 10..25), at(10, 360));
    }

    #[test]
    fn spokes_backward_count_down() {
        // B sees each spoke 10 ms before A.
        assert_eq!(spokes(10..25, 0..15), at(-10, 370));
    }

    #[test]
    fn a_flicker_counts_once() {
        // A flickers for 4 ms at the edge of each spoke.
        let mut sensors = SpokeSensors::TODAY;
        let a = |ms: u32| matches!(ms % 40, 0 | 2 | 4..=15);
        let last = (0..400).map(|ms| sensors.update(a(ms), false, ms)).last();
        assert_eq!(last, Some(at(10, 360)));
    }

    #[test]
    fn b_ahead_by_more_than_the_window_is_forward() {
        // B rose 30 ms before A and is still high: the 2025-26 rule says forward.
        let mut sensors = SpokeSensors::TODAY;
        for ms in 0..30 {
            sensors.update(false, true, ms);
        }
        assert_eq!(sensors.update(true, true, 30), at(1, 30));
    }

    #[test]
    fn spokes_feed_the_speed() {
        // A spoke every 40 ms at 0.1178 m a spoke: 2.945 m/s.
        let mut sensors = SpokeSensors::TODAY;
        let mut speed = WheelSpeed::new(0.1178, 1000);
        let mut v = 0.0;
        for ms in 0..400 {
            let count = sensors.update(ms % 40 < 15, (10..25).contains(&(ms % 40)), ms);
            if ms % 10 == 0 {
                v = speed.update(count, ms); // the spine's tick reads it every 10 ms
            }
        }
        assert!((v - 2.945).abs() < 0.01, "{v}");
    }

    #[test]
    fn survives_the_counter_wrapping() {
        let mut w = wheel();
        w.update(at(i32::MAX - 1, 0), 0);
        w.update(at(i32::MAX, 100), 100);
        let v = w.update(at(i32::MIN, 200), 200); // one more count forward
        assert!((v - 1.0).abs() < 1e-4, "{v}");
    }
}
