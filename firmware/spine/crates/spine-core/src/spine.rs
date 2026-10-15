//! The spine's decisions, one call per tick (about 100 Hz).
//!
//! Priorities, highest first:
//! 1. Any e-stop (hardware input or ESTOP_CMD): throttle off, full brake.
//! 2. The RC transmitter, while its override switch is on.
//! 3. The computer, while armed and sending fresh DRIVE_CMD frames.
//! 4. Otherwise manual: actuators idle.
//!
//! A driver fault (steering, brake, throttle or encoder) stops the car in any mode.
//!
//! The computer's commands come in two kinds, with the same watchdog and arming:
//!
//! | Kind | From | The spine |
//! |---|---|---|
//! | [`DriveCmd`]: a speed and a steering angle | CAN (`firmware/can/aav.dbc`) | runs the speed loop |
//! | [`DirectCmd`]: throttle, brake and steering as they are | the 2025-26 UART link (`legacy-link`) | passes them on, inside its limits |
//!
//! With no wheel speed on the board ([`SpeedFeedback::None`]), the speed loop runs open
//! loop: throttle in proportion to the speed asked for.
//!
//! The computer can't drive until it sends a frame with `armed = 0` and then
//! `armed = 1`: at power-up, after an e-stop, after a driver fault has cleared, and
//! after the command stream stopped while it was driving. A glitch or a reboot never
//! restarts the car by itself.

use crate::limits::slew;
use crate::protocol::{counter_step, DriveCmd, EstopCmd, Mode, VehicleFeedback, VehicleStatus};
use crate::speed_loop::{SpeedLoop, SpeedLoopConfig};
use crate::watchdog::Watchdog;

/// Fault bits, same values as aav_interfaces/VehicleStatus FAULT_*.
pub mod faults {
    pub const CMD_TIMEOUT: u16 = 1;
    pub const BAD_CHECKSUM: u16 = 2;
    pub const BAD_COUNTER: u16 = 4;
    pub const STEERING_DRIVER: u16 = 8;
    pub const BRAKE_DRIVER: u16 = 16;
    pub const THROTTLE_DAC: u16 = 32;
    pub const WHEEL_ENCODER: u16 = 64;
    pub const CAN_BUS: u16 = 128;
    pub const RC_SIGNAL_LOST: u16 = 256;
    pub const OVERSPEED: u16 = 512;

    /// Faults that stop the car and latch it, like a command timeout.
    pub const STOP: u16 = STEERING_DRIVER | BRAKE_DRIVER | THROTTLE_DAC | WHEEL_ENCODER;
}

// Three choices still open with the team (docs/firmware.md, "Still to decide"). Each is one
// constant, set to what the docs propose. `SpineConfig::default()` uses them, so the board
// program and the bench both follow a change here.

/// The steering on an e-stop, and on every other stop the spine makes by itself: a driver
/// fault, a lost RC signal, a command timeout, overspeed. Proposed: hold it where it is.
/// The 2025-26 firmware centred it (`jrkSafeStop()`).
pub const ESTOP_STEERING: EstopSteering = EstopSteering::Hold;

/// The brake while nobody drives, from boot on (0 to 1). Proposed: 0, so the brake lets go
/// once the e-stop input clears. The 2025-26 firmware kept it full on (1.0).
pub const IDLE_BRAKE: f32 = 0.0;

/// What the RC gear switch's brake position does. Proposed: speed zero, so the speed loop
/// brakes to a stop and holds. The 2025-26 firmware put the brake full on at once.
pub const RC_GEAR_BRAKE: RcGearBrake = RcGearBrake::SpeedZero;

// Copies of src/aav_description/config/vehicle.yaml, the one place the car's numbers live:
// the firmware can't read it. src/aav_description/test/test_vehicle.py checks the copies.

/// The virtual centre wheel's steering limit, either way (rad): vehicle.yaml
/// `max_steering_angle`. TODO(Q1): measure on the car.
pub const MAX_STEERING_ANGLE: f32 = 0.5;

/// The fastest the car may go backwards (m/s), whoever drives, the RC transmitter too:
/// vehicle.yaml `max_reverse_speed`. Slow on purpose: nothing senses what is behind the car.
pub const MAX_REVERSE_SPEED: f32 = 0.5;

/// What the steering does when the spine stops the car by itself.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EstopSteering {
    /// Hold the wheels where they are.
    Hold,
    /// Bring the wheels back to straight, at the steering rate limit.
    Centre,
}

/// What the RC gear switch's brake position (its middle) does.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RcGearBrake {
    /// Ask for zero speed: the speed loop brakes to a stop, then holds the car there.
    SpeedZero,
    /// Throttle off and the brake full on at once; the steering still follows the stick.
    FullBrake,
}

/// Where the speed loop gets the car's speed.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum SpeedFeedback {
    /// `Inputs::measured_speed`, from a wheel encoder: closed loop.
    Wheel,
    /// No speed on this board (today's ESP32 control board: the encoder talks to the
    /// Motor-Pi). Open loop: throttle = speed / `full_throttle_speed`, the 2025-26 way.
    /// The overspeed check can't work, and the stop brake is the hold brake.
    None {
        /// The speed (m/s) the car reaches at full throttle. TODO(Q4): measure.
        full_throttle_speed: f32,
    },
}

