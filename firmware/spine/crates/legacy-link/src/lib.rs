//! The 2025-26 UART link, from the Motor-Pi to the ESP32 control board.
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
//! The link only goes one way: the ESP32 sends nothing back on it.
#![no_std]

mod frame;
mod parser;
mod targets;

pub use frame::{Frame, FrameError, BAUD, FRAME_LEN};
pub use parser::Parser;
pub use targets::{Targets, Throttle, BRAKE_FULL, BRAKE_RELEASED, DAC_CAP, STEER_CENTRE};
