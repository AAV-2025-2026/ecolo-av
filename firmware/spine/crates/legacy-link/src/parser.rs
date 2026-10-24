//! Finding frames in the byte stream: version 1 the way the C++ did, version 2 by its
//! sync byte.

use crate::frame::{Frame, FrameError, FRAME_LEN};
use crate::v2::{FrameV2, FRAME_V2_LEN, SYNC};

/// Bytes in, frames out. It keeps up to 13 bytes; when the 13th arrives it checks the
/// sum. A match is a frame, and the buffer starts again. A mismatch drops the oldest byte
/// and waits for one more: the C++'s `memmove(buf, buf + 1, 12); idx = 12;`.
#[derive(Debug, Clone, Default)]
pub struct Parser {
    buf: [u8; FRAME_LEN],
    len: usize,
}

impl Parser {
    pub const fn new() -> Self {
        Parser {
            buf: [0; FRAME_LEN],
            len: 0,
        }
    }

    /// One byte. Returns a frame, a frame turned down, or nothing yet.
    ///
    /// A checksum mismatch is `Err(FrameError::Checksum)`: one for each byte dropped
    /// while the parser finds its way back into step.
    pub fn push(&mut self, byte: u8) -> Option<Result<Frame, FrameError>> {
        self.buf[self.len] = byte;
        self.len += 1;
        if self.len < FRAME_LEN {
            return None;
        }
        match Frame::decode(&self.buf) {
            Ok(frame) => {
                self.len = 0;
                Some(frame.check())
            }
            Err(e) => {
                self.buf.copy_within(1.., 0);
                self.len = FRAME_LEN - 1;
                Some(Err(e))
            }
        }
    }
}

/// Bytes in, version 2 frames out. It waits for the sync byte (0xA5), then keeps 17
/// bytes and checks the CRC. A frame that fails is dropped, and the parser starts again
/// at the next 0xA5 inside it, so a frame that follows straight after is still found.
#[derive(Debug, Clone, Default)]
pub struct ParserV2 {
    buf: [u8; FRAME_V2_LEN],
    len: usize,
}

impl ParserV2 {
    pub const fn new() -> Self {
        ParserV2 {
            buf: [0; FRAME_V2_LEN],
            len: 0,
        }
    }

    /// One byte. Returns a frame, a frame turned down, or nothing yet.
    ///
    /// A byte outside a frame that isn't 0xA5 is `Err(FrameError::Sync)`. A frame whose
    /// CRC, version or flags fail is one error: `Checksum`, `Version` or `Flags`.
    pub fn push(&mut self, byte: u8) -> Option<Result<FrameV2, FrameError>> {
        if self.len == 0 && byte != SYNC {
            return Some(Err(FrameError::Sync));
        }
        self.buf[self.len] = byte;
        self.len += 1;
        if self.len < FRAME_V2_LEN {
            return None;
        }
        let result = FrameV2::decode(&self.buf);
        // Good or bad, these bytes are done with; a bad frame may hold the next one's start.
        let next = if result.is_ok() {
            FRAME_V2_LEN
        } else {
            self.buf[1..]
                .iter()
                .position(|&b| b == SYNC)
                .map_or(FRAME_V2_LEN, |at| at + 1)
        };
        self.buf.copy_within(next.., 0);
        self.len = FRAME_V2_LEN - next;
        Some(result)
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec::Vec;

    fn frame(steering: f32) -> Frame {
        Frame {
            steering,
            speed: 0.25,
            accel: 0.0,
        }
    }

    /// The frames found, and how many results were errors.
    fn feed(p: &mut Parser, bytes: &[u8]) -> (Vec<Frame>, usize) {
        let results: Vec<_> = bytes.iter().filter_map(|&b| p.push(b)).collect();
        let errors = results.iter().filter(|r| r.is_err()).count();
        (results.into_iter().flatten().collect(), errors)
    }

    #[test]
    fn frames_back_to_back() {
        let mut p = Parser::new();
        let stream: Vec<u8> = [frame(0.1).encode(), frame(-0.2).encode()].concat();
        assert_eq!(
            feed(&mut p, &stream),
            (std::vec![frame(0.1), frame(-0.2)], 0)
        );
    }

    #[test]
    fn it_finds_its_way_back_after_noise() {
        let mut p = Parser::new();
        let stream: Vec<u8> = [&[0xAA, 0x55, 0x01][..], &frame(0.3).encode()].concat();
        // One error for each byte dropped.
        assert_eq!(feed(&mut p, &stream), (std::vec![frame(0.3)], 3));
    }

    #[test]
    fn a_frame_out_of_range_is_reported() {
        let mut p = Parser::new();
        let bad = Frame {
            steering: 1.5,
            speed: 0.0,
            accel: 0.0,
        };
        let results: Vec<_> = bad.encode().iter().filter_map(|&b| p.push(b)).collect();
        assert_eq!(results, [Err(FrameError::OutOfRange)]);
        // And the next frame is found straight after it.
        assert_eq!(feed(&mut p, &frame(0.0).encode()).0, [frame(0.0)]);
    }
}

#[cfg(test)]
mod v2_tests {
    extern crate std;

