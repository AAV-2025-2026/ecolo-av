//! From channels to `spine_core::RcInput`: the override switch, throttle and steering.
//!
//! The numbers are the 2025-26 firmware's (`main.cpp` `loop()`, `rc_handler.cpp`
//! `handleRCMode()`). It counted channels from 0, as its iBUS library does, so
//! "channel 5" there is CH6 on the transmitter.
//!
//! | Index | On the transmitter | Use |
//! |---|---|---|
//! | 5 | CH6 | override switch: RC drives above 1500 |
//! | 2 | CH3 | throttle stick |
//! | 3 | CH4 | steering stick |
//! | 4 | CH5 | gear switch: forward below 1200, reverse above 1800, brake between |
//!
//! TODO(Q7): check on the transmitter which switch is CH6 and which is CH5. The C++
//! prints "SwC: TOP=Brake, MID=Fwd, LOW=Rev" at start-up, but its code puts the brake
//! in the middle. The code's order is kept here.

use crate::frame::Channels;
use spine_core::RcInput;

/// Which channel does what, and where the switches change over.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RcMap {
    /// Channel indexes, from 0 (index 0 is CH1).
    pub override_switch: usize,
    pub throttle: usize,
    pub steering: usize,
    pub gear: usize,
    /// A channel is usable only strictly between these (the C++: 100 and 2200).
    pub valid_above: u16,
    pub valid_below: u16,
    /// RC drives while the override switch reads above this.
    pub override_above: u16,
    /// The gear switch: forward below `forward_below`, reverse above
    /// `reverse_above`, brake in between.
    pub forward_below: u16,
    pub reverse_above: u16,
    /// A stick's middle, and how far it travels each way (µs).
    pub centre: u16,
    pub half_travel: u16,
    /// Throttle at or below this fraction counts as none (the C++: 5 %).
    pub throttle_deadband: f32,
}

impl Default for RcMap {
    fn default() -> Self {
        Self::TODAY
    }
}

impl RcMap {
    /// Today's car.
    pub const TODAY: RcMap = RcMap {
        override_switch: 5,
        throttle: 2,
        steering: 3,
        gear: 4,
        valid_above: 100,
        valid_below: 2200,
        override_above: 1500,
        forward_below: 1200,
        reverse_above: 1800,
        centre: 1500,
        half_travel: 500,
        throttle_deadband: 0.05,
    };

    /// What the RC asks for, or None if the override switch reads out of range.
    ///
    /// - Override off: `override_switch: false`, nothing else.
    /// - Override on: throttle and steering, each -1 to 1.
    /// - Override on, but a stick or the gear switch out of range: RC still takes
    ///   over, and asks for zero speed and straight wheels. The C++ did a safe stop
    ///   here (`jrkSafeStop()`).
    pub fn rc_input(&self, ch: &Channels) -> Option<RcInput> {
        let usable = |index: usize| {
            ch.get(index)
                .filter(|&v| v > self.valid_above && v < self.valid_below)
        };
        let switch = usable(self.override_switch)?;
        if switch <= self.override_above {
            return Some(RcInput {
                override_switch: false,
                throttle: 0.0,
                steering: 0.0,
                brake: false,
            });
        }
        let (Some(throttle), Some(steering), Some(gear)) = (
            usable(self.throttle),
            usable(self.steering),
            usable(self.gear),
        ) else {
            return Some(RcInput {
                override_switch: true,
                throttle: 0.0,
                steering: 0.0,
                brake: false,
            });
        };
        let gear = self.gear(gear);
        Some(RcInput {
            override_switch: true,
            throttle: self.signed_throttle(throttle, gear),
            steering: self.below_centre(steering).clamp(-1.0, 1.0),
            brake: gear == Gear::Brake,
        })
    }

    /// Where the gear switch is.
    fn gear(&self, value: u16) -> Gear {
        if value < self.forward_below {
            Gear::Forward
        } else if value > self.reverse_above {
            Gear::Reverse
        } else {
            Gear::Brake
        }
    }

    /// How far a stick is below its middle: 1 at 1000, -1 at 2000.
    fn below_centre(&self, value: u16) -> f32 {
        (f32::from(self.centre) - f32::from(value)) / f32::from(self.half_travel)
    }

    /// The C++ counted the throttle stick below its middle as "go", with 1000 full
    /// (TODO(Q7): the transmitter may reverse CH3). The gear switch gives the sign.
    fn signed_throttle(&self, throttle: u16, gear: Gear) -> f32 {
        let push = self.below_centre(throttle).clamp(0.0, 1.0);
        let push = if push > self.throttle_deadband {
            push
        } else {
            0.0
        };
        match gear {
            Gear::Forward => push,
            Gear::Reverse => -push,
            // spine-core decides what the brake position does (RC_GEAR_BRAKE).
            Gear::Brake => 0.0,
        }
    }
}

