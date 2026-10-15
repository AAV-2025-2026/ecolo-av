//! Where the computer's commands come from: one trait, two links.
//!
//! | Link | Wire | Commands | Reports back |
//! |---|---|---|---|
//! | [`CanLink`] | CAN, through [`Board::can_receive`] (`firmware/can/aav.dbc`) | DRIVE_CMD (a speed), ESTOP_CMD | VEHICLE_FEEDBACK, VEHICLE_STATUS |
//! | [`LegacyLink`] | the Motor-Pi's UART, 13-byte frames (`legacy-link`) | throttle, brake and steering as they are: `DirectCmd` | nothing: the link goes one way |
//!
//! [`SpineBoard`](crate::SpineBoard) takes either; the rest of the loop is the same.

use crate::board::{Board, CanFrame};
use crate::calibration::Calibration;
use embedded_io::{Read, ReadReady};
use legacy_link::{FrameError, Parser, Targets, Throttle};
use spine_core::protocol::{decode_incoming, FrameError as CanError, Incoming};
use spine_core::{DirectCmd, Inputs};

/// Limits on one tick's work, so a flood of frames or bytes can't stall the loop.
const MAX_CAN_FRAMES: usize = 32;
const MAX_UART_READS: usize = 16;

/// A source of the computer's commands, and the way back for the spine's reports.
pub trait CommandLink {
    /// Everything that arrived since the last tick, into `inputs`: `drive_cmd`,
    /// `direct_cmd`, `estop_cmd`, `bad_frame`.
    fn receive<B: Board>(&mut self, board: &mut B, inputs: &mut Inputs);

    /// Send one of the spine's reports (a CAN ID and its bytes). True if it went, or if
    /// this link has no way back; false if it should have gone and didn't.
    fn send<B: Board>(&mut self, board: &mut B, id: u16, data: &[u8]) -> bool;
}

/// CAN, through the board's CAN controller: the frames of `firmware/can/aav.dbc`.
#[derive(Debug, Clone, Copy, Default)]
pub struct CanLink;

impl CommandLink for CanLink {
    fn receive<B: Board>(&mut self, board: &mut B, inputs: &mut Inputs) {
        for _ in 0..MAX_CAN_FRAMES {
            let Some(frame) = board.can_receive() else {
                break;
            };
            match decode_incoming(frame.id(), frame.data()) {
                // A disarm in any frame this tick wins, so an arming edge isn't lost.
                Ok(Incoming::Drive(cmd)) => {
                    if inputs.drive_cmd.is_none_or(|old| old.armed) {
                        inputs.drive_cmd = Some(cmd);
                    }
                }
                // An e-stop request in any frame this tick wins over a release.
                Ok(Incoming::Estop(e)) => {
                    if inputs.estop_cmd.is_none_or(|old| !old.estop_request) {
                        inputs.estop_cmd = Some(e);
                    }
                }
                Err(CanError::UnknownId) => {} // for someone else on the bus
                Err(_) => inputs.bad_frame = true,
            }
        }
    }

    fn send<B: Board>(&mut self, board: &mut B, id: u16, data: &[u8]) -> bool {
        CanFrame::new(id, data).is_some_and(|frame| board.can_send(&frame))
    }
}

/// The 2025-26 UART link from the Motor-Pi (`legacy_uart_bridge`), byte for byte.
///
/// Each frame becomes the Jrk and DAC targets the C++ set for it (`legacy-link`), then a
/// [`DirectCmd`] in spine units, through the calibration, so the devices get the same
/// targets. What the C++ did, and what this does:
///
/// | Frame | C++ | Here |
/// |---|---|---|
/// | accel below -0.05 | brake `\|accel\| * 3500`, DAC cut | the same brake, throttle 0; a stop (the arming edge's first half) |
/// | \|speed\| under 0.03 | DAC ramps to 0, brake released | throttle 0, brake released |
/// | otherwise | DAC ramps to `\|speed\| * 700`, direction from the sign | the same code and direction |
/// | a value outside -1..1 | turned down; DAC ramps to 0, the rest stays | the same: the last command with no throttle |
/// | a bad checksum | one byte dropped | the same; a bad-frame fault bit |
///
/// The direction only changes with throttle: a stop or an idle frame keeps the last one.
pub struct LegacyLink<U> {
    uart: U,
    parser: Parser,
    cal: Calibration,
    last: Option<DirectCmd>,
}

impl<U: Read + ReadReady> LegacyLink<U> {
    /// `uart`: the Motor-Pi's serial port, at [`legacy_link::BAUD`], 8N1.
    pub fn new(uart: U, cal: Calibration) -> Self {
        LegacyLink {
            uart,
            parser: Parser::new(),
            cal,
            last: None,
        }
    }

    /// The command for one frame's targets.
    fn command(&self, t: &Targets) -> DirectCmd {
        let last_reverse = self.last.is_some_and(|c| c.reverse);
        let (throttle, reverse, stop) = match t.throttle {
            Throttle::Cut => (0.0, last_reverse, true),
            Throttle::Idle => (0.0, last_reverse, false),
            Throttle::Drive { code, reverse } => (self.cal.throttle.fraction(code), reverse, false),
        };
        DirectCmd {
            throttle,
            reverse,
            brake: self.cal.brake.fraction(t.brake),
            steering_angle: self.cal.steering.angle(t.steering),
            stop,
        }
    }

