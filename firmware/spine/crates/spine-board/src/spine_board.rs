//! The loop: read everything, step the spine, drive the devices, send CAN frames.
//!
//! One tick, about 100 times a second:
//!
//! | Step | Reads | Fills, in `Inputs` |
//! |---|---|---|
//! | 1 | the computer's commands, from the link: CAN, or the UART ([`CommandLink`]) | `drive_cmd` or `direct_cmd`, `estop_cmd`, `bad_frame` |
//! | 2 | the RC receiver's serial port | `rc` |
//! | 3 | the hardware e-stop, debounced | `hw_estop` |
//! | 4 | the wheel encoder's counter | `measured_speed` |
//! | 5 | the steering and brake Jrks | `measured_steering`; `driver_faults`, with last tick's write errors |
//!
//! Then `Spine::step`, then `Actuators::apply`, then VEHICLE_FEEDBACK every 20 ms
//! and VEHICLE_STATUS every 100 ms, through the link (the UART link drops them).

use crate::actuators::{Actuators, Devices};
use crate::board::Board;
use crate::calibration::Calibration;
use crate::link::{CanLink, CommandLink};
use crate::wheel::WheelSpeed;
use aav_inputs::Debouncer;
use embedded_hal::i2c::I2c;
use embedded_io::{Read, ReadReady};
use ibus::{RcMap, Receiver};
use spine_core::protocol::{VEHICLE_FEEDBACK_ID, VEHICLE_STATUS_ID};
use spine_core::{faults, Inputs, Outputs, Spine, SpineConfig};

/// VEHICLE_FEEDBACK at 50 Hz, and VEHICLE_STATUS at 10 Hz (`docs/firmware.md`).
pub const FEEDBACK_PERIOD_MS: u32 = 20;
pub const STATUS_PERIOD_MS: u32 = 100;

/// A limit on one tick's work, so a flood of bytes can't stall the loop.
const MAX_UART_READS: usize = 16;

/// The whole spine on a board: give it the board, the four devices and the RC
/// receiver's serial port, then call [`SpineBoard::tick`] about 100 times a second.
///
/// The computer's commands come through `L`: CAN by default ([`SpineBoard::new`]), or
/// another [`CommandLink`] ([`SpineBoard::with_link`]).
pub struct SpineBoard<B, I2C, U, L = CanLink> {
    board: B,
    uart: U,
    link: L,
    actuators: Actuators<I2C>,
    spine: Spine,
    rc: Receiver,
    rc_map: RcMap,
    estop: Debouncer,
    wheel: WheelSpeed,
    /// Errors from last tick's writes, and from sending CAN.
    write_faults: u16,
    can_fault: u16,
    feedback: Every,
    status: Every,
}

impl<B: Board, I2C: I2c, U: Read + ReadReady> SpineBoard<B, I2C, U, CanLink> {
    /// The spine, with the computer on CAN, through the board.
    ///
    /// `uart`: the RC receiver's serial port, set to 115200 baud, 8N1.
    pub fn new(
        board: B,
        devices: Devices<I2C>,
        uart: U,
        cal: Calibration,
        config: SpineConfig,
    ) -> Self {
        Self::with_link(board, devices, uart, CanLink, cal, config)
    }
}

impl<B: Board, I2C: I2c, U: Read + ReadReady, L: CommandLink> SpineBoard<B, I2C, U, L> {
    /// The spine, with the computer's commands through `link`.
    ///
    /// `uart`: the RC receiver's serial port, set to 115200 baud, 8N1.
    pub fn with_link(
        board: B,
        devices: Devices<I2C>,
        uart: U,
        link: L,
        cal: Calibration,
        config: SpineConfig,
    ) -> Self {
        SpineBoard {
            board,
            uart,
            link,
            actuators: Actuators::new(devices, cal),
            spine: Spine::new(config),
            rc: Receiver::new(cal.rc_timeout_ms),
            rc_map: cal.rc,
            // Starts tripped, so a reboot is safe. Trips at once; releases only
            // after reading closed for `estop_release_ms`.
            estop: Debouncer::with_times(true, 0, cal.estop_release_ms),
            wheel: WheelSpeed::new(cal.wheel.metres_per_count, cal.wheel.timeout_ms),
            write_faults: 0,
            can_fault: 0,
            feedback: Every::new(FEEDBACK_PERIOD_MS),
            status: Every::new(STATUS_PERIOD_MS),
        }
    }