#[derive(Debug, Clone, Copy)]
pub struct SpineConfig {
    /// No valid DRIVE_CMD for this long while driving = stop (ms).
    pub cmd_timeout_ms: u32,
    /// The firmware's own speed caps (m/s), applied after ego's.
    pub max_speed: f32,
    pub max_reverse_speed: f32,
    /// Steering range (rad), from the car's measurements.
    pub max_steering_angle: f32,
    /// Acceleration and steering-rate caps, also used when a frame sends 0.
    pub max_accel: f32,
    /// Slowing down is capped separately, and harder than ego's 2.0 m/s^2, so the
    /// firmware never lags behind a stop that ego asked for.
    pub max_decel: f32,
    pub max_steer_rate: f32,
    /// Measured speed this far over the cap is a fault and brakes (m/s).
    pub overspeed_margin: f32,
    /// Brake for stops, and brake in manual mode (0..1).
    pub stop_brake: f32,
    pub idle_brake: f32,
    /// The steering on a stop: [`ESTOP_STEERING`].
    pub estop_steering: EstopSteering,
    /// The RC gear switch's brake position: [`RC_GEAR_BRAKE`].
    pub rc_gear_brake: RcGearBrake,
    pub speed_loop: SpeedLoopConfig,
    /// The wheel speed, or none: [`SpeedFeedback`].
    pub speed_feedback: SpeedFeedback,
}

impl Default for SpineConfig {
    fn default() -> Self {
        SpineConfig {
            cmd_timeout_ms: 100,
            max_speed: 3.0,
            max_reverse_speed: MAX_REVERSE_SPEED,
            max_steering_angle: MAX_STEERING_ANGLE,
            max_accel: 1.5,
            max_decel: 2.5,
            max_steer_rate: 0.6,
            overspeed_margin: 0.5,
            stop_brake: 1.0,
            idle_brake: IDLE_BRAKE,
            estop_steering: ESTOP_STEERING,
            rc_gear_brake: RC_GEAR_BRAKE,
            speed_loop: SpeedLoopConfig::default(),
            speed_feedback: SpeedFeedback::Wheel,
        }
    }
}

/// The RC receiver, already scaled by the board crate.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RcInput {
    /// The transmitter's override switch: true = RC drives.
    pub override_switch: bool,
    /// -1..1, positive forward.
    pub throttle: f32,
    /// -1..1, positive left.
    pub steering: f32,
    /// The gear switch is on brake. What that does is [`SpineConfig::rc_gear_brake`].
    pub brake: bool,
}

/// An open-loop command: the actuators' demands as they are, with no speed loop. The
/// 2025-26 UART link carries these (`legacy-link`): it has no speed, and no arming bit.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DirectCmd {
    /// 0..1, to the throttle. Ignored while `brake` is above 0.
    pub throttle: f32,
    /// The direction for the throttle.
    pub reverse: bool,
    /// 0..1, to the brake.
    pub brake: f32,
    /// rad, positive left.
    pub steering_angle: f32,
    /// This command is a stop: no throttle. A stop is the first half of the arming edge,
    /// like `armed = 0` in a DRIVE_CMD; any command after it is the second half. Unlike
    /// `armed = 0`, a stop still drives the actuators: its brake is applied.
    pub stop: bool,
}

/// The computer's latest command, of either kind.
#[derive(Debug, Clone, Copy, PartialEq)]
enum Command {
    Speed(DriveCmd),
    Direct(DirectCmd),
}

impl Command {
    fn armed(&self) -> bool {
        match self {
            Command::Speed(cmd) => cmd.armed,
            // Every command of this kind counts as armed: the link has no arming bit.
            // Only its stops make the edge (below).
            Command::Direct(_) => true,
        }
    }
}

/// Everything the board read this tick.
#[derive(Debug, Clone, Copy, Default)]
pub struct Inputs {
    /// Free-running milliseconds; may wrap.
    pub now_ms: u32,
    /// A valid DRIVE_CMD received since the last tick.
    pub drive_cmd: Option<DriveCmd>,
    /// A valid open-loop command received since the last tick (the UART link).
    pub direct_cmd: Option<DirectCmd>,
    /// A valid ESTOP_CMD received since the last tick.
    pub estop_cmd: Option<EstopCmd>,
    /// A frame for the spine failed its length or checksum since the last tick.
    pub bad_frame: bool,
    /// The hardware e-stop loop is open.
    pub hw_estop: bool,
    /// None when the RC receiver has been silent too long.
    pub rc: Option<RcInput>,
    pub measured_speed: f32,
    pub measured_steering: f32,
    /// Driver faults found by the board: STEERING_DRIVER, BRAKE_DRIVER,
    /// THROTTLE_DAC, WHEEL_ENCODER, CAN_BUS.
    pub driver_faults: u16,
}

/// What the board writes to the hardware this tick.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Outputs {
    pub mode: Mode,
    /// 0..1, to the throttle DAC.
    pub throttle: f32,
    /// 0..1, to the brake actuator.
    pub brake: f32,
    /// Direction output to the motor controller.
    pub reverse: bool,
    /// rad, positive left; the board converts it to a Jrk G2 target.
    pub steering_target: f32,
    pub armed: bool,
    pub estop_active: bool,
    pub faults: u16,
}

