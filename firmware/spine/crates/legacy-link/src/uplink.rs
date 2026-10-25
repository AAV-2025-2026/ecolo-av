//! The uplink (TODO 50, TODO 48): the ESP32's status, back to the Motor-Pi on TX1.
//!
//! ```text
//!  byte  0     1        2     3         4     5     6       7      8..9
//!        0xA5  version  kind  sequence  echo  mode  switch  flags  faults
//!  byte  10..13         14..17         18..21        22..25     26..29       30..33       34
//!        steering (rad) brake (0..1)   throttle out  brake out  RC throttle  RC steering  CRC-8
//! ```
//!
//! The same sync byte, version and CRC-8 as the downlink ([`FrameV2`](crate::FrameV2)),
//! the CRC over bytes 1..33. Floats are little-endian `f32`. A position the ESP32 can't
//! measure (the Jrk has no feedback set up, or its read failed) is NaN on the wire, and
//! its flag bit is clear.

use crate::frame::FrameError;
use crate::v2::{crc8, SYNC, VERSION};

/// Bytes in an uplink frame.
pub const UPLINK_LEN: usize = 35;
/// Byte 2 of a status frame. The only kind so far; a new kind gets a new number.
pub const KIND_STATUS: u8 = 1;

/// Who drives the actuators (byte 5): the same numbers as `VehicleStatus.mode`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DriveMode {
    /// Nobody: stopped, idle or latched (`MODE_MANUAL`).
    Stopped,
    /// The RC transmitter, straight from its sticks on the ESP32 (`MODE_RC`).
    RcDirect,
    /// The computer's frames: ROS drives, or a person through ROS (`MODE_COMPUTER`).
    Computer,
}

impl DriveMode {
    fn to_byte(self) -> u8 {
        match self {
            DriveMode::Stopped => 0,
            DriveMode::RcDirect => 1,
            DriveMode::Computer => 2,
        }
    }

    fn from_byte(byte: u8) -> Result<Self, FrameError> {
        match byte {
            0 => Ok(DriveMode::Stopped),
            1 => Ok(DriveMode::RcDirect),
            2 => Ok(DriveMode::Computer),
            _ => Err(FrameError::Field),
        }
    }
}

/// Where the transmitter's mode switch is (byte 6), as the ESP32 read it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModeSwitch {
    /// No usable RC signal: the receiver is silent, or the switch reads out of range.
    NoSignal,
    /// The computer drives.
    Computer,
    /// A person drives with the RC, through ROS: the ESP32 sends the sticks up and
    /// takes the computer's frames.
    RcViaRos,
    /// A person drives with the RC, straight from the ESP32 (the fallback).
    RcDirect,
}

impl ModeSwitch {
    fn to_byte(self) -> u8 {
        match self {
            ModeSwitch::NoSignal => 0,
            ModeSwitch::Computer => 1,
            ModeSwitch::RcViaRos => 2,
            ModeSwitch::RcDirect => 3,
        }
    }

    fn from_byte(byte: u8) -> Result<Self, FrameError> {
        match byte {
            0 => Ok(ModeSwitch::NoSignal),
            1 => Ok(ModeSwitch::Computer),
            2 => Ok(ModeSwitch::RcViaRos),
            3 => Ok(ModeSwitch::RcDirect),
            _ => Err(FrameError::Field),
        }
    }
}

/// The RC sticks, as the ESP32 reads them (`ibus::RcMap`): what RC direct would drive.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Sticks {
    /// -1..1, positive forward: the throttle stick, signed by the gear switch.
    pub throttle: f32,
    /// -1..1, positive left.
    pub steering: f32,
    /// The gear switch is on brake.
    pub brake: bool,
}

/// One uplink status frame.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Uplink {
    /// +1 a frame, 255 then 0: a gap means frames were lost.
    pub sequence: u8,
    /// The last Orin counter the ESP32 took from a version 2 frame; none before the
    /// first, and never with version 1 frames.
    pub echo: Option<u8>,
    pub mode: DriveMode,
    pub switch: ModeSwitch,
    /// The spine accepts the computer's commands.
    pub armed: bool,
    /// Any stop: an e-stop, a timeout, a fault, latched.
    pub estop: bool,
    /// The spine's fault bits (`VehicleStatus.FAULT_*`).
    pub faults: u16,
    /// The steering Jrk's position (rad, positive left), if it has feedback.
    pub steering: Option<f32>,
    /// The brake Jrk's position (0 released .. 1 full), if it has feedback.
    pub brake_position: Option<f32>,
    /// What the ESP32 drives the throttle (0..1) and the brake (0..1) with.
    pub throttle_out: f32,
    pub brake_out: f32,
    /// The sticks; all 0 with [`ModeSwitch::NoSignal`].
    pub sticks: Sticks,
}

/// Byte 7.
mod flag {
    pub const ARMED: u8 = 1 << 0;
    pub const ESTOP: u8 = 1 << 1;
    pub const ECHO: u8 = 1 << 2;
    pub const STEERING: u8 = 1 << 3;
    pub const BRAKE_POSITION: u8 = 1 << 4;
    pub const STICK_BRAKE: u8 = 1 << 5;
    pub const ALL: u8 = ARMED | ESTOP | ECHO | STEERING | BRAKE_POSITION | STICK_BRAKE;
}

