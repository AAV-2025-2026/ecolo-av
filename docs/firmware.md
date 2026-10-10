# Firmware: the spine, its CAN contract, and today's ESP32

## `src/` vs `firmware/`

- **`src/`** holds ROS 2 packages. They run on the Linux computers: the Orin, the Pis and
  laptops.
  - Some are **drivers in the ROS sense**: they open a USB or serial device, parse its
    protocol and publish standard messages. Examples are `yahboom_imu_cpp` (the IMU over
    USB serial), `ublox_dgnss` (GPS) and `ti_ros2_driver` (radar).
  - So yes, there is hardware code in `src/`, but only for devices that plug into a Linux
    computer.
- **`firmware/`** holds code for microcontrollers (ESP32, Pico 2). There's no Linux and no
  ROS there.
  - Firmware owns the pins, the I2C actuator drivers, the RC receiver, the e-stop input
    and the timing-critical loops.
  - It reaches ROS only through a bridge node in `src/`: CAN to `aav_spine`, or today
    UART to `aav_legacy`.

Pins, I2C addresses and calibration never appear in ROS. ROS only knows device names,
like `can0` and `/dev/aav/imu`.

### Defined interfaces with several implementations

The pattern is already how ROS works: **the interface is the message type, the topic
name and the frame.**

| Interface | Implementations today |
|---|---|
| `/imu/data_raw`: `sensor_msgs/msg/Imu` in `imu_link`, gyro + accel with covariances | `yahboom_imu_cpp`, `gazebo_adapter`. Any other IMU driver that publishes the same thing drops in, and nothing downstream changes. |
| `/gps/fix`: `sensor_msgs/msg/NavSatFix` in `gps_link` | `ublox_nav_sat_fix_hp`, `gazebo_adapter`; `nmea_navsat_driver` would also fit |
| The backend contract: `/ego/actuator_cmd` in, `/vehicle/odom` (and `/vehicle/status`) out | `spine_bridge`, `legacy_uart_bridge` + `encoder_udp`, `turtlesim_adapter`, `gazebo_adapter`, `carla_adapter` |

Inside the firmware, the same idea applies at a lower level:
- Rust's `embedded-hal` traits (I2C, SPI, GPIO, delays) are the standard hardware
  interface, and device drivers are written against them.
- `spine-core` goes one step further and has no hardware access at all. The board code
  reads the hardware into a plain `Inputs` struct, calls `Spine::step`, and writes the
  returned `Outputs` to the hardware. So the logic is tested on a laptop, and swapping a
  motor driver changes only board code.

## The spine

The spine is the microcontroller between the Orin and the actuators. It replaces today's
chain of Motor Pi → UART → ESP32. Its jobs:
- receive drive commands over CAN, and refuse them unless armed;
- run the speed loop (target speed in, throttle/brake/direction out) and drive steering
  to the target angle;
- read the wheel encoder, and report speed, steering angle, mode and faults;
- give the RC transmitter's override switch and the hardware e-stop priority over the
  computer;
- stop by itself when commands stop: a 200 ms watchdog.

Priorities, highest first, from `spine-core/src/spine.rs`:
1. **Any e-stop** (the hardware input or `ESTOP_CMD`): throttle off, full brake.
2. **The RC transmitter**, while its override switch is on.
3. **The computer**, while armed and sending fresh `DRIVE_CMD` frames.
4. **Otherwise manual:** the actuators are idle.

After an e-stop, or after the commands stop while the computer was driving, the computer
must re-arm before it can drive again: a frame with `armed = 0`, then `armed = 1`.
`spine_bridge` does this when you call `/spine/arm`. A glitch never restarts the car by
itself.

## The CAN contract: `firmware/can/aav.dbc`

- **Bus:** classic CAN at 500 kbit/s, with 11-bit IDs.
- **Signals:** little-endian, physical value = raw × scale.
- **Checks:** every frame ends with a CRC-8 (SAE-J1850) over the ID and data, plus a
  4-bit rolling counter per ID. A frame with a bad CRC or counter is rejected, and its
  fault bit is set.

| ID | Frame | From → to | Rate | Signals |
|---|---|---|---|---|
| 0x010 | `ESTOP_CMD` | Orin → spine | 10 Hz, and at once on change | `estop_request` (latched until 0 and re-armed) |
| 0x100 | `DRIVE_CMD` | Orin → spine | 50 Hz while ego is fresh | `target_speed` (0.001 m/s), `steering_angle` (0.0001 rad, + left), `accel_limit`, `steer_rate_limit`, `armed` |
| 0x180 | `VEHICLE_FEEDBACK` | spine → Orin | 50 Hz | `measured_speed`, `measured_steering_angle`, `wheel_ticks` |
| 0x181 | `VEHICLE_STATUS` | spine → Orin | 10 Hz | `mode` (manual / RC / computer), `armed`, `estop_active`, `throttle` %, `brake` %, `faults` (bits, as in `VehicleStatus.msg`) |

One definition, three implementations, kept in step by generated test vectors:
- `firmware/can/aav.dbc`: the source of truth. A CAN tool such as SavvyCAN or cantools
  can open it to decode a live bus.
