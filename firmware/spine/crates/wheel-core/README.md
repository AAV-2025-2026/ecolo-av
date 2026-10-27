# wheel-core

## Overview

The CAN wheel nodes' logic: Hall sensor pulses in, wheel speed and the WHEEL_SPEED
CAN frame out. Plain `no_std` Rust with no hardware access, like `spine-core`: a
board crate would own the pin, the clock and the CAN driver.

```text
 Hall sensor edge ──► WheelNode::on_pulse(now_us)
 every 10 ms      ──► WheelNode::frame(now_us, direction) ──► [u8; 8] onto the CAN bus
```

A node counts the holes of the front brake rotor as they pass a Hall sensor, and sends
WHEEL_SPEED_L (0x200) or WHEEL_SPEED_R (0x201) every 10 ms (`firmware/can/aav.dbc`,
`docs/can-plan.md`).

**Who sends those frames today.** The plan (KEFC) had an ESP32-CAN-X2 per wheel,
running this crate. Since 23 Oct the hardware lead's Arduino sends them
instead, in Arduino C++ (the hardware lead's choice). So no board uses this crate yet (`boards/esp32s3-wheel` was
never written). It still pins down what a correct WHEEL_SPEED frame is.

## Interface

| Item | Does |
|---|---|
| `WheelConfig { holes_per_rev, wheel_radius, zero_speed_timeout_ms, min_pulse_gap_us }` | one wheel's settings, measured on the car (radius in m) |
| `WheelConfig::metres_per_pulse()` | 2π × radius ÷ holes (m) |
| `WheelConfig::slowest_speed()` | the slowest speed that still reads as moving (m/s) |
| `WheelNode::new(wheel, cfg)` | a node for `Wheel::Left` or `Wheel::Right`; a bad setting is a `ConfigError` |
| `on_pulse(now_us)` | one Hall edge; false if ignored as noise |
| `speed(now_us)` | the tyre's speed over the ground (m/s), 0 or more |
| `pulse_count()` | pulses so far; wraps at 65536, as in the frame |
| `frame(now_us, direction)` | the next 8-byte WHEEL_SPEED frame, with its 4-bit counter |
| `wheel()`, `config()` | what it was made with |
| `Direction` | `Forward`, `Reverse`, for a board that can tell |
| `ConfigError` | `NoHoles`, `BadRadius`, `BadTimeout` |
| `FRAME_PERIOD_MS` | 10 (100 Hz) |

It takes the frame (`protocol::WheelSpeed`) and the speed from pulse timing
(`encoder::SpeedEstimator`) from [`spine-core`](../spine-core/README.md).

## Invariants

- `no_std`, no allocator, no hardware access.
- The settings come from the board crate, not ROS: calibration belongs in the
  firmware.
- Times are a free-running microsecond clock that may wrap (every 71 minutes). The
  timeout must be under half its range.
- Speed is in m/s and never negative from one Hall sensor. With `direction: None`
  the frame says the direction is unknown, and the receiver takes the sign from the
  drive direction.
- No pulse for `zero_speed_timeout_ms`: the wheel reads as stopped.
- Pulses closer than `min_pulse_gap_us` are noise and don't count.
- The frame layout and IDs are `aav.dbc`'s, through `spine-core`'s protocol.

## Side Effects

None. It returns the frame's bytes; a board would put them on the CAN bus.

## Verification

```sh
cd firmware/spine
cargo test -p wheel-core     # 9 tests
```