pub struct Spine {
    cfg: SpineConfig,
    watchdog: Watchdog,
    speed_loop: SpeedLoop,
    last_cmd: Option<Command>,
    last_counter: Option<u8>,
    sw_estop: bool,
    latched: bool,
    timeout_latched: bool,
    fault_latched: bool,
    seen_disarm: bool,
    mode: Mode,
    speed_setpoint: f32,
    steering_setpoint: f32,
    last_ms: Option<u32>,
    frame_faults: u16,
    feedback_counter: u8,
    status_counter: u8,
}

impl Spine {
    pub fn new(cfg: SpineConfig) -> Self {
        Spine {
            cfg,
            watchdog: Watchdog::new(cfg.cmd_timeout_ms),
            speed_loop: SpeedLoop::new(cfg.speed_loop),
            last_cmd: None,
            last_counter: None,
            sw_estop: false,
            latched: true, // boot latched: the computer must disarm, then arm
            timeout_latched: false,
            fault_latched: false,
            seen_disarm: false,
            mode: Mode::Manual,
            speed_setpoint: 0.0,
            steering_setpoint: 0.0,
            last_ms: None,
            frame_faults: 0,
            feedback_counter: 0,
            status_counter: 0,
        }
    }

    pub fn step(&mut self, i: &Inputs) -> Outputs {
        let c = self.cfg;
        let dt = match self.last_ms {
            Some(t) => (i.now_ms.wrapping_sub(t) as f32 / 1000.0).min(0.1),
            None => 0.0,
        };
        self.last_ms = Some(i.now_ms);
        if i.bad_frame {
            self.frame_faults |= faults::BAD_CHECKSUM;
        }

        // New frames. A repeated counter means a stuck sender: it doesn't
        // count as a fresh command.
        if let Some(e) = i.estop_cmd {
            self.sw_estop = e.estop_request;
        }
        if let Some(cmd) = i.drive_cmd {
            if counter_step(self.last_counter, cmd.counter) == 0 {
                self.frame_faults |= faults::BAD_COUNTER;
            } else {
                self.watchdog.feed(i.now_ms);
                self.last_cmd = Some(Command::Speed(cmd));
                if !cmd.armed {
                    self.seen_disarm = true;
                }
            }
            self.last_counter = Some(cmd.counter);
        }
        // The UART link has no counter: its checksum is all it has.
        if let Some(cmd) = i.direct_cmd {
            self.watchdog.feed(i.now_ms);
            self.last_cmd = Some(Command::Direct(cmd));
            if cmd.stop {
                self.seen_disarm = true;
            }
        }
        let fresh = !self.watchdog.expired(i.now_ms);
        let armed_request = fresh && self.last_cmd.is_some_and(|cmd| cmd.armed());

        // Latches.
        let estop = i.hw_estop || self.sw_estop;
        if estop {
            self.latched = true;
            self.seen_disarm = false;
        }
        let driver_fault = i.driver_faults & faults::STOP != 0;
        if driver_fault {
            self.latched = true;
            self.fault_latched = true;
            self.seen_disarm = false;
        }
        if self.mode == Mode::Computer && !fresh && !estop {
            self.latched = true;
            self.timeout_latched = true;
            self.seen_disarm = false;
        }
        if self.latched && !estop && !driver_fault && self.seen_disarm && armed_request {
            self.latched = false;
            self.timeout_latched = false;
            self.fault_latched = false;
        }

        // Mode.
        let rc_override = i.rc.is_some_and(|rc| rc.override_switch);
        let rc_lost = self.mode == Mode::Rc && i.rc.is_none();
        self.mode = if rc_override || rc_lost {
            Mode::Rc
        } else if armed_request && !self.latched {
            Mode::Computer
        } else {
            Mode::Manual
        };

        let mut fault_bits = i.driver_faults | self.frame_faults;
        if self.timeout_latched {
            fault_bits |= faults::CMD_TIMEOUT;
        }
        if rc_lost {
            fault_bits |= faults::RC_SIGNAL_LOST;
        }
        let over = if i.measured_speed >= 0.0 {
            i.measured_speed - c.max_speed
        } else {
            -i.measured_speed - c.max_reverse_speed
        };
        // Without a wheel speed, there is no overspeed to see.
        let over = if c.speed_feedback == SpeedFeedback::Wheel {
            over
        } else {
            0.0
        };
        if over > c.overspeed_margin {
            fault_bits |= faults::OVERSPEED;
        }

        let stop = estop || driver_fault || rc_lost || over > c.overspeed_margin;
        let out = |throttle, brake, reverse, steering, s: &Self| Outputs {
            mode: s.mode,
            throttle,
            brake,
            reverse,
            steering_target: steering,
            armed: armed_request && !s.latched,
            estop_active: estop || s.timeout_latched || s.fault_latched,
            faults: fault_bits,
        };

        if stop || (self.mode == Mode::Manual && (self.timeout_latched || self.fault_latched)) {
            self.speed_setpoint = 0.0;
            self.speed_loop.reset();
            if c.estop_steering == EstopSteering::Centre {
                self.steering_setpoint = slew(self.steering_setpoint, 0.0, c.max_steer_rate, dt);
            }
            return out(0.0, c.stop_brake, false, self.steering_setpoint, self);
        }

        // Targets for this mode, inside the firmware's own limits.
        let mut full_brake = false;
        let (target_speed, target_steering, accel, steer_rate) = match self.mode {
            Mode::Manual => {
                self.speed_setpoint = 0.0;
                self.speed_loop.reset();
                return out(0.0, c.idle_brake, false, self.steering_setpoint, self);
            }
            Mode::Rc => {
                let rc = i.rc.unwrap_or(RcInput {
                    override_switch: true,
                    throttle: 0.0,
                    steering: 0.0,
                    brake: false,
                });
                full_brake = rc.brake && c.rc_gear_brake == RcGearBrake::FullBrake;
                let cap = if rc.throttle >= 0.0 {
                    c.max_speed
                } else {
                    c.max_reverse_speed
                };
                (
                    rc.throttle.clamp(-1.0, 1.0) * cap,
                    rc.steering.clamp(-1.0, 1.0) * c.max_steering_angle,
                    c.max_accel,
                    c.max_steer_rate,
                )
            }
            Mode::Computer => {
                let cmd = match self.last_cmd {
                    Some(Command::Speed(cmd)) => cmd,
                    Some(Command::Direct(cmd)) => return self.direct(&cmd, dt, &out),
                    None => DriveCmd {
                        target_speed: 0.0,
                        steering_angle: self.steering_setpoint,
                        accel_limit: 0.0,
                        steer_rate_limit: 0.0,
                        armed: false,
                        counter: 0,
                    },
                };
                let accel = if cmd.accel_limit > 0.0 {
                    cmd.accel_limit.min(c.max_accel)
                } else {
                    c.max_accel
                };
                let rate = if cmd.steer_rate_limit > 0.0 {
                    cmd.steer_rate_limit.min(c.max_steer_rate)
                } else {
                    c.max_steer_rate
                };
                (cmd.target_speed, cmd.steering_angle, accel, rate)
            }
        };
        let target_speed = target_speed.clamp(-c.max_reverse_speed, c.max_speed);
        let target_steering = target_steering.clamp(-c.max_steering_angle, c.max_steering_angle);
        self.steering_setpoint = slew(self.steering_setpoint, target_steering, steer_rate, dt);
        if full_brake {
            self.speed_setpoint = 0.0;
            self.speed_loop.reset();
            return out(0.0, c.stop_brake, false, self.steering_setpoint, self);
        }
        // Slowing down (toward zero, or through it) uses the separate, harder cap.
        let slowing = target_speed.abs() < self.speed_setpoint.abs()
            || target_speed * self.speed_setpoint < 0.0;
        let rate = if slowing { c.max_decel } else { accel };
        self.speed_setpoint = slew(self.speed_setpoint, target_speed, rate, dt);
        let drive = match c.speed_feedback {
            SpeedFeedback::Wheel => {
                self.speed_loop
                    .update(self.speed_setpoint, i.measured_speed, dt)
            }
            SpeedFeedback::None {
                full_throttle_speed,
            } => self
                .speed_loop
                .open_loop(self.speed_setpoint, full_throttle_speed),
        };
        out(
            drive.throttle,
            drive.brake,
            drive.reverse,
            self.steering_setpoint,
            self,
        )
    }

