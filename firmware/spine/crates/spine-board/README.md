# spine-board

The glue between `spine-core` and the car's devices, for any board. `spine-core`
decides; this crate connects it to the hardware without knowing which chip runs it.
Plain `no_std` Rust.

A board crate (ESP32, Pico 2 or STM32, once the team picks: Q10 to Q13) does three
things:

1. implements the `Board` trait: the clock, the e-stop pin, the wheel counter, CAN;
2. builds a `SpineBoard` from that, its I2C bus and the RC receiver's serial port;
3. calls `init()` once, then `tick()` about 100 times a second.

## One tick

| Step | What |
|---|---|
| 1 | CAN frames in: DRIVE_CMD, ESTOP_CMD, and any bad frame |
| 2 | iBUS bytes from the serial port, to the RC input |
| 3 | the hardware e-stop, debounced: trips at once, releases after 50 ms closed |
| 4 | the wheel counter, to the measured speed |
| 5 | the steering Jrk's feedback, and both Jrks' errors |
| 6 | `Spine::step` |
| 7 | the devices, in a safe order (below) |
| 8 | VEHICLE_FEEDBACK every 20 ms, VEHICLE_STATUS every 100 ms |

The order of the writes, every tick:

| Step | Device | Rule |
|---|---|---|
| 1 | DAC | if the throttle falls: first, so an e-stop's throttle is 0 before the brake comes on |
| 2 | brake Jrk | always |
| 3 | expander | the direction changes only while the DAC is at 0 |
| 4 | DAC | if the throttle rises: last, and only once the brake write worked |
| 5 | steering Jrk | always |

## For the board crate

| Setting | Value |
|---|---|
| I2C | 100 kHz, as today. Faster, and the Jrk needs 100 µs of quiet after each read |
| Bus time | a few ms a tick at 100 kHz: 3 reads, 4 writes, and the Jrks stretch the clock (up to 150 µs a byte) |
| iBUS serial port | 115200 baud, 8N1, receive only |
| CAN | classic, 500 kbit/s, 11-bit IDs (`firmware/can/aav.dbc`) |
| Tick | about every 10 ms; the ramp and the e-stop use the clock, not the tick count |
| E-stop pin | `estop_open()` is true when the loop is open, whatever level that is on the pin |
| Wheel counter | `wheel()` gives the count, and the clock at its latest count |

## API

| Item | Does |
|---|---|
| `Board` | the trait a board implements: `now_ms`, `estop_open`, `wheel`, `can_receive`, `can_send` |
| `CanFrame`, `WheelCount` | what those return |
| `Calibration::TODAY` | today's numbers (below) |
| `Devices::new(steering, brake, dac, expander, &cal)` | the four I2C devices; share one bus with `embedded-hal-bus` |
| `SpineBoard::new(board, devices, uart, cal, config)` | the whole spine |
| `SpineBoard::init()`, `tick()` | power-up, then one pass of the loop |
| `Actuators::apply(&outputs, now_ms)` | drives the devices; returns fault bits |
| `Actuators::read()` | the steering angle and the Jrks' faults |
| `WheelSpeed::update(count, now_ms)` | the speed from the wheel counter |

Faults found here go to `spine-core`, which stops the car until the computer arms again:

| Fault | When |
|---|---|
| `STEERING_DRIVER` | a steering Jrk transfer fails, or it reports an error |
| `BRAKE_DRIVER` | the same, for the brake Jrk |
| `THROTTLE_DAC` | a DAC or expander transfer fails (the direction belongs to the throttle) |
| `CAN_BUS` | a frame can't be sent (doesn't stop the car by itself) |

## Today's numbers

From the 2025-26 firmware. TODO marks an unconfirmed number, with the design doc's
question.

