# Audit, 10 October 2026: Firmware contract and diagram status

A read-only audit by a Claude Code agent, kept as it reported. Line numbers are from the tree at the time; fixes are tracked in `TODO.md`.

I found two arming bugs to fix before anyone writes firmware, but otherwise the answer is mostly yes: the CAN contract is complete and consistent. I didn't change anything under /home/ben/aav. My scratch work is in /tmp/aav_fwaudit/.

**1. Verdict**

Mostly yes. These all agree on every ID, frame length (DLC), bit, scale, sign, byte order, CRC and counter:
- aav.dbc
- can_codec.py
- protocol.rs
- test_vectors.json
- an independent parse with cantools, plus my own CRC check

Both test suites pass: `cargo test --offline` (34+9), and the aav_spine pytest (10 passed). What isn't ready is behaviour at the edges: two arming bugs (B1, B2) and three wrong behaviours (W1–W3), all small fixes in existing code. The board crate doesn't exist yet, and the hardware decisions it needs (section 4) are still open. None of them stops a board-crate skeleton tested with mocks; fix B1 and B2 first so the firmware isn't written against the wrong arming rules. I confirmed B1, B2 and W1–W3 by feeding the real spine_bridge.py (ROS stubbed out, fake clock) into the real spine-core.

**2. Contract inconsistencies**

BREAKS
- **B1. `/spine/arm` does nothing after a hardware e-stop or a watchdog trip.** spine_bridge.py:87 only sends the armed 0→1 edge if its own flag is false. The bridge can't see those latches, so the call answers "armed" and the spine stays latched; in the replay it was still MANUAL a second later. docs/firmware.md:61 says this works. Fix: change spine_bridge.py:87 to `if request.data:`.
- **B2. A spine reset starts driving again by itself.** `Spine::new` starts unlatched with `seen_disarm=true` (spine.rs:147-149). With armed=1 frames still arriving, the car was back in COMPUTER mode 10 ms after a reboot. That contradicts spine.rs:11 ("a glitch never restarts the car"). Fix: start with `latched: true, seen_disarm: false`, make the test at spine.rs:383 send armed=0 first, and add a boot test.

WRONG
- **W1. A stale command keeps the car moving for 500 ms, not 200 ms.** The bridge re-sends the last ego command with fresh counters until it is 0.3 s old (spine.yaml:5, spine_bridge.py:107-125); only then does the 200 ms watchdog start. In the replay, ego's last message was at 0.98 s and full brake came at 1.48 s. Fix: set `cmd_timeout: 0.06`, or send DRIVE_CMD from `on_cmd()` instead of a timer. The 20 ms period itself is fine: 10 frames per watchdog window.
- **W2. Driver faults never stop the car.** The fault bits are only reported (spine.rs:218); a stop happens only for e-stop, RC loss or overspeed (spine.rs:234). With WHEEL_ENCODER set and 0 m/s measured, throttle climbed to 0.53 in 3 s, and overspeed can't trip on a dead encoder. Fix: treat STEERING_DRIVER, BRAKE_DRIVER, THROTTLE_DAC and WHEEL_ENCODER as a stop that latches like a timeout.
- **W3. The firmware brakes more gently than ego asks.** `max_accel` 1.5 limits both speeding up and slowing down (spine.rs:59, 273, 284), but ego slows at 2.0 (ego.yaml:11). In the replay, ego was at 0 after 0.5 s while the spine's setpoint was still 0.25 m/s. That breaks "firmware limits sit under ego's" (docs/firmware.md:108). Fix: add a `max_decel` of at least 2.5 to SpineConfig.

NOTE
- ESTOP_CMD's counter is never checked and it has no timeout (spine.rs:173-175), yet docs/firmware.md:69 says bad counters are rejected.
- FAULT_BAD_COUNTER says "repeated or skipped" (VehicleStatus.msg:25), but the firmware only flags repeats (spine.rs:177).
- The bridge checks neither the spine's counters nor how old its feedback is (spine_bridge.py:135+), so a frozen or silent spine goes unnoticed.
- The DBC has no cycle-time attributes (cantools reads none) and no comment on `estop_active`, which also covers the watchdog latch (spine.rs:242).
- The sign and units of `wheel_ticks` aren't defined (aav.dbc:86), and the bridge ignores it.
- `max_steering_angle` lives in two places: vehicle.yaml:21 and spine.rs:58.
- Broken references: the README.md named in firmware/spine/Cargo.toml:4 doesn't exist, and neither does docs/status.md (README.md:21, CLAUDE.md:6).

Regenerating the test vectors into /tmp gives byte-identical files.

**3. One interface, several drivers**

