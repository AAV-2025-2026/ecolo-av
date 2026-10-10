# Firmware: the spine and its CAN contract

ROS stops at the CAN bus. Below it, a microcontroller called the spine owns the pins, the
actuators and the watchdog. This page covers what goes where, the CAN contract, and
what's left to build.

## src/ vs firmware/

| | `src/` | `firmware/` |
|---|---|---|
| Runs on | Linux computers: the Orin, the Pis, laptops | microcontrollers: ESP32, Pico 2 |
| ROS? | yes | no |
| Hardware code | only for devices that plug into Linux by USB or serial: the IMU, GPS, radar | pins, I2C actuator drivers, the RC receiver, the e-stop, timing loops |
| Reaches ROS | directly | through a bridge node: CAN to `aav_spine`, or today UART to `aav_legacy` |

ROS never sees a pin or an I2C address, only device names like `can0` and `/dev/aav/imu`.

## One interface, many drivers

In ROS the interface is the message type, the topic and the frame. Any driver that
publishes the same thing drops in, and nothing downstream changes.

| Interface | Implementations |
|---|---|
| IMU: `sensor_msgs/Imu` on `/imu/data_raw`, frame `imu_link` | `yahboom_imu_cpp`, `gazebo_adapter` |
| GPS: `sensor_msgs/NavSatFix` on `/gps/fix`, frame `gps_link` | `ublox_dgnss`, `gazebo_adapter`; `nmea_navsat_driver` would fit |
| Backend: `/ego/actuator_cmd` in, `/vehicle/odom` out | `spine_bridge`, `legacy_uart_bridge`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` |

The firmware applies the same idea one level down. `spine-core` never touches hardware:
the board code fills an `Inputs` struct, calls `Spine::step`, and writes out the
`Outputs`. The logic is tested on a laptop, and changing a motor driver only changes board
code.

## The spine's job

- Take drive commands over CAN, and refuse them unless armed.
- Run the speed loop, and steer to the target angle.
- Read the wheel encoder. Report speed, steering, mode and faults.
- Let the RC override switch and the hardware e-stop beat the computer.
- Stop by itself when commands stop: a 200 ms watchdog.

Who wins, highest first:

| # | Source | When |
|---|---|---|
| 1 | Any e-stop: the hardware button, or the `ESTOP_CMD` frame | always: throttle off, full brake |
| 2 | The RC transmitter | while its override switch is on |
| 3 | The computer | while armed and sending fresh `DRIVE_CMD` frames |
| 4 | Nobody | the actuators idle |

After an e-stop or a timeout, the computer must re-arm (`/spine/arm`) before it can drive
again. A glitch never restarts the car by itself.

## The CAN contract

`firmware/can/aav.dbc` is the source of truth: classic CAN at 500 kbit/s, 11-bit IDs,
little-endian. Every frame ends with a CRC-8 and a 4-bit counter, and a bad one is
rejected.

| ID | Frame | Direction | Rate | Carries |
|---|---|---|---|---|
| 0x010 | `ESTOP_CMD` | Orin → spine | 10 Hz, and at once on change | the e-stop request |
| 0x100 | `DRIVE_CMD` | Orin → spine | 50 Hz | target speed, steering angle, limits, armed |
| 0x180 | `VEHICLE_FEEDBACK` | spine → Orin | 50 Hz | measured speed and steering, wheel ticks |
| 0x181 | `VEHICLE_STATUS` | spine → Orin | 10 Hz | mode, armed, e-stop, throttle %, brake %, faults |

Both sides test against the same generated frames. To change a frame:
1. Edit the DBC.
2. Edit both codecs: `can_codec.py` and `protocol.rs`.
3. Run `python3 firmware/can/gen_test_vectors.py`, then `tools/test.sh`.

## firmware/spine: the Rust code

`crates/spine-core` is plain `no_std` Rust: no allocator, no dependencies, no hardware.
`cargo test` runs its 43 tests on any laptop.

| Module | Does |
|---|---|
| `spine.rs` | the priorities above: `Spine::step(&Inputs) -> Outputs`, about 100 times a second |
| `protocol.rs` | encodes and decodes the four frames, with the CRC and counter checks |
| `watchdog.rs` | the 200 ms command watchdog |
| `speed_loop.rs` | PI speed control into throttle and brake, never both at once |
| `limits.rs` | clamps and slew limits: 3.0 m/s, ±0.5 rad, 1.5 m/s², 0.6 rad/s |
| `encoder.rs` | quadrature decoding, and speed from the time between counts |

The ESP32 board code that calls it is [[missing]]. Hardware facts from today's car:

| Part | Interface | Today's setting |
|---|---|---|
| Steering: Pololu Jrk G2 | I2C 0x05 | targets about 0–3500; the calibrations disagree (Q2) |
| Brake: Pololu Jrk G2 | I2C 0x04 | targets 400–3500 |
| Throttle: 10-bit DAC | I2C 0x0C | capped at 700 of 1023 |
| Direction | PCA9555 expander, I2C 0x20 | |
| I2C bus | SDA GPIO 21, SCL GPIO 22 | |
| RC receiver: FlySky FS-iA6B | iBUS on GPIO 32, 115200 baud | channel 5 override, 2 throttle, 3 steering, 4 mode |

## Today's firmware: firmware/legacy/

Copied unchanged from the 2025-26 team, as the fallback until the spine exists.

| Folder | What | Talks to ROS through |
|---|---|---|
| `aav_umod_esp32/` | the ESP32 actuator firmware | UART from the Motor Pi, 13-byte frames: `legacy_uart_bridge` |
| `wheel_encoder_pico2/` | the Pico 2 wheel encoder | UDP port 10111: `encoder_udp` |
| `aav_sentinel_pico2/` | a Pico 2 status display | not wired in |

!!! warning "Before driving on the legacy path"
  1. **No command timeout.** If frames stop, the last throttle stays on.
  2. **The OTA update page has no password.** Anyone on the WiFi can flash the car.
  3. **No feedback.** No speed, steering or faults come back.
  4. **The steering sign is unconfirmed.** Check it with the wheels off the ground.
  5. **The WiFi password was public** in the 2025-26 repositories. Change it.

## Still to decide

The design doc's questions Q10–Q17:
- who owns the spine, and which microcontroller;
- the CAN transceiver and wiring;
- where the encoder and the e-stop connect;
- steering feedback;
- what the actuators do when nobody is driving.