    /// Power-up: throttle 0, brake on, expander set up, steering centred. Call once
    /// before the first tick. Returns the fault bits; they also go into the first
    /// tick, so a device that failed here keeps the car stopped until it is armed.
    pub fn init(&mut self) -> u16 {
        self.write_faults = self.actuators.init();
        self.write_faults
    }

    /// One pass of the loop. Returns what the spine decided.
    pub fn tick(&mut self) -> Outputs {
        let now = self.board.now_ms();
        let mut inputs = Inputs {
            now_ms: now,
            ..Inputs::default()
        };
        self.link.receive(&mut self.board, &mut inputs);
        self.read_rc(now);
        inputs.rc = self.rc.channels(now).and_then(|c| self.rc_map.rc_input(&c));
        let open = self.board.estop_open();
        self.estop.update(open, now);
        inputs.hw_estop = self.estop.level();
        let wheel = self.board.wheel();
        inputs.measured_speed = self.wheel.update(wheel, now);
        let readings = self.actuators.read();
        inputs.measured_steering = readings.steering;
        inputs.driver_faults = readings.faults | self.write_faults | self.can_fault;

        let out = self.spine.step(&inputs);
        self.write_faults = self.actuators.apply(&out, now);
        self.send_frames(now, &inputs, wheel.count, &out);
        out
    }

    /// The board, for whatever else it does (LEDs, say).
    pub fn board(&mut self) -> &mut B {
        &mut self.board
    }

    /// The command link, to read what it has seen (its stats, say).
    pub fn link(&mut self) -> &mut L {
        &mut self.link
    }

    /// The devices and their state, to read something else from them.
    pub fn actuators(&mut self) -> &mut Actuators<I2C> {
        &mut self.actuators
    }

    /// Feed the iBUS parser whatever the serial port has. A UART error loses those
    /// bytes; the parser resyncs.
    fn read_rc(&mut self, now: u32) {
        let mut buf = [0; 32];
        for _ in 0..MAX_UART_READS {
            if !matches!(self.uart.read_ready(), Ok(true)) {
                break;
            }
            match self.uart.read(&mut buf) {
                Ok(n) if n > 0 => {
                    for &byte in &buf[..n] {
                        self.rc.push(byte, now);
                    }
                }
                _ => break,
            }
        }
    }

    fn send_frames(&mut self, now: u32, inputs: &Inputs, wheel_count: i32, out: &Outputs) {
        let mut sent: Option<bool> = None;
        if self.feedback.due(now) {
            let data = self.spine.feedback_frame(
                inputs.measured_speed,
                inputs.measured_steering,
                wheel_count as u16, // the frame carries the low 16 bits
            );
            sent = Some(self.send(VEHICLE_FEEDBACK_ID, &data));
        }
        if self.status.due(now) {
            let data = self.spine.status_frame(out);
            let ok = self.send(VEHICLE_STATUS_ID, &data);
            sent = Some(sent.unwrap_or(true) && ok);
        }
        if let Some(ok) = sent {
            self.can_fault = if ok { 0 } else { faults::CAN_BUS };
        }
    }

    fn send(&mut self, id: u16, data: &[u8]) -> bool {
        self.link.send(&mut self.board, id, data)
    }
}

/// A job due every `period_ms`, on average.
#[derive(Debug, Clone, Copy)]
struct Every {
    period_ms: u32,
    next_ms: Option<u32>,
}

impl Every {
    const fn new(period_ms: u32) -> Self {
        Every {
            period_ms,
            next_ms: None,
        }
    }

