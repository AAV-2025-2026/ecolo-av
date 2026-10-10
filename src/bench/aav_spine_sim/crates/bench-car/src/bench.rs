//! The bench: the spine's real logic driving the model car, one tick at a time.
//!
//! Frames go in as they arrive from the bus. Each tick builds the spine's `Inputs` (the
//! frames since the last tick, the model's speed and steering, the bench's switches), runs
//! `Spine::step`, moves the model under the `Outputs`, and returns the frames the spine
//! sends: VEHICLE_FEEDBACK every 20 ms, VEHICLE_STATUS every 100 ms, as on the car.

use spine_core::protocol::{decode_incoming, FrameError, Incoming};
use spine_core::protocol::{VEHICLE_FEEDBACK_ID, VEHICLE_STATUS_ID};
use spine_core::{Inputs, Outputs, Spine, SpineConfig};

use crate::plant::{Plant, PlantConfig, Pose};

/// How often the spine sends each frame (ms), from firmware/can/aav.dbc.
pub const FEEDBACK_PERIOD_MS: u32 = 20;
pub const STATUS_PERIOD_MS: u32 = 100;

/// One CAN frame: an 11-bit ID and 8 data bytes.
pub type Frame = (u16, [u8; 8]);

pub struct Bench {
    spine: Spine,
    plant: Plant,
    now_ms: u32,
    since_feedback_ms: u32,
    since_status_ms: u32,
    pending: Inputs,
    hw_estop: bool,
    driver_faults: u16,
    last: Option<Outputs>,
}

impl Bench {
    pub fn new(spine: SpineConfig, plant: PlantConfig, start: Pose) -> Self {
        Bench {
            spine: Spine::new(spine),
            plant: Plant::new(plant, start),
            now_ms: 0,
            since_feedback_ms: 0,
            since_status_ms: 0,
            pending: Inputs::default(),
            hw_estop: false,
            driver_faults: 0,
            last: None,
        }
    }

    /// A frame from the bus. Frames for other IDs are ignored, as the spine's filter does.
    pub fn receive(&mut self, id: u16, data: &[u8]) {
        match decode_incoming(id, data) {
            Ok(Incoming::Drive(cmd)) => self.pending.drive_cmd = Some(cmd),
            Ok(Incoming::Estop(cmd)) => self.pending.estop_cmd = Some(cmd),
            Err(FrameError::UnknownId) => {}
            Err(_) => self.pending.bad_frame = true,
        }
    }

    /// The hardware e-stop loop: true = open (pressed).
    pub fn set_hw_estop(&mut self, open: bool) {
        self.hw_estop = open;
    }

    /// Pretend a driver failed: spine_core::faults bits, 0 = all well.
    pub fn set_driver_faults(&mut self, bits: u16) {
        self.driver_faults = bits;
    }

    /// Run the spine and the model for `dt_ms`, and return the frames due.
    pub fn tick(&mut self, dt_ms: u32) -> Vec<Frame> {
        self.now_ms = self.now_ms.wrapping_add(dt_ms);
        let pose = self.plant.pose();
        let inputs = Inputs {
            now_ms: self.now_ms,
            hw_estop: self.hw_estop,
            rc: None,
            measured_speed: pose.speed,
            measured_steering: pose.steering,
            driver_faults: self.driver_faults,
            ..core::mem::take(&mut self.pending)
        };
        let out = self.spine.step(&inputs);
        self.plant.step(&out, dt_ms as f32 / 1000.0);
        self.last = Some(out);

        let mut frames = Vec::new();
        self.since_feedback_ms += dt_ms;
        self.since_status_ms += dt_ms;
        if self.since_feedback_ms >= FEEDBACK_PERIOD_MS {
            self.since_feedback_ms -= FEEDBACK_PERIOD_MS;
            let p = self.plant.pose();
            let data = self
                .spine
                .feedback_frame(p.speed, p.steering, self.plant.wheel_ticks());
            frames.push((VEHICLE_FEEDBACK_ID, data));
        }
        if self.since_status_ms >= STATUS_PERIOD_MS {
            self.since_status_ms -= STATUS_PERIOD_MS;
            frames.push((VEHICLE_STATUS_ID, self.spine.status_frame(&out)));
        }
        frames
    }

    /// Where the model car is: the ground truth.
    pub fn pose(&self) -> Pose {
        self.plant.pose()
    }