    /// An open-loop command, in computer mode: steering at the steering rate limit, the
    /// throttle and the brake as asked (never both), inside the firmware's limits.
    fn direct(
        &mut self,
        cmd: &DirectCmd,
        dt: f32,
        out: &impl Fn(f32, f32, bool, f32, &Self) -> Outputs,
    ) -> Outputs {
        let c = self.cfg;
        self.speed_setpoint = 0.0;
        self.speed_loop.reset();
        let target = cmd
            .steering_angle
            .clamp(-c.max_steering_angle, c.max_steering_angle);
        let target = if target.is_nan() {
            self.steering_setpoint
        } else {
            target
        };
        self.steering_setpoint = slew(self.steering_setpoint, target, c.max_steer_rate, dt);
        let brake = if cmd.brake.is_nan() {
            1.0
        } else {
            cmd.brake.clamp(0.0, 1.0)
        };
        let throttle = if cmd.stop || brake > 0.0 || cmd.throttle.is_nan() {
            0.0
        } else {
            cmd.throttle.clamp(0.0, 1.0)
        };
        out(throttle, brake, cmd.reverse, self.steering_setpoint, self)
    }

    /// VEHICLE_FEEDBACK frame (send at 50 Hz).
    pub fn feedback_frame(
        &mut self,
        measured_speed: f32,
        measured_steering: f32,
        wheel_ticks: u16,
    ) -> [u8; 8] {
        self.feedback_counter = (self.feedback_counter + 1) & 0x0F;
        VehicleFeedback {
            measured_speed,
            measured_steering_angle: measured_steering,
            wheel_ticks,
            counter: self.feedback_counter,
        }
        .encode()
    }