ROS side, now: this already follows Ben's idea. `/imu/data_raw` (sensor_msgs/Imu, frame `imu_link`, with covariances, no orientation) comes from yahboom_imu_cpp (imu_node.cpp:40, 117-127) or from gazebo_adapter (gazebo_adapter.py:90-96). The Madgwick filter then makes `/imu/data` for both, so the driver seam is `/imu/data_raw`, not `/imu/data`. The gap is that the contract is only prose; nothing checks it.

Firmware side, now: spine-core has no traits. Its seams are plain structs: `Inputs` (spine.rs:82), `Outputs` (:104), `RcInput` (:71) and `Spine::step` (:160). Drivers are left to the unwritten board crate (lib.rs:3-7).

The smallest proposal. I prototyped it in /tmp/aav_fwaudit/proposal; it compiles as `no_std` against unmodified spine-core and 3 mock tests pass.
- **spine-core/src/hw.rs:** one trait per device kind. All methods take `&mut self`, and `DriverError` is a unit struct.

| Trait | Methods |
|---|---|
| `CanBus` | `receive() -> Option<(u16,[u8;8],usize)>`, `transmit(id: u16, data: &[u8]) -> bool`, `healthy() -> bool` |
| `Steering` | `set_angle(rad: f32) -> Result<(), DriverError>`, `angle() -> Result<f32, DriverError>` |
| `Brake` | `set(level: f32) -> Result<(), DriverError>` |
| `Throttle` | `set(level: f32, reverse: bool) -> Result<(), DriverError>` |
| `WheelSpeed` | `speed(now_ms: u32) -> f32`, `ticks() -> u16` |
| `RcReceiver` | `read(now_ms: u32) -> Option<RcInput>` |
| `EstopInput` | `pressed() -> bool` |

- **spine-core/src/board.rs:** `Board<C,S,B,T,W,R,E>::tick(&mut self, spine: &mut Spine, now_ms) -> Outputs`. Each tick it reads the bus and devices into `Inputs` (newest DRIVE_CMD; any stop request wins), calls `step`, and writes the outputs. It turns driver errors into the matching fault bits and sends feedback every 2nd tick and status every 10th.
- **spine-core/src/mock.rs** (behind `cfg(any(test, feature="mock"))`): MockCan, MockSteering { target, fail }, MockLevel, MockWheel, MockRc, MockEstop.
- **Board crate:** supplies the real drivers, each generic over embedded-hal 1.0 I2C: Jrk G2 for Steering and Brake, DAC + PCA9555 for Throttle, the IR sensors for WheelSpeed, iBUS for the RC receiver, TWAI for CAN.
- **IMU:** there's none on the spine, so no firmware IMU trait yet. If one moves there, add `Imu::read() -> Result<ImuSample, DriverError>` and a CAN frame; the bridge republishing `/imu/data_raw` would then be a third implementation of the same ROS contract.
- **ROS side:**
  - add `frame:` and `rate_hz:` to the sensor topics in interfaces.yaml;
  - add a no-ROS `tools/contracts.py` with `imu_raw_problems(msg) -> list[str]`, tested against a fake message;
  - have check_graph.py sample one message per sensor topic and run it.

**4. Still undefined for whoever writes the ESP32 firmware**
- [ ] **The board crate itself.** Cargo.toml says it's "generated separately", but the README it points to is missing, and the license is "TODO" (Cargo.toml:12).
- [ ] **MCU and toolchain (Q10–Q17).** Today's board is a classic ESP32 (platformio.ini:13, Xtensa), which needs the target `xtensa-esp32-none-elf` installed through espup. An ESP32-C3 or C6 would use the standard rustup targets `riscv32imc` or `riscv32imac-unknown-none-elf`. This machine has only the x86_64 stable toolchain. esp-hal's CAN (TWAI) driver is behind its unstable feature.
- [ ] **Pin map.** Undefined: TWAI TX/RX, encoder A/B (the encoder is on the Pico today), the hardware e-stop input and its polarity (the legacy firmware has none), LEDs. Known from hardware_configs.h:
  - I2C on SDA 21 / SCL 22;
  - Jrk steering at 0x05, Jrk brake at 0x04;
  - 10-bit DAC at 0x0C (its format looks like an AD5311; confirm the part);
  - PCA9555 at 0x20, P00 = direction, HIGH = forward;
  - iBUS on GPIO 32.
- [ ] **CAN wiring:** transceiver part, termination, connector, and the Orin end. Only the 500 kbit/s rate is decided.
- [ ] **Calibrations:**
  - radians to steering Jrk target (hardware_configs.h:28-36 gives centre 1950, 500 and "~1000"; Q2);
  - brake 0..1 to Jrk 400..3500;
  - throttle 0..1 to DAC 0..700 with a ramp;
  - metres per encoder count.
