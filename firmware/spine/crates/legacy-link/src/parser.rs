//! Finding frames in the byte stream, the way the C++ did.

use crate::frame::{Frame, FrameError, FRAME_LEN};

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