| What | Value | Question |
|---|---|---|
| Addresses | steering 0x05, brake 0x04, DAC 0x0C, expander 0x20 | |
| Steering centre, limits | 1950; 400 to 3500 | Q2 |
| Steering scale | 3100 counts a radian: 1550 counts to full lock, taken as 0.5 rad | Q1, Q2 |
| Steering sign | turning left raises the target | Q2 |
| Brake | 400 released, 3500 full | Q3 |
| Throttle | 0 to 1 is DAC code 0 to 700 (of 1023) | Q4 |
| Throttle ramp | up 600 codes a second; down at once | Q4 |
| Direction | expander P00: high forward, low reverse | Q4 |
| Other expander pins | outputs, high | Q13 |
| Wheel | 0.1178 m a count (8 spokes, 0.30 m wheel) | Q5 |
| RC | `ibus::RcMap::TODAY`; silent after 100 ms | Q7 |
| E-stop input | releases after 50 ms closed | Q6 |

## Test

```sh
cd firmware/spine
cargo test -p spine-board
```

`actuators` is tested transfer by transfer with `embedded-hal-mock`, one mock standing
in for the whole bus, so the order between devices is checked. The loop is tested end
to end on a fake board, a recording I2C bus and a fake serial port (`src/rig.rs`):
e-stops, arming, RC, the CAN frames and their rates, and each fault.

## Ported from

The 2025-26 firmware in `firmware/legacy/aav_umod_esp32/src/` (from AAV_cortex,
commit 90de619e52):

| Here | C++ file | C++ function |
|---|---|---|
| `Actuators::init` | `main.cpp` | `setup()`: the PCA9555, `writeDAC(0)`, steering to `JRK_CENTER`, brake to `JRK_MAX` |
| steering radians to targets, limits | `modules/ros2_handler/ros2_handler.cpp`, `modules/jrk_g2/jrk_g2.cpp` | `handleROS2Messages()`; `setSteer()` clamps to `JRK_MIN`, `JRK_MAX` |
| brake 0 to 1 to targets | `modules/ros2_handler/ros2_handler.cpp`, `modules/rc_handler/rc_handler.cpp` | `handleROS2Messages()`; `handleRCMode()` |
| throttle 0 to 1 to codes | `modules/ros2_handler/ros2_handler.cpp` | `handleROS2Messages()`: `fabsf(speed) * DAC_MAX_CAP` |
| the throttle ramp | `modules/dac/dac.cpp` | `writeDACRamped()`: `ACCEL_STEP` |
| throttle off before the brake | `modules/ros2_handler/ros2_handler.cpp`, `modules/jrk_g2/jrk_g2.cpp` | `handleROS2Messages()`: the "hard cut" when braking; `jrkSafeStop()` |
| the direction pin | `modules/rc_handler/rc_handler.cpp`, `modules/ros2_handler/ros2_handler.cpp` | `ext_digitalWrite(DIR_PIN, ...)` |
| Jrk errors after each target | `modules/jrk_g2/jrk_g2.cpp` | `setSteer()`, `setBrake()`: `getErrorFlagsHalting()` |
| the RC input | `main.cpp`, `modules/rc_handler/rc_handler.cpp` | `loop()`, `handleRCMode()`, through `ibus::RcMap` |

Changed on purpose:

| What | C++ | Here |
|---|---|---|
| Start-up order | expander, DAC, steering, brake | DAC 0, brake, expander, steering: the order of every tick |
| A Jrk missing at start-up | never commanded again, and the car still drives | tried every tick; its fault stops the car |
| Jrk errors, I2C errors | printed, then ignored | fault bits: the car stops |
| Throttle ramp down | 12 codes a loop, except when braking | at once |
| Throttle ramp up | 6 codes a loop | 600 codes a second: 6 a tick at 100 Hz |
| Brake scale | `\|accel\| * 3500`, clamped: nothing below 11 % | straight from 400 to 3500 |
| Changing direction | pin, 1 ms, then the ramped throttle: it could reverse with the throttle on | only with the DAC at 0, and no throttle that tick |
| Throttle with the brake on | RC "brake" ramped the throttle down with the brake full on | the throttle is 0 whenever the brake is on |
| Throttle and brake both asked for | can't happen in spine-core | `debug_assert!` in tests; on the car the brake wins, since a panic would leave the DAC at its last code |
| Steering on an e-stop | centred (`jrkSafeStop()`) | spine-core's `ESTOP_STEERING`: held where it was (proposed), or `Centre` |
| Brake with nobody driving | on (3500) from start-up | spine-core's `IDLE_BRAKE` (0.0): released once the e-stop input clears (proposed; 1.0 keeps it on) |