    /// True if the job is due at `now_ms`; then the next one is booked.
    fn due(&mut self, now_ms: u32) -> bool {
        let next = *self.next_ms.get_or_insert(now_ms);
        if (now_ms.wrapping_sub(next) as i32) < 0 {
            return false;
        }
        let after = next.wrapping_add(self.period_ms);
        // More than a period late: start again from now, rather than catch up.
        let late = now_ms.wrapping_sub(after) as i32 >= 0;
        self.next_ms = Some(if late {
            now_ms.wrapping_add(self.period_ms)
        } else {
            after
        });
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_keeps_its_average() {
        let mut e = Every::new(20);
        let due: usize = (0..100).filter(|i| e.due(i * 10)).count();
        assert_eq!(due, 50); // every other 10 ms tick
        let mut e = Every::new(20);
        // Ticks 11 ms apart still give one every 20 ms on average.
        let due: usize = (0..200).filter(|i| e.due(i * 11)).count();
        assert!((109..=111).contains(&due), "{due}");
    }

    #[test]
    fn every_restarts_after_a_long_gap() {
        let mut e = Every::new(20);
        assert!(e.due(0));
        assert!(e.due(1000)); // late: once, not 50 times
        assert!(!e.due(1010));
        assert!(e.due(1020));
    }

    #[test]
    fn every_survives_clock_wrap() {
        let mut e = Every::new(20);
        assert!(e.due(u32::MAX - 5));
        assert!(!e.due(u32::MAX));
        assert!(e.due(14)); // 20 ms after the first
    }
}

/// The whole loop, end to end, on the test rig.
#[cfg(test)]
mod loop_tests {
    extern crate std;
    use crate::rig::{Rig, BRAKE, DAC, EXPANDER, STEER};
    use jrk_g2::command::set_target;
    use jrk_g2::ErrorFlags;
    use spine_core::faults;
    use spine_core::protocol::{
        Mode, VehicleFeedback, VehicleStatus, DRIVE_CMD_ID, VEHICLE_FEEDBACK_ID, VEHICLE_STATUS_ID,
    };
    use std::vec;

    #[test]
    fn init_cuts_the_throttle_then_brakes_then_sets_up() {
        let w = Rig::new().writes();
        assert_eq!(w[0], (DAC, vec![0x00, 0x00]));
        assert_eq!(w[1], (BRAKE, set_target(3500).to_vec()));
        assert_eq!(w[2], (EXPANDER, vec![0x04, 0x00, 0x00]));
        assert_eq!(w[3], (EXPANDER, vec![0x02, 0xFF, 0xFF]));
        assert_eq!(w[4], (EXPANDER, vec![0x06, 0x00, 0x00]));
        assert_eq!(w[5], (STEER, set_target(1950).to_vec()));
    }

    #[test]
    fn armed_frames_after_a_reboot_do_not_drive() {
        let mut rig = Rig::new();
        let out = rig.drive_for(1.0, true, 30);
        assert_eq!(out.mode, Mode::Manual);
        assert!(rig.dac_codes().iter().all(|&c| c == 0));
    }

    #[test]
    fn once_armed_the_computer_drives_and_the_throttle_ramps() {
        let mut rig = Rig::new();
        rig.arm();
        rig.clear();
        let out = rig.drive_for(1.0, true, 30);
        assert_eq!(out.mode, Mode::Computer);
        let codes = rig.dac_codes();
        assert!(*codes.last().unwrap() > 0);
        assert!(codes.windows(2).all(|w| w[1] <= w[0] + 6), "{codes:?}");
    }

    /// Arm, drive until the throttle is on, and forget the writes so far.
    fn driving() -> Rig {
        let mut rig = Rig::new();
        rig.arm();
        rig.drive_for(1.0, true, 30);
        assert!(rig.sb.actuators().throttle_code() > 0);
        rig.clear();
        rig
    }

    #[test]
    fn a_hardware_estop_cuts_the_throttle_before_the_brake() {
        let mut rig = driving();
        rig.sb.board().estop_open = true;
        rig.drive(1.0, true);
        let out = rig.tick();
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
        let throttle_off = rig.position(DAC, 0).unwrap();
        let brake_on = rig.position(BRAKE, 3500).unwrap();
        assert!(throttle_off < brake_on);
    }