- [ ] **Steering feedback:** where `measured_steering_angle` comes from (the Jrk's own feedback, or a separate sensor).
- [ ] **Faults:** a detection rule per fault bit, and what each fault does (W2).
- [ ] **RC:**
  - The IBusBM library numbers channels from 0, so 5, 2, 3, 4 are transmitter channels CH6, CH3, CH4, CH5.
  - Loss detection: the library keeps stale values, so set transmitter failsafe values plus an iBUS timeout.
  - The legacy firmware drives RC open-loop with a gear switch; spine-core drives it closed-loop on the encoder.
  - Releasing the override hands control back to the computer without a re-arm (spine.rs:208-216). Decide whether that's wanted.
- [ ] **Boot:** safe outputs before CAN starts, the boot latch (B2), an MCU hardware watchdog, and what cuts the throttle if the MCU hangs (the DAC holds its last value).
- [ ] **Idle brake:** `idle_brake` is 0, so releasing an e-stop lets the brake go, while a watchdog trip holds full brake (spine.rs:246 vs 254-257).
- [ ] **Config/version frame:** there's none; SpineConfig is compiled in. Decide whether that stays.

**5. Legacy path**

Matches:
- **UART:** `/dev/ttyAMA0` at 115200 8N1 (legacy.yaml:5-6). That's the same as the 2025-26 Pi bridge (AAV_cortex uart_bridge.py:15-16) and the ESP32's Serial1 on GPIO 16/17 (main.cpp:93).
- **Frame:** three little-endian float32s plus a byte-sum checksum (ros2_handler.cpp:17-27 = legacy_protocol.py:63-65), clamped to ±1.
- **Units:** as legacy_protocol.py documents.
- **Encoder:** UDP port 10111, a 4-byte big-endian int32 about every 100 ms, 8 counts per revolution.
- **Firmware copy:** our ESP32 copy is byte-identical to its source branch.

Problems:
- **WRONG, steering:** the gain differs by side. Negative values use 1950 counts per unit and clip at −0.795; positive values use 1550 (ros2_handler.cpp:35-38, jrk_g2.cpp:16). With `steering_sign` −1, left gets 26% more lock than right. Fix: scale negative values by 1550/1950 in `to_legacy`.
- **WRONG, encoder address:** the Pico sends only to 192.168.1.193 (wiznet.ino:19), but orin.yaml:17 runs `encoder_udp` on the Orin.
- **WRONG, missing packets:** `encoder_udp` publishes 0 m/s when no packets arrive (encoder_udp.py:56-73), so the EKF thinks the car is parked. It should stop publishing after about 0.3 s of silence and log it.
- **NOTE, brake scale:** brake values below 0.114 mean "released".
- **NOTE, throttle ramp:** the DAC ramps once per frame (dac.cpp:31-42), so `rate_hz` sets the throttle ramp.
- **NOTE, encoder Pico:** `while (!Serial)` at wiznet.ino:82 probably blocks unless a USB host is connected.
- **NOTE, Pi UART:** on a Pi 3/4, `ttyAMA0` is the Bluetooth UART; `/dev/serial0` is safer.

**6. Diagram status**

Evidence: tonight's test runs, ~/.ros/log (only turtle.launch.py has ever run), and pixi.lock.

| Box | Implemented by | Status |
|---|---|---|
| Wheel + steer (spine CAN) | spine_bridge + ros2_socketcan | codec works (tested); node never run (config only) |
| Wheel speed (today) | aav_legacy encoder_udp | decoding tested; node config only |
| IMU | yahboom_imu_cpp + imu_filter_madgwick | config only |
| Car model | aav_description (vehicle.yaml → URDF) | works (4 tests, ran live); numbers are guesses |
| GPS | ublox_dgnss + ublox_nav_sat_fix_hp | config only; the u-blox driver isn't in pixi.lock |
| Lidar / cameras | none | missing |
| ekf_local | robot_localization | works in turtle (wheel odometry only) |
| ekf_global, navsat_transform | aav_localization configs | config only |
| costmap_2d | Nav2 costmaps (nav2.yaml) | config only; no sensor layer enabled |
| Joystick | aav_teleop | config only (e-stop button still TODO) |
| Keyboard | teleop_twist_keyboard (tools/keyboard.sh) | stock; no recorded run |
| Scripted | aav_scripted | works (6 tests, ran live) |
| Nav2 | aav_navigation | config only |
| AI | /cmd_vel/ai reserved | missing |
| twist_mux | stock, aav_mux config | works (ran live) |
| ego | aav_ego | works (14 tests, ran live) |
| Real car | aav_spine | codec tested; node never run |
| Today's car | aav_legacy | protocol tested (9 tests); never run on the car |
| turtlesim | aav_turtlesim | works (ran live, check_graph: 0 failures) |
| Gazebo | aav_gazebo | 2 tests pass; Gazebo has been running since 23:08, probably the launch audit; I didn't check the result |
| CARLA | aav_carla | stub |
| Spine firmware | spine-core | logic works (43 tests); board crate missing |

Another session is restyling files under src/ right now. I re-checked: the logic is unchanged, and the line numbers above match the tree at 23:15.