    /// What the spine wrote to the actuators on the last tick.
    pub fn outputs(&self) -> Option<Outputs> {
        self.last
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use spine_core::faults;
    use spine_core::protocol::{DriveCmd, EstopCmd, Mode, VehicleStatus};

    /// The bench, and what spine_bridge would send it.
    struct Rig {
        bench: Bench,
        counter: u8,
    }

    impl Rig {
        fn new() -> Self {
            Rig {
                bench: Bench::new(
                    SpineConfig::default(),
                    PlantConfig::default(),
                    Pose::default(),
                ),
                counter: 0,
            }
        }

        fn drive(&mut self, speed: f32, steering: f32, armed: bool) {
            self.counter = (self.counter + 1) & 0x0F;
            let cmd = DriveCmd {
                target_speed: speed,
                steering_angle: steering,
                accel_limit: 0.0,
                steer_rate_limit: 0.0,
                armed,
                counter: self.counter,
            };
            self.bench
                .receive(spine_core::protocol::DRIVE_CMD_ID, &cmd.encode());
        }

        /// `seconds` of 10 ms ticks, with a drive command every 20 ms (50 Hz).
        fn run(&mut self, seconds: f32, cmd: Option<(f32, f32, bool)>) -> Vec<Frame> {
            let mut frames = Vec::new();
            for i in 0..(seconds * 100.0) as usize {
                if let (Some((v, d, armed)), true) = (cmd, i % 2 == 0) {
                    self.drive(v, d, armed);
                }
                frames.extend(self.bench.tick(10));
            }
            frames
        }

        /// What spine_bridge's /spine/arm does: armed=0 frames, then armed=1.
        fn arm(&mut self) {
            self.run(0.1, Some((0.0, 0.0, false)));
            self.run(0.1, Some((0.0, 0.0, true)));
        }

        fn last_status(frames: &[Frame]) -> VehicleStatus {
            let (_, data) = frames
                .iter()
                .rev()
                .find(|(id, _)| *id == VEHICLE_STATUS_ID)
                .unwrap();
            VehicleStatus::decode(data).unwrap()
        }
    }

    #[test]
    fn boots_latched_and_does_not_move_without_the_arming_edge() {
        let mut rig = Rig::new();
        let frames = rig.run(2.0, Some((1.0, 0.0, true)));
        assert_eq!(rig.bench.pose().speed, 0.0);
        assert!(!Rig::last_status(&frames).armed);
    }

    #[test]
    fn armed_it_drives_to_the_target_speed_through_the_speed_loop() {
        let mut rig = Rig::new();
        rig.arm();
        let frames = rig.run(8.0, Some((1.0, 0.0, true)));
        let v = rig.bench.pose().speed;
        assert!((v - 1.0).abs() < 0.15, "settles near 1 m/s: {v}");
        let status = Rig::last_status(&frames);
        assert_eq!(status.mode, Mode::Computer);
        assert!(status.armed);
        assert!(
            rig.bench.pose().x > 4.0,
            "it went somewhere: {}",
            rig.bench.pose().x
        );
    }

    #[test]
    fn asked_to_stop_it_stops_instead_of_creeping() {
        let mut rig = Rig::new();
        rig.arm();
        rig.run(8.0, Some((1.0, 0.0, true)));
        rig.run(2.0, Some((0.0, 0.0, true)));
        assert_eq!(rig.bench.pose().speed, 0.0, "stopped within 2 s");
        let x = rig.bench.pose().x;
        rig.run(5.0, Some((0.0, 0.0, true)));
        assert_eq!(rig.bench.pose().x, x, "and held there");
    }

    #[test]
    fn steering_follows_the_command() {
        let mut rig = Rig::new();
        rig.arm();
        rig.run(3.0, Some((1.0, 0.3, true)));
        assert!((rig.bench.pose().steering - 0.3).abs() < 0.02);
        assert!(rig.bench.pose().yaw > 0.0, "turning left");
    }

    #[test]
    fn lost_commands_brake_the_car_and_latch_it() {
        let mut rig = Rig::new();
        rig.arm();
        rig.run(5.0, Some((1.0, 0.0, true)));
        assert!(rig.bench.pose().speed > 0.5);
        let frames = rig.run(3.0, None);
        assert_eq!(rig.bench.pose().speed, 0.0, "the watchdog braked");
        let status = Rig::last_status(&frames);
        assert!(!status.armed);
        assert!(status.faults & faults::CMD_TIMEOUT != 0);
    }

    #[test]
    fn the_software_estop_brakes() {
        let mut rig = Rig::new();
        rig.arm();
        rig.run(5.0, Some((1.0, 0.0, true)));
        let estop = EstopCmd {
            estop_request: true,
            counter: 1,
        };
        rig.bench
            .receive(spine_core::protocol::ESTOP_CMD_ID, &estop.encode());
        let frames = rig.run(2.0, Some((1.0, 0.0, true)));
        assert_eq!(rig.bench.pose().speed, 0.0);
        assert!(Rig::last_status(&frames).estop_active);
    }

    #[test]
    fn the_hardware_estop_and_a_driver_fault_brake_too() {
        for which in 0..2 {
            let mut rig = Rig::new();
            rig.arm();
            rig.run(5.0, Some((1.0, 0.0, true)));
            if which == 0 {
                rig.bench.set_hw_estop(true);
            } else {
                rig.bench.set_driver_faults(faults::STEERING_DRIVER);
            }
            rig.run(2.0, Some((1.0, 0.0, true)));
            assert_eq!(rig.bench.pose().speed, 0.0, "case {which}");
        }
    }

    #[test]
    fn a_bad_checksum_is_reported_and_ignored() {
        let mut rig = Rig::new();
        let mut data = DriveCmd {
            target_speed: 1.0,
            steering_angle: 0.0,
            accel_limit: 0.0,
            steer_rate_limit: 0.0,
            armed: false,
            counter: 1,
        }
        .encode();
        data[7] ^= 0xFF;
        rig.bench.receive(spine_core::protocol::DRIVE_CMD_ID, &data);
        let frames = rig.run(0.1, None);
        assert!(Rig::last_status(&frames).faults & faults::BAD_CHECKSUM != 0);
    }

    #[test]
    fn frames_go_out_at_50_and_10_hz() {
        let mut rig = Rig::new();
        let frames = rig.run(1.0, None);
        let count = |id| frames.iter().filter(|(i, _)| *i == id).count();
        assert_eq!(count(VEHICLE_FEEDBACK_ID), 50);
        assert_eq!(count(VEHICLE_STATUS_ID), 10);
    }
}