    use super::*;
    use crate::v2::Flags;
    use std::vec::Vec;

    fn frame(counter: u8) -> FrameV2 {
        FrameV2 {
            values: Frame {
                steering: 0.1,
                speed: 0.25,
                accel: 0.0,
            },
            counter,
            flags: Flags {
                armed: true,
                estop: false,
            },
        }
    }

    /// The frames found, and the errors, in order.
    fn feed(p: &mut ParserV2, bytes: &[u8]) -> (Vec<FrameV2>, Vec<FrameError>) {
        let results: Vec<_> = bytes.iter().filter_map(|&b| p.push(b)).collect();
        let errors = results.iter().filter_map(|r| r.err()).collect();
        (results.into_iter().flatten().collect(), errors)
    }

    #[test]
    fn frames_back_to_back() {
        let mut p = ParserV2::new();
        let stream = [frame(1).encode(), frame(2).encode()].concat();
        assert_eq!(
            feed(&mut p, &stream),
            (std::vec![frame(1), frame(2)], std::vec![])
        );
    }

    #[test]
    fn noise_before_a_frame_is_skipped() {
        let mut p = ParserV2::new();
        let stream = [&[0x00, 0x13, 0xFF][..], &frame(3).encode()].concat();
        let (frames, errors) = feed(&mut p, &stream);
        assert_eq!(frames, [frame(3)]);
        assert_eq!(errors, [FrameError::Sync; 3]);
    }

    #[test]
    fn a_bad_crc_is_one_error_and_the_next_frame_still_comes() {
        let mut p = ParserV2::new();
        let mut bad = frame(4).encode();
        bad[16] ^= 0xFF;
        let stream = [bad, frame(5).encode()].concat();
        assert_eq!(
            feed(&mut p, &stream),
            (std::vec![frame(5)], std::vec![FrameError::Checksum])
        );
    }

    #[test]
    fn a_frame_cut_short_does_not_hide_the_next() {
        // The Pi rebooted mid-frame: 9 bytes, then whole frames. The 17 bytes from the
        // first 0xA5 fail their CRC; the parser starts again at the next frame's 0xA5.
        let mut p = ParserV2::new();
        let stream = [
            &frame(6).encode()[..9],
            &frame(8).encode(),
            &frame(9).encode(),
        ]
        .concat();
        assert_eq!(
            feed(&mut p, &stream),
            (
                std::vec![frame(8), frame(9)],
                std::vec![FrameError::Checksum]
            )
        );
    }

    #[test]
    fn a_counter_of_0xa5_is_not_mistaken_for_a_start() {
        let mut p = ParserV2::new();
        let stream = [frame(0xA5).encode(), frame(0xA6).encode()].concat();
        assert_eq!(feed(&mut p, &stream).0, [frame(0xA5), frame(0xA6)]);
    }

    #[test]
    fn a_version_1_stream_never_gives_a_frame() {
        let mut p = ParserV2::new();
        let v1: Vec<u8> = (0..20)
            .flat_map(|i| {
                Frame {
                    steering: 0.0,
                    speed: i as f32 / 20.0,
                    accel: 0.0,
                }
                .encode()
            })
            .collect();
        assert!(feed(&mut p, &v1).0.is_empty());
    }
}