    #[test]
    fn an_estop_frame_does_the_same() {
        let mut rig = driving();
        rig.drive(1.0, true);
        rig.estop_frame(true);
        let out = rig.tick();
        assert!(out.estop_active);
        assert!(rig.position(DAC, 0).unwrap() < rig.position(BRAKE, 3500).unwrap());
    }

    #[test]
    fn an_estop_request_wins_over_a_release_in_the_same_tick() {
        let mut rig = driving();
        rig.drive(1.0, true);
        rig.estop_frame(true);
        rig.estop_frame(false);
        assert_eq!(rig.tick().brake, 1.0);
    }

    #[test]
    fn a_disarm_and_an_arm_in_one_tick_still_arm() {
        let mut rig = Rig::new();
        rig.ticks(6); // the e-stop input releases
        rig.drive(0.0, false);
        rig.drive(1.0, true);
        rig.tick();
        assert_eq!(rig.drive_for(1.0, true, 3).mode, Mode::Computer);
    }

    #[test]
    fn rc_drives_without_the_computer() {
        let mut rig = Rig::new();
        rig.ticks(6);
        let mut out = rig.tick();
        for _ in 0..30 {
            rig.rc(true, 1000, 1500, 1000); // override on, full throttle, forward
            out = rig.tick();
        }
        assert_eq!(out.mode, Mode::Rc);
        assert!(out.throttle > 0.0);
        assert!(rig.sb.actuators().throttle_code() > 0);
    }

    #[test]
    fn a_silent_receiver_stops_rc() {
        let mut rig = Rig::new();
        rig.ticks(6);
        for _ in 0..30 {
            rig.rc(true, 1000, 1500, 1000);
            rig.tick();
        }
        let out = rig.ticks(15); // 150 ms without a frame
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
        assert_ne!(out.faults & faults::RC_SIGNAL_LOST, 0);
        assert_eq!(rig.sb.actuators().throttle_code(), 0);
    }

    #[test]
    fn feedback_every_20_ms_and_status_every_100_ms() {
        let mut rig = Rig::new();
        rig.sb.board().wheel.count = 70_000;
        rig.bus.borrow_mut().steering_feedback = 2260; // 0.1 rad left
        rig.ticks(100); // 1 s
        let sent = &rig.sb.board().sent;
        let feedback: std::vec::Vec<_> = sent
            .iter()
            .filter(|f| f.id() == VEHICLE_FEEDBACK_ID)
            .collect();
        let status = sent.iter().filter(|f| f.id() == VEHICLE_STATUS_ID).count();
        assert_eq!((feedback.len(), status), (50, 10));
        let last = VehicleFeedback::decode(feedback[49].data()).unwrap();
        assert_eq!(last.wheel_ticks, 70_000_u32 as u16);
        assert!((last.measured_steering_angle - 0.1).abs() < 0.01);
        let status = sent.iter().rfind(|f| f.id() == VEHICLE_STATUS_ID).unwrap();
        assert!(VehicleStatus::decode(status.data()).is_ok());
    }

    #[test]
    fn a_failed_send_is_a_can_bus_fault() {
        let mut rig = Rig::new();
        rig.sb.board().can_ok = false;
        rig.tick();
        assert_ne!(rig.tick().faults & faults::CAN_BUS, 0);
        rig.sb.board().can_ok = true;
        rig.ticks(3); // the next sends work
        assert_eq!(rig.tick().faults & faults::CAN_BUS, 0);
    }

    #[test]
    fn a_dead_dac_stops_the_car() {
        let mut rig = driving();
        rig.bus.borrow_mut().failing.push(DAC);
        rig.drive(1.0, true);
        rig.tick(); // the write fails
        rig.drive(1.0, true);
        let out = rig.tick();
        assert_ne!(out.faults & faults::THROTTLE_DAC, 0);
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
    }