    /// VEHICLE_STATUS frame (send at 10 Hz). Reports frame faults seen since
    /// the previous status frame, then clears them.
    pub fn status_frame(&mut self, out: &Outputs) -> [u8; 8] {
        self.status_counter = (self.status_counter + 1) & 0x0F;
        let frame = VehicleStatus {
            mode: out.mode,
            armed: out.armed,
            estop_active: out.estop_active,
            throttle: out.throttle * 100.0,
            brake: out.brake * 100.0,
            faults: out.faults | self.frame_faults,
            counter: self.status_counter,
        }
        .encode();
        self.frame_faults = 0;
        frame
    }

    pub fn mode(&self) -> Mode {
        self.mode
    }

    /// The rate-limited speed the speed loop is chasing (m/s).
    pub fn speed_setpoint(&self) -> f32 {
        self.speed_setpoint
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    struct Car {
        spine: Spine,
        now: u32,
        counter: u8,
    }

    impl Car {
        fn new() -> Self {
            Car::with_config(SpineConfig::default())
        }

        fn with_config(cfg: SpineConfig) -> Self {
            Car {
                spine: Spine::new(cfg),
                now: 1000,
                counter: 0,
            }
        }

        fn cmd(&mut self, speed: f32, steering: f32, armed: bool) -> DriveCmd {
            self.counter = (self.counter + 1) & 0x0F;
            DriveCmd {
                target_speed: speed,
                steering_angle: steering,
                accel_limit: 0.0,
                steer_rate_limit: 0.0,
                armed,
                counter: self.counter,
            }
        }

        fn tick(&mut self, mut i: Inputs) -> Outputs {
            self.now += 10;
            i.now_ms = self.now;
            self.spine.step(&i)
        }

        /// The computer's arming edge: `armed = 0`, then the caller sends `armed = 1`.
        fn arm(&mut self) {
            self.drive(0.0, 0.0, false, 2);
        }

        fn drive(&mut self, speed: f32, steering: f32, armed: bool, ticks: u32) -> Outputs {
            let mut last = None;
            for _ in 0..ticks {
                let cmd = self.cmd(speed, steering, armed);
                last = Some(self.tick(Inputs {
                    drive_cmd: Some(cmd),
                    ..Default::default()
                }));
            }
            last.unwrap()
        }
    }

    #[test]
    fn idle_without_commands() {
        let mut car = Car::new();
        let out = car.tick(Inputs::default());
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(out.throttle, 0.0);
        assert_eq!(out.faults & faults::CMD_TIMEOUT, 0);
    }

    #[test]
    fn boots_latched_until_disarm_then_arm() {
        let mut car = Car::new();
        // Armed frames straight after a reboot must not drive...
        let out = car.drive(1.0, 0.0, true, 20);
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(out.throttle, 0.0);
        // ...until the computer disarms, then arms.
        car.arm();
        assert_eq!(car.drive(1.0, 0.0, true, 5).mode, Mode::Computer);
    }

    #[test]
    fn armed_commands_drive() {
        let mut car = Car::new();
        car.arm();
        let out = car.drive(1.0, 0.0, true, 20);
        assert_eq!(out.mode, Mode::Computer);
        assert!(out.armed);
        assert!(out.throttle > 0.0);
        assert_eq!(out.brake, 0.0);
    }

    #[test]
    fn unarmed_commands_do_not_drive() {
        let mut car = Car::new();
        let out = car.drive(1.0, 0.0, false, 20);
        assert_eq!(out.mode, Mode::Manual);
        assert_eq!(out.throttle, 0.0);
    }

    #[test]
    fn lost_commands_brake_and_latch() {
        let mut car = Car::new();
        car.arm();
        car.drive(1.0, 0.0, true, 20);
        let mut out = car.tick(Inputs::default());
        for _ in 0..25 {
            out = car.tick(Inputs::default()); // 250 ms of silence
        }
        assert_eq!(out.brake, 1.0);
        assert_eq!(out.throttle, 0.0);
        assert_ne!(out.faults & faults::CMD_TIMEOUT, 0);
        // Fresh armed commands alone don't restart the car...
        let out = car.drive(1.0, 0.0, true, 5);
        assert_eq!(out.throttle, 0.0);
        // ...a disarm then an arm does.
        car.drive(0.0, 0.0, false, 2);
        let out = car.drive(1.0, 0.0, true, 5);
        assert_eq!(out.mode, Mode::Computer);
        assert_eq!(out.faults & faults::CMD_TIMEOUT, 0);
    }

    #[test]
    fn software_estop_brakes_and_needs_rearm() {
        let mut car = Car::new();
        car.arm();
        car.drive(1.0, 0.0, true, 10);
        let cmd = car.cmd(1.0, 0.0, true);
        let out = car.tick(Inputs {
            drive_cmd: Some(cmd),
            estop_cmd: Some(EstopCmd {
                estop_request: true,
                counter: 1,
            }),
            ..Default::default()
        });
        assert!(out.estop_active);
        assert_eq!(out.brake, 1.0);
        let cmd = car.cmd(1.0, 0.0, true);
        let out = car.tick(Inputs {
            drive_cmd: Some(cmd),
            estop_cmd: Some(EstopCmd {
                estop_request: false,
                counter: 2,
            }),
            ..Default::default()
        });
        assert_ne!(out.mode, Mode::Computer);
        car.drive(0.0, 0.0, false, 2);
        assert_eq!(car.drive(1.0, 0.0, true, 3).mode, Mode::Computer);
    }

    #[test]
    fn hardware_estop_beats_rc() {
        let mut car = Car::new();
        let rc = RcInput {
            override_switch: true,
            throttle: 1.0,
            steering: 0.0,
            brake: false,
        };
        let out = car.tick(Inputs {
            rc: Some(rc),
            hw_estop: true,
            ..Default::default()
        });
        assert_eq!(out.throttle, 0.0);
        assert_eq!(out.brake, 1.0);
    }

    #[test]
    fn rc_beats_computer() {
        let mut car = Car::new();
        car.arm();
        car.drive(1.0, 0.0, true, 10);
        let rc = RcInput {
            override_switch: true,
            throttle: 0.0,
            steering: 1.0,
            brake: false,
        };
        let cmd = car.cmd(1.0, 0.0, true);
        let out = car.tick(Inputs {
            drive_cmd: Some(cmd),
            rc: Some(rc),
            ..Default::default()
        });
        assert_eq!(out.mode, Mode::Rc);
    }

    #[test]
    fn rc_signal_loss_brakes() {
        let mut car = Car::new();
        let rc = RcInput {
            override_switch: true,
            throttle: 0.5,
            steering: 0.0,
            brake: false,
        };
        car.tick(Inputs {
            rc: Some(rc),
            ..Default::default()
        });
        let out = car.tick(Inputs::default());
        assert_eq!(out.brake, 1.0);
        assert_ne!(out.faults & faults::RC_SIGNAL_LOST, 0);
    }

    #[test]
    fn speed_setpoint_ramps() {
        let mut car = Car::new();
        car.arm();
        car.drive(3.0, 0.0, true, 11); // 100 ms of ramp at 1.5 m/s^2
        let sp = car.spine.speed_setpoint();
        assert!(sp > 0.1 && sp < 0.2, "{sp}");
    }

    #[test]
    fn reverse_is_capped_for_the_computer_and_the_rc() {
        // The computer asks for 2 m/s backwards: it gets the reverse cap.
        let mut car = Car::new();
        car.arm();
        car.drive(-2.0, 0.2, true, 300);
        assert!((car.spine.speed_setpoint() + MAX_REVERSE_SPEED).abs() < 1e-6);
        // Full reverse on the RC stick: the same cap.
        let mut car = Car::new();
        let rc = RcInput {
            override_switch: true,
            throttle: -1.0,
            steering: 0.0,
            brake: false,
        };
        for _ in 0..300 {
            car.tick(Inputs {
                rc: Some(rc),
                ..Default::default()
            });
        }
        assert!((car.spine.speed_setpoint() + MAX_REVERSE_SPEED).abs() < 1e-6);
        assert_eq!(SpineConfig::default().max_reverse_speed, MAX_REVERSE_SPEED);
    }

    #[test]
    fn steering_is_clamped() {
        let mut car = Car::new();
        car.arm();
        let out = car.drive(0.5, 2.0, true, 300);
        assert!((out.steering_target - SpineConfig::default().max_steering_angle).abs() < 1e-6);
    }

    #[test]
    fn slows_down_faster_than_ego() {
        let mut car = Car::new();
        car.arm();
        car.drive(1.0, 0.0, true, 100); // up to 1 m/s
        assert!((car.spine.speed_setpoint() - 1.0).abs() < 1e-3);
        // ego stops at 2.0 m/s^2, so from 1 m/s it reaches 0 in 0.5 s. At 2.5 m/s^2
        // the firmware is already there after 0.4 s.
        car.drive(0.0, 0.0, true, 40);
        assert!(
            car.spine.speed_setpoint().abs() < 1e-3,
            "{}",
            car.spine.speed_setpoint()
        );
    }

    #[test]
    fn driver_fault_stops_and_needs_rearm() {
        let mut car = Car::new();
        car.arm();
        car.drive(1.0, 0.0, true, 20);
        let cmd = car.cmd(1.0, 0.0, true);
        let out = car.tick(Inputs {
            drive_cmd: Some(cmd),
            driver_faults: faults::WHEEL_ENCODER,
            ..Default::default()
        });
        assert_eq!(out.throttle, 0.0);
        assert_eq!(out.brake, 1.0);
        assert_ne!(out.faults & faults::WHEEL_ENCODER, 0);
        // The fault clears, but the car stays stopped until a fresh arm.
        let out = car.drive(1.0, 0.0, true, 5);
        assert_eq!(out.throttle, 0.0);
        assert!(out.estop_active);
        car.arm();
        assert_eq!(car.drive(1.0, 0.0, true, 5).mode, Mode::Computer);
    }

    #[test]
    fn driver_fault_stops_rc_too() {
        let mut car = Car::new();
        let rc = RcInput {
            override_switch: true,
            throttle: 1.0,
            steering: 0.0,
            brake: false,
        };
        let out = car.tick(Inputs {
            rc: Some(rc),
            driver_faults: faults::THROTTLE_DAC,
            ..Default::default()
        });
        assert_eq!(out.throttle, 0.0);
        assert_eq!(out.brake, 1.0);
    }

    #[test]
    fn repeated_counter_is_a_fault_and_not_fresh() {
        let mut car = Car::new();
        let cmd = car.cmd(1.0, 0.0, true);
        car.tick(Inputs {
            drive_cmd: Some(cmd),
            ..Default::default()
        });
        let out = car.tick(Inputs {
            drive_cmd: Some(cmd),
            ..Default::default()
        });
        assert_ne!(out.faults & faults::BAD_COUNTER, 0);
    }

    #[test]
    fn the_open_choices_are_what_the_docs_propose() {
        // docs/firmware.md, "Still to decide". Change them only with the team.
        assert_eq!(ESTOP_STEERING, EstopSteering::Hold);
        assert_eq!(IDLE_BRAKE, 0.0);
        assert_eq!(RC_GEAR_BRAKE, RcGearBrake::SpeedZero);
        let c = SpineConfig::default();
        assert_eq!(c.estop_steering, ESTOP_STEERING);
        assert_eq!(c.idle_brake, IDLE_BRAKE);
        assert_eq!(c.rc_gear_brake, RC_GEAR_BRAKE);
    }

    /// Steer to 0.3 rad, then hold the hardware e-stop for `ticks`.
    fn steering_on_an_estop(cfg: SpineConfig, ticks: usize) -> std::vec::Vec<f32> {
        let mut car = Car::with_config(cfg);
        car.arm();
        let out = car.drive(0.0, 0.3, true, 100);
        assert!((out.steering_target - 0.3).abs() < 1e-6);
        let estop = Inputs {
            hw_estop: true,
            ..Default::default()
        };
        (0..ticks)
            .map(|_| car.tick(estop).steering_target)
            .collect()
    }

    #[test]
    fn an_estop_holds_the_steering() {
        let steering = steering_on_an_estop(SpineConfig::default(), 100);
        assert!(
            steering.iter().all(|s| (s - 0.3).abs() < 1e-6),
            "{steering:?}"
        );
    }

    #[test]
    fn an_estop_can_centre_the_steering_instead() {
        let cfg = SpineConfig {
            estop_steering: EstopSteering::Centre,
            ..SpineConfig::default()
        };
        let steering = steering_on_an_estop(cfg, 100);
        // Back at the steering rate limit, 0.6 rad/s: 6 mrad a tick, straight after 0.5 s.
        assert!((steering[0] - 0.294).abs() < 1e-4, "{}", steering[0]);
        assert!(steering.windows(2).all(|w| w[1] <= w[0]));
        assert_eq!(steering[60..], [0.0; 40]);
    }

    #[test]
    fn the_idle_brake_after_boot() {
        // Nobody drives straight after boot: the brake is released...
        let out = Car::new().tick(Inputs::default());
        assert_eq!((out.mode, out.brake), (Mode::Manual, 0.0));
        // ...or full on, as the 2025-26 firmware kept it.
        let cfg = SpineConfig {
            idle_brake: 1.0,
            ..SpineConfig::default()
        };
        assert_eq!(Car::with_config(cfg).tick(Inputs::default()).brake, 1.0);
    }

    /// RC drives, with the gear switch on brake and the steering stick full left, while
    /// the car still rolls at 1 m/s.
    fn rc_on_brake(cfg: SpineConfig) -> Outputs {
        let mut car = Car::with_config(cfg);
        let rc = RcInput {
            override_switch: true,
            throttle: 0.0,
            steering: 1.0,
            brake: true,
        };
        let inputs = Inputs {
            rc: Some(rc),
            measured_speed: 1.0,
            ..Default::default()
        };
        (0..10).map(|_| car.tick(inputs)).last().unwrap()
    }

    #[test]
    fn the_rc_gear_brake_asks_for_speed_zero() {
        let out = rc_on_brake(SpineConfig::default());
        assert_eq!((out.mode, out.throttle), (Mode::Rc, 0.0));
        // The speed loop brakes as hard as the overspeed needs, not fully.
        assert!(out.brake > 0.0 && out.brake < 1.0, "{}", out.brake);
        assert!(out.steering_target > 0.0, "the stick still steers");
    }

    #[test]
    fn the_rc_gear_brake_can_be_the_full_brake() {
        let cfg = SpineConfig {
            rc_gear_brake: RcGearBrake::FullBrake,
            ..SpineConfig::default()
        };
        let out = rc_on_brake(cfg);
        assert_eq!((out.mode, out.throttle, out.brake), (Mode::Rc, 0.0, 1.0));
        assert!(out.steering_target > 0.0, "the stick still steers");
    }

    #[test]
    fn status_frame_round_trips() {
        let mut car = Car::new();
        car.arm();
        let out = car.drive(1.0, 0.1, true, 5);
        let frame = car.spine.status_frame(&out);
        let back = VehicleStatus::decode(&frame).unwrap();
        assert_eq!(back.mode, Mode::Computer);
        assert!(back.armed);
    }

    // --- Open-loop commands (the 2025-26 UART link) and no wheel speed ---

    fn direct(throttle: f32, brake: f32, steering: f32) -> DirectCmd {
        DirectCmd {
            throttle,
            reverse: false,
            brake,
            steering_angle: steering,
            stop: brake > 0.0,
        }
    }

    impl Car {
        fn send_direct(&mut self, cmd: DirectCmd, ticks: u32) -> Outputs {
            let mut last = None;
            for _ in 0..ticks {
                last = Some(self.tick(Inputs {
                    direct_cmd: Some(cmd),
                    ..Default::default()
                }));
            }
            last.unwrap()
        }
    }

    #[test]
    fn direct_commands_need_a_stop_first() {
        let mut car = Car::new();
        // A drive frame straight after boot does nothing...
        let out = car.send_direct(direct(0.5, 0.0, 0.0), 5);
        assert_eq!((out.mode, out.throttle), (Mode::Manual, 0.0));
        // ...until a stop frame (the arming edge's first half), then a drive frame.
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        let out = car.send_direct(direct(0.5, 0.0, 0.0), 1);
        assert_eq!(out.mode, Mode::Computer);
        assert_eq!((out.throttle, out.brake), (0.5, 0.0));
    }

    #[test]
    fn direct_commands_pass_through_inside_limits() {
        let mut car = Car::new();
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        let out = car.send_direct(direct(3.0, 0.0, 0.0), 1);
        assert_eq!(out.throttle, 1.0); // clamped to 0..1
                                       // The brake wins over the throttle, and the stop frame's brake passes as it is.
        let out = car.send_direct(direct(0.5, 0.4, 0.0), 1);
        assert_eq!((out.throttle, out.brake), (0.0, 0.4));
        assert_eq!(out.mode, Mode::Computer); // a stop frame still counts as fresh
                                              // Reverse passes through.
        let mut cmd = direct(0.2, 0.0, 0.0);
        cmd.reverse = true;
        let out = car.send_direct(cmd, 1);
        assert!(out.reverse && out.throttle == 0.2);
    }

    #[test]
    fn direct_steering_is_rate_limited_and_capped() {
        let mut car = Car::new();
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        let out = car.send_direct(direct(0.0, 0.0, 2.0), 1);
        let cfg = SpineConfig::default();
        assert!(out.steering_target <= cfg.max_steer_rate * 0.01 + 1e-6);
        let out = car.send_direct(direct(0.0, 0.0, 2.0), 300);
        assert_eq!(out.steering_target, cfg.max_steering_angle);
    }

    #[test]
    fn direct_commands_time_out_into_a_full_stop() {
        let mut car = Car::new();
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        car.send_direct(direct(0.5, 0.0, 0.0), 1);
        let mut out = car.tick(Inputs::default());
        for _ in 0..25 {
            out = car.tick(Inputs::default());
        }
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
        assert_ne!(out.faults & faults::CMD_TIMEOUT, 0);
        // Drive frames alone don't restart it: a stop frame must come first.
        let out = car.send_direct(direct(0.5, 0.0, 0.0), 3);
        assert_eq!(out.throttle, 0.0);
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        assert_eq!(car.send_direct(direct(0.5, 0.0, 0.0), 1).throttle, 0.5);
    }

    #[test]
    fn rc_and_estop_beat_direct_commands() {
        let mut car = Car::new();
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        car.send_direct(direct(0.5, 0.0, 0.0), 1);
        let out = car.tick(Inputs {
            direct_cmd: Some(direct(0.5, 0.0, 0.0)),
            hw_estop: true,
            ..Default::default()
        });
        assert_eq!((out.throttle, out.brake), (0.0, 1.0));
        let mut car = Car::new();
        car.send_direct(direct(0.0, 1.0, 0.0), 1);
        let out = car.tick(Inputs {
            direct_cmd: Some(direct(0.5, 0.0, 0.0)),
            rc: Some(RcInput {
                override_switch: true,
                throttle: 0.0,
                steering: 0.0,
                brake: false,
            }),
            ..Default::default()
        });
        assert_eq!((out.mode, out.throttle), (Mode::Rc, 0.0));
    }

    fn open_loop_config() -> SpineConfig {
        SpineConfig {
            speed_feedback: SpeedFeedback::None {
                full_throttle_speed: 3.0,
            },
            ..SpineConfig::default()
        }
    }

    #[test]
    fn without_a_wheel_speed_the_throttle_follows_the_setpoint() {
        let mut car = Car::with_config(open_loop_config());
        car.arm();
        // 1.5 m/s of 3.0: the setpoint ramps at 1.5 m/s^2, so after 1.5 s it is there.
        let out = car.drive(1.5, 0.0, true, 200);
        assert_eq!(out.mode, Mode::Computer);
        assert!((out.throttle - 0.5).abs() < 1e-3, "{}", out.throttle);
        assert_eq!(out.brake, 0.0);
        // Back to zero: the throttle falls with the setpoint, then the hold brake.
        let out = car.drive(0.0, 0.0, true, 200);
        assert_eq!(out.throttle, 0.0);
        assert_eq!(out.brake, SpeedLoopConfig::default().hold_brake);
    }

    #[test]
    fn without_a_wheel_speed_there_is_no_overspeed() {
        let mut car = Car::with_config(open_loop_config());
        let out = car.tick(Inputs {
            measured_speed: 20.0,
            ..Default::default()
        });
        assert_eq!(out.faults & faults::OVERSPEED, 0);
    }
}
