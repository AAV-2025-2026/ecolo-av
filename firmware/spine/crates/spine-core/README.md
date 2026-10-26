# spine-core

## Overview

The spine's logic: every decision the spine makes, with no hardware. Plain `no_std`
Rust with no allocator and no dependencies, so the same code runs on the board and in
`cargo test` on a laptop.

The board crate owns the drivers (`spine-board` is the glue). Each tick, about 100 times
a second, it reads them into `Inputs`, calls `Spine::step`, and writes `Outputs` back.

```text
  CAN frames, RC, e-stop pin,    ┌──────────────┐    throttle, brake, direction,
  wheel speed, driver faults ──► │  Spine::step │ ──► steering (rad), mode, faults
            (Inputs)             └──────────────┘          (Outputs)
```

Who drives, highest first:

| # | Who | When |
|---|---|---|
| 1 | nobody: throttle off, full brake | any e-stop (the hardware input or ESTOP_CMD) |
| 2 | the RC transmitter | its mode switch is on RC direct |
| 3 | the computer | armed, and sending fresh commands (RC via ROS counts here) |
| 4 | nobody: the actuators idle | otherwise (manual) |

A driver fault (steering, brake, throttle or encoder) stops the car in any mode.

## Interface

| Module | Item | Does |
|---|---|---|
| `spine` | `Spine::new(cfg)`, `step(&inputs)` | the decisions, one call per tick |
| | `feedback_frame(...)`, `status_frame(&outputs)` | VEHICLE_FEEDBACK (send at 50 Hz), VEHICLE_STATUS (10 Hz) |
| | `mode()`, `speed_setpoint()` | who drives; the rate-limited speed the loop chases (m/s) |
| | `Inputs`, `Outputs` | what the board read; what it writes |
| | `SpineConfig` (and `default()`) | timeout 100 ms, 3.0 m/s, accel 1.5, decel 2.5 m/s², steering 0.6 rad/s... |
| | `DirectCmd` | an open-loop command (throttle, brake, steering), from the UART link |
| | `RcInput`, `RcSwitch` | the sticks, -1..1; the mode switch: `Computer`, `ViaRos`, `Direct` |
| | `SpeedFeedback` | `Wheel` (closed loop) or `None { full_throttle_speed }` (open loop) |
| | `EstopSteering`, `RcGearBrake` | the types of two of the choices below: `Hold`, `Centre`; `SpeedZero`, `FullBrake` |
| | `faults::*` | the fault bits, as `VehicleStatus.FAULT_*`; `faults::STOP` latches |
| `protocol` | `DriveCmd`, `EstopCmd`, `VehicleFeedback`, `VehicleStatus`, `WheelSpeed` | the CAN frames of `aav.dbc`: `encode()`, `decode()` |
| | `decode_incoming`, `decode_report`, `counter_step`, `frame_crc`, `crc8_sae_j1850` | frames by ID; the 4-bit counter; the CRC |
| | `Mode`, `Wheel` | `Manual`, `Rc`, `Computer`; `Left`, `Right` |
| | `Incoming`, `Report` | what `decode_incoming` gives (`Estop`, `Drive`); what `decode_report` gives (`Feedback`, `Status`, `WheelSpeed`) |
| | `FrameError` | `WrongLength`, `BadChecksum`, `UnknownId` |
| | `ESTOP_CMD_ID` … `WHEEL_SPEED_R_ID` | the six IDs in the table below |
| `speed_loop` | `SpeedLoop::update(target, measured, dt)` | a PI with a setpoint weight: a `Drive` (throttle, brake, `reverse`) |
| | `SpeedLoop::open_loop(target, full_throttle_speed)`, `reset()` | throttle in proportion to the target, with no wheel speed; clear the integral |
| | `SpeedLoopConfig` (and `smooth()`), `AntiWindup` | the gains; how the integral is bounded: `Bounds` (today) or `Clamp` |
| | `SpeedLoopProfile`, `UnknownProfile` | named sets (`Default`, `Smooth`) for the sims and car days; parsing a name it doesn't know gives `UnknownProfile` |
| `encoder` | `Quadrature`, `SpeedEstimator` | quadrature decoding; speed from the time between counts |
| `watchdog` | `Watchdog` | trips when no valid command came for its timeout |
| `limits` | `slew`, `abs` | rate limiting |

| CAN frame | ID | Way |
|---|---|---|
| ESTOP_CMD | 0x010 | in |
| DRIVE_CMD | 0x100 | in |
| VEHICLE_FEEDBACK | 0x180 | out |
| VEHICLE_STATUS | 0x181 | out |
| WHEEL_SPEED_L, _R | 0x200, 0x201 | from the wheel sensors (`wheel-core`) |

Also used outside this workspace: `ros/can_bridge/aav_spine_bridge` and
`ros/sim/aav_spine_sim` (bench mode, `pixi run bench`).

## Three choices still open

Each is one constant in `src/spine.rs`, set to what `docs/firmware.md` proposes.
Change one only with the team.

| Constant | Set to | The 2025-26 firmware |
|---|---|---|
| `ESTOP_STEERING` | `Hold`: on any stop, the wheels stay where they are | `Centre` |
| `IDLE_BRAKE` | `0.0`: the brake lets go once the e-stop input clears | `1.0` |
| `RC_GEAR_BRAKE` | `SpeedZero`: the gear switch's brake asks for zero speed | `FullBrake` |

## Invariants

- `no_std`, no allocator, no dependencies, no hardware access.
- REP-103 units: m/s, rad, positive steering left. Throttle and brake 0..1 (percent
  only inside VEHICLE_STATUS).
- The computer can't drive until it sends `armed = 0`, then `armed = 1`: at power-up,
  after an e-stop, after a driver fault, after a command timeout. A glitch or a
  reboot never restarts the car by itself.
- No valid command for 100 ms while driving: stop, full brake, latched
  (`CMD_TIMEOUT`).
- A repeated counter is a stuck sender: not a fresh command.
- A lost RC signal in either RC position brakes (`RC_SIGNAL_LOST`).
- Throttle and brake are never both above zero.
- Reverse never faster than `MAX_REVERSE_SPEED` (0.5 m/s), whoever drives.
  Open-loop UART commands too: with no wheel speed their reverse throttle is capped at
  `max_reverse_speed / full_throttle_speed`; with one, cut while at or over the limit.
- `MAX_STEERING_ANGLE` (0.5 rad) and `MAX_REVERSE_SPEED` copy `vehicle.yaml`;
  `ros/bringup/aav_description/test/test_vehicle.py` checks the copies.
- `protocol` and `ros/can_bridge/aav_spine/aav_spine/can_codec.py` put the same bytes
  on the bus: `tests/vectors.rs` is generated from the Python codec. After any change
  to `aav.dbc`, follow the steps in the root `CLAUDE.md`.
- `speed_loop` and Gazebo's Python port agree on `../../speed_loop_vectors.txt`.

## Side Effects

None. It returns frames as bytes and `Outputs` as numbers; the board sends and drives.

## Verification

```sh
cd firmware/spine
cargo test -p spine-core
```

After changing the CAN frames: `python3 firmware/can/gen_test_vectors.py`, then
`tools/test.sh`. After changing the speed loop: `python3 firmware/spine/gen_speed_loop_vectors.py`.
