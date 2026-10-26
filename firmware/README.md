# firmware

## Overview

Everything that runs on the car's small boards, plus the CAN contract between them and
ROS. New firmware is Rust (`no_std`, Embassy). The 2025-26 team's C++ boards keep
running until each one's Rust version replaces it. The plan: `docs/rust-firmware.md`.

```
ROS (Orin) ──CAN (aav.dbc)── spine board ──I2C── Jrks (steer, brake), DAC (throttle)
          └─UART (Motor Pi)─┘           └─iBUS── RC receiver
```

## Subdirectories & Boundaries

| Folder | What it is |
|---|---|
| [can](./can/README.md) | **the CAN contract**: `aav.dbc` (six frames, 500 kbit/s, CRC-8 and rolling counters) and the generator for the shared test vectors |
| [spine](./spine/README.md) | the Rust workspace: 13 crates (logic like `spine-core`, drivers against `embedded-hal` 1.0) and four board programs |
| [legacy](./legacy/README.md) | the 2025-26 C++ ESP32 board that drives the car today; replaced by `spine/boards/esp32-umod` |
| [udp](./udp/README.md) | hand-written examples of the wheel encoder's 4-byte UDP packet, a contract shared by Rust and Python |

## Invariants

- **The red button always stops the car.** Firmware only reads a spare contact.
- Safe after any reset: throttle 0, latched. Disarm, then arm, to drive again.
- The brake after a reset follows `IDLE_BRAKE`, a team choice (`docs/firmware.md`):
  - `spine-core` sets it to `0.0`, the proposed setting, so the brake lets go on the
    first tick after a reset, unless the board program sets its own;
  - `esp32-umod` sets `1.0` (full on, as the 2025-26 C++ did); `pico2` keeps `0.0`.
- A command older than 100 ms means stop and latch.
- Pins, I2C addresses and calibration live here, never in ROS.
- `aav.dbc` changes follow the root CLAUDE.md: update `can_codec.py` and `protocol.rs`,
  run `gen_test_vectors.py`, run every suite that reads the vectors.
- Logic crates have no hardware and are tested on a laptop.

## Side Effects

- The board programs move the car: I2C to the Jrks, the DAC and the I/O expander.
- CAN, UART, UDP and the RC receiver; flashing a board replaces its program.

## Verification

- Run: `cd firmware/spine && cargo test` (also part of `tools/test.sh` and `pixi run test`).