impl Uplink {
    /// The 35 bytes.
    pub fn encode(&self) -> [u8; UPLINK_LEN] {
        let bit = |on: bool, mask: u8| if on { mask } else { 0 };
        let mut b = [0; UPLINK_LEN];
        b[0] = SYNC;
        b[1] = VERSION;
        b[2] = KIND_STATUS;
        b[3] = self.sequence;
        b[4] = self.echo.unwrap_or(0);
        b[5] = self.mode.to_byte();
        b[6] = self.switch.to_byte();
        b[7] = bit(self.armed, flag::ARMED)
            | bit(self.estop, flag::ESTOP)
            | bit(self.echo.is_some(), flag::ECHO)
            | bit(self.steering.is_some(), flag::STEERING)
            | bit(self.brake_position.is_some(), flag::BRAKE_POSITION)
            | bit(self.sticks.brake, flag::STICK_BRAKE);
        b[8..10].copy_from_slice(&self.faults.to_le_bytes());
        let values = [
            self.steering.unwrap_or(f32::NAN),
            self.brake_position.unwrap_or(f32::NAN),
            self.throttle_out,
            self.brake_out,
            self.sticks.throttle,
            self.sticks.steering,
        ];
        for (chunk, value) in b[10..34].chunks_exact_mut(4).zip(values) {
            chunk.copy_from_slice(&value.to_le_bytes());
        }
        b[34] = crc8(&b[1..34]);
        b
    }

    /// A frame from 35 bytes: the sync byte, the CRC, then the version, the kind and
    /// each field.
    pub fn decode(b: &[u8; UPLINK_LEN]) -> Result<Uplink, FrameError> {
        if b[0] != SYNC {
            return Err(FrameError::Sync);
        }
        if crc8(&b[1..34]) != b[34] {
            return Err(FrameError::Checksum);
        }
        if b[1] != VERSION || b[2] != KIND_STATUS {
            return Err(FrameError::Version);
        }
        let flags = b[7];
        if flags & !flag::ALL != 0 {
            return Err(FrameError::Flags);
        }
        let on = |mask: u8| flags & mask != 0;
        let value = |at: usize| {
            let mut four = [0; 4];
            four.copy_from_slice(&b[at..at + 4]);
            f32::from_le_bytes(four)
        };
        Ok(Uplink {
            sequence: b[3],
            echo: on(flag::ECHO).then_some(b[4]),
            mode: DriveMode::from_byte(b[5])?,
            switch: ModeSwitch::from_byte(b[6])?,
            armed: on(flag::ARMED),
            estop: on(flag::ESTOP),
            faults: u16::from_le_bytes([b[8], b[9]]),
            steering: on(flag::STEERING).then(|| value(10)),
            brake_position: on(flag::BRAKE_POSITION).then(|| value(14)),
            throttle_out: value(18),
            brake_out: value(22),
            sticks: Sticks {
                throttle: value(26),
                steering: value(30),
                brake: on(flag::STICK_BRAKE),
            },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn status() -> Uplink {
        Uplink {
            sequence: 41,
            echo: Some(200),
            mode: DriveMode::Computer,
            switch: ModeSwitch::RcViaRos,
            armed: true,
            estop: false,
            faults: 0x0102,
            steering: Some(0.125),
            brake_position: None,
            throttle_out: 0.25,
            brake_out: 0.0,
            sticks: Sticks {
                throttle: 0.5,
                steering: -0.75,
                brake: false,
            },
        }
    }

    #[test]
    fn round_trip() {
        let u = status();
        let b = u.encode();
        assert_eq!((b[0], b[1], b[2], b[3], b[4]), (0xA5, 2, 1, 41, 200));
        assert_eq!((b[5], b[6], b[7]), (2, 2, 0b0000_1101));
        assert_eq!((b[8], b[9]), (0x02, 0x01));
        assert!(f32::from_le_bytes([b[14], b[15], b[16], b[17]]).is_nan());
        assert_eq!(Uplink::decode(&b), Ok(u));
        let quiet = Uplink {
            echo: None,
            mode: DriveMode::Stopped,
            switch: ModeSwitch::NoSignal,
            steering: None,
            sticks: Sticks::default(),
            ..u
        };
        assert_eq!(Uplink::decode(&quiet.encode()), Ok(quiet));
    }

    #[test]
    fn every_single_bit_error_is_caught() {
        let b = status().encode();
        for bit in 8..UPLINK_LEN * 8 {
            let mut bad = b;
            bad[bit / 8] ^= 0x80 >> (bit % 8);
            assert!(Uplink::decode(&bad).is_err(), "bit {bit}");
        }
    }

    #[test]
    fn unknown_kinds_modes_and_flags_are_turned_down() {
        let fix = |mut b: [u8; UPLINK_LEN]| {
            b[34] = crc8(&b[1..34]);
            b
        };
        let mut b = status().encode();
        b[2] = 2;
        assert_eq!(Uplink::decode(&fix(b)), Err(FrameError::Version));
        let mut b = status().encode();
        b[5] = 3;
        assert_eq!(Uplink::decode(&fix(b)), Err(FrameError::Field));
        let mut b = status().encode();
        b[6] = 4;
        assert_eq!(Uplink::decode(&fix(b)), Err(FrameError::Field));
        let mut b = status().encode();
        b[7] |= 0x40;
        assert_eq!(Uplink::decode(&fix(b)), Err(FrameError::Flags));
    }
}
