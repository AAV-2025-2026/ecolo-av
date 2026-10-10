//! The FlySky iBUS protocol, from the car's RC receiver (an FS-iA6B).
//!
//! The receiver sends a 32-byte frame about every 7 ms, at 115200 baud: the header
//! `0x20 0x40`, 14 channels as little-endian `u16`, then a checksum. Sticks and
//! switches read 1000 to 2000.
//!
//! | Module | Does |
//! |---|---|
//! | `frame` | one frame: [`decode`], [`encode`], [`checksum`], [`Channels`] |
//! | `parser` | [`Parser`]: finds frames one byte at a time, and resyncs after noise |
//! | `receiver` | [`Receiver`]: the latest frame, or `None` once the receiver goes silent |
//! | [`rc`] | [`RcMap`]: channels to `spine_core::RcInput` |
//!
//! Plain `no_std` Rust with no hardware access: the board reads the UART and feeds
//! the bytes in, so the same code runs on any board and in `cargo test`.
//!
//! ```
//! use ibus::{encode, Channels, RcMap, Receiver};
//!
//! let mut receiver = Receiver::new(100);
//! let mut sticks = [1500; 14];
//! sticks[5] = 2000; // override switch on
//! for byte in encode(&Channels(sticks)) {
//!     receiver.push(byte, 0);
//! }
//! let rc = receiver.channels(0).and_then(|c| RcMap::default().rc_input(&c));
//! assert!(rc.unwrap().override_switch);
//! ```
#![no_std]

mod frame;
mod parser;
pub mod rc;
mod receiver;

pub use frame::{checksum, decode, encode, Channels, BAUD, CHANNELS, FRAME_LEN, HEADER};
pub use parser::Parser;
pub use rc::RcMap;
pub use receiver::Receiver;