    #[test]
    fn a_jrk_error_stops_the_car() {
        let mut rig = driving();
        rig.bus
            .borrow_mut()
            .jrk_errors
            .push((BRAKE, ErrorFlags::NO_POWER));
        rig.drive(1.0, true);
        let out = rig.tick();
        assert_ne!(out.faults & faults::BRAKE_DRIVER, 0);
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
    }

    #[test]
    fn bad_frames_are_reported_and_others_frames_ignored() {
        let mut rig = Rig::new();
        rig.can(0x300, &[1, 2, 3]); // someone else's frame
        assert_eq!(rig.tick().faults & faults::BAD_CHECKSUM, 0);
        rig.can(DRIVE_CMD_ID, &[0; 8]); // the CRC is wrong
        assert_ne!(rig.tick().faults & faults::BAD_CHECKSUM, 0);
    }
}

/// The loop with the 2025-26 UART link instead of CAN, and no wheel speed: today's ESP32
/// control board, as `boards/esp32-umod` builds it.
#[cfg(test)]
mod legacy_loop_tests {
    extern crate std;
    use super::SpineBoard;
    use crate::actuators::Devices;
    use crate::calibration::Calibration;
    use crate::link::{FrameVersion, LegacyLink};
    use crate::rig::{BusState, FakeBoard, FakeBus, FakeUart, BRAKE, DAC, STEER};
    use core::cell::RefCell;
    use jrk_g2::command::set_target;
    use legacy_link::{Flags, Frame, FrameV2};
    use spine_core::protocol::Mode;
    use spine_core::{faults, Outputs, SpeedFeedback, SpineConfig};
    use std::rc::Rc;
    use std::vec::Vec;

    struct LegacyRig {
        sb: SpineBoard<FakeBoard, FakeBus, FakeUart, LegacyLink<FakeUart>>,
        bus: Rc<RefCell<BusState>>,
        motor_pi: FakeUart,
        receiver: FakeUart,
    }

    impl LegacyRig {
        fn new() -> Self {
            Self::with_version(FrameVersion::V1)
        }

        fn with_version(version: FrameVersion) -> Self {
            let bus = FakeBus::default();
            let (motor_pi, receiver) = (FakeUart::default(), FakeUart::default());
            let cal = Calibration::TODAY;
            let devices = Devices::new(bus.clone(), bus.clone(), bus.clone(), bus.clone(), &cal);
            let config = SpineConfig {
                speed_feedback: SpeedFeedback::None {
                    full_throttle_speed: 3.0,
                },
                ..SpineConfig::default()
            };
            let link = LegacyLink::new(motor_pi.clone(), cal, version);
            let board = FakeBoard::new();
            let mut sb = SpineBoard::with_link(board, devices, receiver.clone(), link, cal, config);
            sb.init();
            LegacyRig {
                sb,
                bus: bus.0,
                motor_pi,
                receiver,
            }
        }

        /// One frame from the Motor-Pi, then a 20 ms tick: the bridge's 50 Hz.
        fn frame(&mut self, steering: f32, speed: f32, accel: f32) -> Outputs {
            let bytes = Frame {
                steering,
                speed,
                accel,
            }
            .encode();
            self.motor_pi.0.borrow_mut().extend(bytes);
            self.sb.board().now += 20;
            self.sb.tick()
        }

        /// One version 2 frame, then a 20 ms tick.
        fn frame_v2(&mut self, speed: f32, accel: f32, counter: u8, armed: bool) -> Outputs {
            let bytes = FrameV2 {
                values: Frame {
                    steering: 0.0,
                    speed,
                    accel,
                },
                counter,
                flags: Flags {
                    armed,
                    estop: false,
                },
            }
            .encode();
            self.motor_pi.0.borrow_mut().extend(bytes);
            self.sb.board().now += 20;
            self.sb.tick()
        }

        /// `n` version 2 frames, the counter moving by one each (from `*counter`).
        fn moving(&mut self, n: usize, speed: f32, accel: f32, counter: &mut u8) -> Outputs {
            (0..n)
                .map(|_| {
                    *counter = counter.wrapping_add(1);
                    self.frame_v2(speed, accel, *counter, true)
                })
                .last()
                .unwrap()
        }

