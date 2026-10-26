# ros/can_bridge

## Overview

The **real car's backend**: ego's commands go out to the car's boards, and the car's
feedback comes back as `/vehicle/*`. Only one of these runs at a time.

```
/control/car/actuator_cmd ──▶ spine_bridge ──CAN (aav.dbc)──▶ spine board
                         └──▶ legacy_uart_bridge ──UART──▶ 2025-26 ESP32 (today)
```

`spine_bridge` on a stand-in reads `/control/bench/actuator_cmd` or
`/control/gazebo/actuator_cmd` instead (its `source` parameter: `bench` or `sim`).

## Subdirectories & Boundaries

| Package | What it is |
|---|---|
| [aav_spine_bridge](./aav_spine_bridge/README.md) | the default `spine_bridge`, in Rust (rclrs); packs frames with the firmware's `spine-core`. Logic crate: [spine-bridge](./aav_spine_bridge/crates/spine-bridge/README.md) |
| [aav_spine](./aav_spine/README.md) | the Python twin of `spine_bridge`, `arm_when_open`, and `spine.launch.py` (`bridge:=rust|python`) |
| [aav_legacy](./aav_legacy/README.md) | the interim backend for the 2025-26 hardware: `legacy_uart_bridge` (ESP32 over UART) and `encoder_udp` (UDP wheel encoder) |

## Invariants

- CAN ids and layouts come from `firmware/can/aav.dbc`; the codecs share its test vectors.
- Bridges read only the output mux's `/control/<target>/actuator_cmd`, never
  `/ego/actuator_cmd`. On the car that is `/control/car/actuator_cmd`.
- A stale command or an e-stop sends brake frames. How fast:

  | Bridge | Stale after | Board's own watchdog | Car brakes within |
  |---|---|---|---|
  | `spine_bridge` | 0.1 s | 100 ms (spine-core) | 0.2 s |
  | `legacy_uart_bridge` | 0.3 s | none with `frame_version: 1`, the car's setting today | 0.3 s, and only while the bridge runs |
- Arming is refused during an e-stop or while the output mux gate is not OPEN.
- The Python and Rust bridges behave the same, topic for topic.

## Side Effects

- Moves the real car: CAN frames on `can0` (Linux only), or the ESP32's serial port.
- UDP port 10111 for the old wheel encoder.

## Verification

- Run: `pixi run test` (also runs the `spine-bridge` crate's `cargo test`).