    fn take(&mut self, result: Result<legacy_link::Frame, FrameError>, inputs: &mut Inputs) {
        let cmd = match result {
            Ok(frame) => self.command(&frame.targets()),
            Err(FrameError::OutOfRange) => {
                inputs.bad_frame = true;
                // The C++: "packet rejected", the throttle ramps to 0, the rest stays.
                let Some(last) = self.last else {
                    return;
                };
                DirectCmd {
                    throttle: 0.0,
                    ..last
                }
            }
            Err(FrameError::Checksum) => {
                inputs.bad_frame = true;
                return;
            }
        };
        self.last = Some(cmd);
        // A stop in any frame this tick wins, so an arming edge isn't lost.
        if inputs.direct_cmd.is_none_or(|old| !old.stop) {
            inputs.direct_cmd = Some(cmd);
        }
    }
}

impl<U: Read + ReadReady> CommandLink for LegacyLink<U> {
    fn receive<B: Board>(&mut self, _board: &mut B, inputs: &mut Inputs) {
        let mut buf = [0; 64];
        for _ in 0..MAX_UART_READS {
            if !matches!(self.uart.read_ready(), Ok(true)) {
                break;
            }
            match self.uart.read(&mut buf) {
                Ok(n) if n > 0 => {
                    for &byte in &buf[..n] {
                        if let Some(result) = self.parser.push(byte) {
                            self.take(result, inputs);
                        }
                    }
                }
                _ => break,
            }
        }
    }

    /// The link goes one way: nothing to send, and nothing lost.
    fn send<B: Board>(&mut self, _board: &mut B, _id: u16, _data: &[u8]) -> bool {
        true
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use crate::rig::{FakeBoard, FakeUart};
    use legacy_link::Frame;

    fn frame(steering: f32, speed: f32, accel: f32) -> [u8; 13] {
        Frame {
            steering,
            speed,
            accel,
        }
        .encode()
    }

    fn receive(link: &mut LegacyLink<FakeUart>, bytes: &[u8]) -> Inputs {
        link.uart.0.borrow_mut().extend(bytes.iter().copied());
        let mut inputs = Inputs::default();
        link.receive(&mut FakeBoard::new(), &mut inputs);
        inputs
    }

    fn link() -> LegacyLink<FakeUart> {
        LegacyLink::new(FakeUart::default(), Calibration::TODAY)
    }

    /// The devices' targets for a command, through today's calibration.
    fn targets(cmd: &DirectCmd) -> (u16, u16, u16) {
        let cal = Calibration::TODAY;
        (
            cal.steering.target(cmd.steering_angle),
            cal.brake.target(cmd.brake),
            cal.throttle.code(cmd.throttle),
        )
    }

    #[test]
    fn a_frame_gives_the_cpp_targets_back() {
        let mut l = link();
        let cases = [
            ((0.5, 0.5, 0.0), (2725, 400, 350)),
            ((-0.5, -1.0, 0.0), (975, 400, 700)),
            ((-1.0, 0.0, -1.0), (400, 3500, 0)),
            ((0.123, 0.0, -0.3), (2140, 1050, 0)),
        ];
        for ((s, v, a), want) in cases {
            let cmd = receive(&mut l, &frame(s, v, a)).direct_cmd.unwrap();
            assert_eq!(targets(&cmd), want, "{s} {v} {a}");
        }
    }

    #[test]
    fn a_brake_frame_is_a_stop_and_keeps_the_direction() {
        let mut l = link();
        let cmd = receive(&mut l, &frame(0.0, -0.5, 0.0)).direct_cmd.unwrap();
        assert!(cmd.reverse && !cmd.stop);
        let cmd = receive(&mut l, &frame(0.0, 0.5, -1.0)).direct_cmd.unwrap();
        assert!(cmd.stop && cmd.reverse && cmd.throttle == 0.0);
        let cmd = receive(&mut l, &frame(0.0, 0.0, 0.0)).direct_cmd.unwrap();
        assert!(!cmd.stop && cmd.reverse && cmd.throttle == 0.0); // idle
    }

    #[test]
    fn a_stop_wins_within_a_tick() {
        let mut l = link();
        let both = [frame(0.0, 0.0, -1.0), frame(0.0, 0.5, 0.0)].concat();
        assert!(receive(&mut l, &both).direct_cmd.unwrap().stop);
        let both = [frame(0.0, 0.5, 0.0), frame(0.0, 0.4, 0.0)].concat();
        let cmd = receive(&mut l, &both).direct_cmd.unwrap();
        assert_eq!(targets(&cmd).2, 280); // the latest
    }

    #[test]
    fn a_frame_out_of_range_cuts_the_throttle_and_keeps_the_rest() {
        let mut l = link();
        receive(&mut l, &frame(0.5, 0.5, 0.0));
        let mut bad = [0u8; 13];
        bad[..4].copy_from_slice(&2.0f32.to_le_bytes());
        bad[12] = bad[..12].iter().fold(0u8, |s, &b| s.wrapping_add(b));
        let inputs = receive(&mut l, &bad);
        assert!(inputs.bad_frame);
        assert_eq!(targets(&inputs.direct_cmd.unwrap()), (2725, 400, 0));
        // With nothing before it, nothing.
        assert_eq!(receive(&mut link(), &bad).direct_cmd, None);
    }

    #[test]
    fn noise_is_a_bad_frame_and_the_next_frame_still_comes() {
        let mut l = link();
        let noisy = [&[0x01, 0x02][..], &frame(0.0, 0.25, 0.0)].concat();
        let inputs = receive(&mut l, &noisy);
        assert!(inputs.bad_frame);
        assert_eq!(targets(&inputs.direct_cmd.unwrap()).2, 175);
    }

    #[test]
    fn nothing_goes_back() {
        assert!(link().send(&mut FakeBoard::new(), 0x181, &[0; 8]));
    }
}
