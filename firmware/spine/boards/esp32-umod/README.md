# spine-esp32-umod

The spine on today's control board: the SparkFun ESP32 MicroMod (the original ESP32,
Xtensa) on the AAV carrier, beside the Motor-Pi. The Rust replacement for
`firmware/legacy/aav_umod_esp32`. **Never flashed yet.** The C++ stays until this is proven
on the car.

## What it does

| Part | How |
|---|---|
| The brain | `spine-core`, every 10 ms |
| The devices | `spine-board`: two Jrk G2s, the DAC, the PCA9555, on I2C 21/22 at 100 kHz |
| Commands | the Motor-Pi's 13-byte frames on GPIO16 (default), or CAN on TWAI (`can`) |
| RC override | iBUS on GPIO32 |
| Speed | none on this board: open loop |
| Watchdog | TIMG1, 100 ms |
| Log | the USB cable: a `STATUS` line every 200 ms |

The pin map is `src/pins.rs` (and `docs/rust-firmware.md`).

## Features

| Feature | Use |
|---|---|
| `legacy-uart` (default) | today: a drop-in for the C++, with `aav_legacy` |
| `can` | the KEFC plan: `firmware/can/aav.dbc`. Its pins are unknown: see `src/pins.rs` |
| `estop-input` | the e-stop's spare contact on GPIO27, once wired (Q6) |

## Build and flash

```sh
pixi run esp-tools        # once: Espressif's Rust, espup, espflash (needs rustup)
pixi run esp-build        # or: --no-default-features --features can
pixi run esp-flash        # bench only, wheels off the ground: docs/esp32-bench.md
```

It is a workspace of its own: it builds only for `xtensa-esp32-none-elf`, with the `esp`
toolchain (`rust-toolchain.toml`). `tools/test.sh` builds both links, with clippy, where
that toolchain is installed.

## Settings

In `src/main.rs`:

| Constant | Set to | Why |
|---|---|---|
| `TICK`, `WATCHDOG_MS` | 10 ms, 100 ms | as the Pico 2 program; `spine-core` expects them |
| `I2C_KHZ` | 100 | as the C++ |
| `FULL_THROTTLE_SPEED` | 3.0 m/s | the open loop's scale; `legacy.yaml`'s guess (Q4) |
| `IDLE_BRAKE` | 1.0 | the C++ kept the brake on while nobody drives; Ben decides |

What differs from the C++, and what Ben must decide: `docs/rust-firmware.md`.