        fn frames(&mut self, n: usize, steering: f32, speed: f32, accel: f32) -> Outputs {
            (0..n)
                .map(|_| self.frame(steering, speed, accel))
                .last()
                .unwrap()
        }

        /// Stop frames past the e-stop input's release (50 ms after boot): the arming
        /// edge's first half. The bridge sends them whenever ego is stale.
        fn arm(&mut self) {
            self.frames(5, 0.0, 0.0, -1.0);
        }

        /// The latest bytes written to a device.
        fn last(&self, address: u8) -> Option<Vec<u8>> {
            let state = self.bus.borrow();
            let latest = state.writes.iter().rev().find(|w| w.0 == address);
            latest.map(|w| w.1.clone())
        }

        fn dac(&self) -> u16 {
            self.last(DAC)
                .map_or(0, |w| ad5311::decode([w[0], w[1]]).code)
        }
    }

    #[test]
    fn drive_frames_after_a_reboot_do_not_drive_until_a_stop_frame() {
        let mut rig = LegacyRig::new();
        let out = rig.frames(10, 0.0, 0.5, 0.0);
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(rig.dac(), 0);
        // The bridge sends stop frames whenever ego is stale, so this comes first anyway.
        rig.arm();
        assert_eq!(rig.last(BRAKE), Some(set_target(3500).to_vec()));
        let out = rig.frames(100, 0.0, 0.5, 0.0);
        assert_eq!(out.mode, Mode::Computer);
        // The C++'s code for speed 0.5, reached through the ramp; the brake let go.
        assert_eq!(rig.dac(), 350);
        assert_eq!(rig.last(BRAKE), Some(set_target(400).to_vec()));
    }

    #[test]
    fn the_steering_reaches_the_cpp_target() {
        let mut rig = LegacyRig::new();
        rig.arm();
        rig.frames(200, 0.5, 0.0, 0.0); // 2725: the C++'s target for +0.5
        assert_eq!(rig.last(STEER), Some(set_target(2725).to_vec()));
        rig.frames(300, -1.0, 0.0, 0.0); // 0, clipped to 400
        assert_eq!(rig.last(STEER), Some(set_target(400).to_vec()));
    }

    #[test]
    fn a_brake_frame_cuts_the_throttle_at_once() {
        let mut rig = LegacyRig::new();
        rig.arm();
        rig.frames(100, 0.0, 0.8, 0.0);
        assert!(rig.dac() > 0);
        rig.frame(0.0, 0.8, -0.3);
        assert_eq!(rig.dac(), 0);
        assert_eq!(rig.last(BRAKE), Some(set_target(1050).to_vec()));
    }

    #[test]
    fn silence_brakes_fully_within_the_timeout() {
        let mut rig = LegacyRig::new();
        rig.arm();
        rig.frames(100, 0.0, 0.5, 0.0);
        let mut out = rig.sb.tick();
        for _ in 0..25 {
            rig.sb.board().now += 10;
            out = rig.sb.tick();
        }
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
        assert_ne!(out.faults & faults::CMD_TIMEOUT, 0);
        assert_eq!(rig.dac(), 0);
        assert_eq!(rig.last(BRAKE), Some(set_target(3500).to_vec()));
    }

    #[test]
    fn the_rc_override_beats_the_motor_pi() {
        let mut rig = LegacyRig::new();
        rig.arm();
        rig.frames(100, 0.0, 0.5, 0.0);
        let mut ch = [1500; ibus::CHANNELS];
        ch[5] = 2000; // the override switch
        ch[4] = 1500; // the gear switch on brake
        let rc = ibus::encode(&ibus::Channels(ch));
        rig.receiver.0.borrow_mut().extend(rc);
        let out = rig.frame(0.0, 0.5, 0.0);
        assert_eq!(out.mode, Mode::Rc);
    }

    // --- Version 2: the Orin's heartbeat (TODO 50) ---

