//! The UART link from the Motor-Pi to the ESP32 control board: the 2025-26 frame
//! (version 1), and version 2 with the Orin's heartbeat (TODO 50).
//!
//! The ROS side is `src/backends/aav_legacy/aav_legacy/legacy_protocol.py`. The firmware
//! side was `firmware/legacy/aav_umod_esp32/src/modules/ros2_handler/ros2_handler.cpp`;
//! this crate does what it did, so the Rust board is a drop-in replacement.
//!
//! | Part | Here | The C++ |
//! |---|---|---|
//! | 13 bytes: three little-endian `f32`, then a sum checksum | [`Frame`] | `memcpy`, `calc += buf[j]` |
//! | resync: on a bad checksum, drop one byte and try again | [`Parser`] | `memmove(buf, buf + 1, 12)` |
//! | each value within -1..1, or the frame is turned down | [`Frame::check`] | `fabsf(...) <= 1.0f` |
//! | the Jrk and DAC targets for a frame | [`Frame::targets`] | the rest of `handleROS2Messages()` |
//!
//! ```text
//!  byte  0..3      4..7     8..11    12
//!       steering  speed    accel    sum(bytes 0..11) & 0xFF
//! ```
//!
//! Version 2 ([`FrameV2`], [`ParserV2`]) keeps the three values and adds a sync byte, a
//! version, the Orin's counter, the armed and e-stop flags, and a CRC-8:
//!
//! ```text
//!  byte  0     1   2..5      6..9   10..13  14       15     16
//!        0xA5  2   steering  speed  accel   counter  flags  CRC-8/SAE-J1850 of 1..15
//! ```
//!
//! The link only goes one way: the ESP32 sends nothing back on it.
#![no_std]

mod frame;
mod parser;
mod targets;
mod v2;

pub use frame::{Frame, FrameError, BAUD, FRAME_LEN};
pub use parser::{Parser, ParserV2};
pub use targets::{Targets, Throttle, BRAKE_FULL, BRAKE_RELEASED, DAC_CAP, STEER_CENTRE};
pub use v2::{crc8, Flags, FrameV2, Heartbeat, FRAME_V2_LEN, SYNC, VERSION};