- `src/backends/aav_spine/aav_spine/can_codec.py`: the ROS side.
- `firmware/spine/crates/spine-core/src/protocol.rs`: the firmware side.
- `firmware/can/gen_test_vectors.py`: writes the same frames from the Python codec into
  `test_vectors.json` (for Python's tests) and `tests/vectors.rs` (for `cargo test`).
  If either side drifts, its tests fail.

To change a frame:
1. Edit the DBC.
2. Edit both codecs.
3. Run `python3 firmware/can/gen_test_vectors.py`.
4. Run `tools/test.sh`.

## `firmware/spine/`: the Rust firmware

`crates/spine-core` is plain `no_std` Rust, with no allocator, no dependencies and no
hardware access. `cargo test` runs it on any laptop (43 tests).

| Module | Does |
|---|---|
| `spine.rs` | The mode logic above. `Spine::step(&Inputs) -> Outputs`, about 100 times a second. Also builds the feedback and status frames. |
| `protocol.rs` | Encode and decode the four frames, with the CRC and counter checks |
| `watchdog.rs` | The 200 ms command watchdog |
| `speed_loop.rs` | PI speed control into throttle, brake and direction. Throttle and brake are never both on. It holds the brake while stopped. The gains are starting points to tune. |
| `limits.rs` | Clamping and slew-rate limits |
| `encoder.rs` | Quadrature decoding (bounce-proof transition table) and speed from the time between counts, so it stays smooth at walking pace |

Firmware limits sit under ego's. Defaults are in `SpineConfig::default()`:
- 3.0 m/s forward and 1.0 m/s reverse;
- steering ±0.5 rad;
- 1.5 m/s² acceleration;
- 0.6 rad/s steering rate.

### The board crate (not written yet)

The ESP32 program that owns the hardware and calls `spine-core`. It isn't a workspace
member, because it needs Espressif's toolchain. Each tick it must:
1. read CAN (the ESP32's built-in TWAI controller, through a 3.3 V CAN transceiver), the
   iBUS receiver, the encoder inputs and the hardware e-stop into `Inputs`;
2. call `spine.step(&inputs)`;
3. write `Outputs` to the actuators, and send `VEHICLE_FEEDBACK` at 50 Hz and
   `VEHICLE_STATUS` at 10 Hz.

Hardware facts from today's firmware (`firmware/legacy/aav_umod_esp32/src/modules/hardware_configs.h`):

| Part | Interface | Today's setting |
|---|---|---|
| Steering: Pololu Jrk G2 | I2C, address 0x05 | targets roughly 0–3500. The calibrations disagree (Q2): measure before porting. |
| Brake: Pololu Jrk G2 | I2C, address 0x04 | targets 400–3500 |
| Throttle: 10-bit DAC | I2C, address 0x0C | capped at 700 of 1023, ramped up 6 and down 12 per step |
| Direction (forward/reverse) | PCA9555 I/O expander, I2C 0x20 | |
| I2C bus | SDA GPIO 21, SCL GPIO 22 | |
| RC receiver: FlySky FS-iA6B | iBUS on GPIO 32 (RX), 115200 baud | channels: 5 override, 2 throttle, 3 steering, 4 drive mode |

Getting started with Rust on the ESP32:
1. `cargo install espup espflash && espup install`.
2. Generate a project with `esp-generate`.
3. Add `spine-core = { path = "../crates/spine-core" }`.
4. Build and flash with `cargo run --release`, which uses `espflash` over USB.

The `esp-hal` CAN (TWAI) driver was marked unstable as of 2025, so check its status
first. The fallback is C++ on the same contract: the DBC and the test vectors don't care
what language produced the bytes.

## Today's firmware: `firmware/legacy/`

Copied unchanged from the 2025-26 repositories, as a reference and as the fallback until
the spine exists.

| Folder | What | How it talks |
|---|---|---|
| `aav_umod_esp32/` | ESP32 (SparkFun MicroMod) actuator firmware: steering, brake, throttle, direction, RC override. From AAV_cortex branch `6-pico2-aav-firmware`. | UART from the Motor Pi: 13-byte frames (three float32s plus a checksum), driven by `aav_legacy`'s `legacy_uart_bridge`. Also WiFi, a web page and OTA updates. |
| `wheel_encoder_pico2/` | Pico 2 + W5500 Ethernet. Two IR sensors on an 8-spoke wheel. | UDP to port 10111: a signed count every ~100 ms. `aav_legacy`'s `encoder_udp` turns it into `/vehicle/odom`. |
| `aav_sentinel_pico2/` | Pico 2 status display (LCD) | not wired into the new stack |

### Known hazards: read before driving the legacy path

1. **No command timeout in the ESP32.** If frames stop, because the bridge, the Pi or the
   cable dies, **the last throttle stays on.**
   - `legacy_uart_bridge` sends brake frames when ego goes quiet or `/estop` is true, but
     it can't protect against its own death.
   - Add a timeout in the firmware (`ros2_handler.cpp`) before any test with the wheels on
     the ground. Until then: wheels off the ground, and the e-stop in hand.
2. **The OTA update page (`/update`) has no password.** Anyone on the WiFi can flash the
   car. Disable it or protect it.
3. **No feedback.** The ESP32 sends nothing back: no speed, no steering, no faults. Speed
   comes from the separate encoder, and the steering angle is unmeasured.
4. **Steering sign and calibration are unconfirmed.** `legacy.yaml` assumes +1 steers
   right (`steering_sign: -1`), from the 2025-26 joystick config. Check it with the wheels
   up.
5. **Open-loop throttle.** Speed maps to throttle through `full_throttle_speed` (a guess,
   3 m/s). Measure it.
6. **WiFi credentials.** They were removed from `main.cpp` and are now read from an
   untracked `secrets.h` (copy `secrets.h.example`). The old values are public in the
   2025-26 repositories, so change the router password.

## Still to decide for the spine

Open questions Q10–Q17 in the design doc:
- the spine's owner;
- which microcontroller;
- the CAN transceiver and wiring;
- where the encoder and the hardware e-stop connect;
- steering feedback (a sensor, or the Jrk G2's own feedback);
- what the actuators do when nobody drives (`idle_brake`).