    /// Armed (a stand-still frame: the hold brake is a stop), then driving at speed 0.5.
    fn driving_v2() -> (LegacyRig, u8) {
        let mut rig = LegacyRig::with_version(FrameVersion::V2);
        let mut counter = 0;
        rig.moving(5, 0.0, -0.3, &mut counter);
        let out = rig.moving(100, 0.5, 0.0, &mut counter);
        assert_eq!(out.mode, Mode::Computer);
        assert_eq!(rig.dac(), 350);
        (rig, counter)
    }

    #[test]
    fn v2_a_moving_counter_drives() {
        driving_v2();
    }

    #[test]
    fn v2_a_frozen_counter_brakes_within_the_timeout_though_frames_still_come() {
        let (mut rig, counter) = driving_v2();
        // The Pi keeps sending the same drive frame at 50 Hz: the Orin stopped.
        let mut braked_after = None;
        for i in 1..=15 {
            let out = rig.frame_v2(0.5, 0.0, counter, true);
            if braked_after.is_none() && out.faults & faults::CMD_TIMEOUT != 0 {
                braked_after = Some(i * 20);
                assert_eq!((out.throttle, out.brake), (0.0, 1.0));
            }
        }
        // 100 ms after the last new counter, at the next 20 ms tick.
        assert_eq!(braked_after, Some(120));
        assert_eq!(rig.dac(), 0);
        assert_eq!(rig.last(BRAKE), Some(set_target(3500).to_vec()));
        // The 15, and the very first frame after boot, which only set the counter.
        assert_eq!(rig.sb.link().stats().repeats, 16);
    }

    #[test]
    fn v2_after_a_heartbeat_loss_it_stays_braked_until_a_stop() {
        let (mut rig, mut counter) = driving_v2();
        for _ in 0..10 {
            rig.frame_v2(0.5, 0.0, counter, true);
        }
        // The counter moves again, still driving: latched, no throttle.
        let out = rig.moving(20, 0.5, 0.0, &mut counter);
        assert_eq!(out.mode, Mode::Manual);
        assert_ne!(out.faults & faults::CMD_TIMEOUT, 0);
        assert_eq!(rig.dac(), 0);
        // A stop with a new counter (ego standing still), then driving again: re-armed.
        rig.moving(3, 0.0, -0.3, &mut counter);
        let out = rig.moving(100, 0.5, 0.0, &mut counter);
        assert_eq!(out.mode, Mode::Computer);
        assert_eq!(rig.dac(), 350);
    }

    #[test]
    fn v2_stop_frames_with_a_frozen_counter_do_not_re_arm() {
        // The bridge's stale stops while the Orin is gone carry the last counter: they
        // must not count as the arming edge's stop.
        let (mut rig, mut counter) = driving_v2();
        for _ in 0..20 {
            rig.frame_v2(0.0, -1.0, counter, false);
        }
        let out = rig.moving(30, 0.5, 0.0, &mut counter);
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(rig.dac(), 0);
    }

    #[test]
    fn v2_bad_crc_frames_are_ignored_so_the_heartbeat_stops() {
        let (mut rig, mut counter) = driving_v2();
        let mut out = rig.sb.tick();
        for _ in 0..10 {
            counter = counter.wrapping_add(1);
            let mut bytes = FrameV2 {
                values: Frame {
                    steering: 0.0,
                    speed: 0.5,
                    accel: 0.0,
                },
                counter,
                flags: Flags {
                    armed: true,
                    estop: false,
                },
            }
            .encode();
            bytes[16] ^= 0x5A;
            rig.motor_pi.0.borrow_mut().extend(bytes);
            rig.sb.board().now += 20;
            out = rig.sb.tick();
        }
        assert_ne!(out.faults & faults::CMD_TIMEOUT, 0);
        assert_eq!(rig.dac(), 0);
        assert_eq!(rig.sb.link().stats().bad, 10);
    }

    #[test]
    fn v2_ignores_version_1_frames_so_never_drives() {
        let mut rig = LegacyRig::with_version(FrameVersion::V2);
        rig.arm(); // version 1 stop frames
        let out = rig.frames(100, 0.0, 0.5, 0.0);
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(rig.dac(), 0);
    }
}