/// The gear switch's three positions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Gear {
    Forward,
    Reverse,
    Brake,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::frame::CHANNELS;

    /// Channels with the override, throttle, steering and gear set; the rest at 1500.
    fn ch(override_switch: u16, throttle: u16, steering: u16, gear: u16) -> Channels {
        let mut c = [1500; CHANNELS];
        c[5] = override_switch;
        c[2] = throttle;
        c[3] = steering;
        c[4] = gear;
        Channels(c)
    }

    fn rc(c: Channels) -> Option<RcInput> {
        RcMap::default().rc_input(&c)
    }

    const ON: u16 = 2000;
    const OFF: u16 = 1000;
    const FWD: u16 = 1000;
    const BRAKE: u16 = 1500;
    const REV: u16 = 2000;

    #[test]
    fn override_off_drives_nothing() {
        let r = rc(ch(OFF, 1000, 1000, FWD)).unwrap();
        assert!(!r.override_switch);
        assert_eq!((r.throttle, r.steering), (0.0, 0.0));
        // Exactly 1500 is still off, as in the C++ (`> 1500`).
        assert!(!rc(ch(1500, 1000, 1500, FWD)).unwrap().override_switch);
        assert!(rc(ch(1501, 1000, 1500, FWD)).unwrap().override_switch);
    }

    #[test]
    fn forward_and_reverse_take_the_throttle_below_centre() {
        let fwd = rc(ch(ON, 1000, 1500, FWD)).unwrap();
        assert!(fwd.override_switch);
        assert_eq!(fwd.throttle, 1.0);
        assert_eq!(rc(ch(ON, 1250, 1500, FWD)).unwrap().throttle, 0.5);
        assert_eq!(rc(ch(ON, 1250, 1500, REV)).unwrap().throttle, -0.5);
        // Above centre is no throttle.
        assert_eq!(rc(ch(ON, 1900, 1500, FWD)).unwrap().throttle, 0.0);
    }

    #[test]
    fn the_brake_position_asks_for_zero_speed_and_says_brake() {
        let r = rc(ch(ON, 1000, 1500, BRAKE)).unwrap();
        assert_eq!((r.throttle, r.brake), (0.0, true));
        // The edges count as brake too: forward needs < 1200, reverse > 1800.
        for edge in [1200, 1800] {
            let r = rc(ch(ON, 1000, 1500, edge)).unwrap();
            assert_eq!((r.throttle, r.brake), (0.0, true), "{edge}");
        }
        // Forward and reverse are not brake; nor is the override off.
        assert!(!rc(ch(ON, 1000, 1500, FWD)).unwrap().brake);
        assert!(!rc(ch(ON, 1000, 1500, REV)).unwrap().brake);
        assert!(!rc(ch(OFF, 1000, 1500, BRAKE)).unwrap().brake);
    }

    #[test]
    fn the_throttle_deadband_is_the_cpps_5_percent() {
        // The C++ took `map(...) < -5`: 1474 and below is go, 1475 is not.
        assert_eq!(rc(ch(ON, 1475, 1500, FWD)).unwrap().throttle, 0.0);
        assert!(rc(ch(ON, 1474, 1500, FWD)).unwrap().throttle > 0.05);
    }

    #[test]
    fn steering_1000_is_plus_one_and_2000_minus_one() {
        // The C++: current_steering = map(steering, 1000, 2000, 100, -100) / 100.
        assert_eq!(rc(ch(ON, 2000, 1000, FWD)).unwrap().steering, 1.0);
        assert_eq!(rc(ch(ON, 2000, 1500, FWD)).unwrap().steering, 0.0);
        assert_eq!(rc(ch(ON, 2000, 2000, FWD)).unwrap().steering, -1.0);
    }

    #[test]
    fn past_the_end_stops_at_full_lock_and_does_not_wrap() {
        // In the C++, steering above 2000 made map() negative; cast to uint16_t and
        // clamped, that was full lock the other way.
        assert_eq!(rc(ch(ON, 2000, 2150, FWD)).unwrap().steering, -1.0);
        assert_eq!(rc(ch(ON, 2000, 900, FWD)).unwrap().steering, 1.0);
        assert_eq!(rc(ch(ON, 900, 1500, FWD)).unwrap().throttle, 1.0);
    }

    #[test]
    fn a_bad_stick_with_the_override_on_asks_for_a_stop() {
        for bad in [0, 100, 2200, 3000] {
            for c in [
                ch(ON, bad, 1500, FWD),
                ch(ON, 1000, bad, FWD),
                ch(ON, 1000, 1500, bad),
            ] {
                let r = rc(c).unwrap();
                assert!(r.override_switch, "{bad}");
                assert_eq!(
                    (r.throttle, r.steering, r.brake),
                    (0.0, 0.0, false),
                    "{bad}"
                );
            }
        }
    }

    #[test]
    fn a_bad_override_switch_is_no_usable_rc() {
        for bad in [0, 100, 2200, 3000] {
            assert_eq!(rc(ch(bad, 1000, 1500, FWD)), None, "{bad}");
        }
    }
}
