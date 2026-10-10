# Rust on the hardware

Ben's direction (10 October 2026): write the firmware and the hardware drivers in Rust,
not C or C++, even where the ROS nodes above stay in Python. The 2025-26 C++ firmware keeps
running today's car until a Rust version replaces each board. This page is the plan, and
what's done so far.

## Why Rust at this level

| Reason | What it means here |
|---|---|
| The same code on the chip and on a laptop | the logic is plain `no_std` Rust, so `cargo test` checks it on any laptop, with no board |
| Mistakes caught when it compiles | no stray pointers, no data races between an interrupt and the main loop |
| One driver for every board | a driver written against `embedded-hal` runs on an ESP32, a Pico, an STM32, and on the Pi under Linux |
| The spine is already Rust | `spine-core`: modes, arming, the watchdog, the speed loop, the CAN frames (48 tests), and the drivers for its devices |

## What runs where

| Hardware | Runs | Rust there |
|---|---|---|
| ESP32, Pico 2 (RP2350), STM32, Arduino | bare metal: no operating system | a HAL for the chip, plus a small framework (below) |
| Raspberry Pi, Jetson Orin | Linux | ordinary Rust programs; drivers reach the pins through `linux-embedded-hal` (or `rppal` on a Pi) |
| Laptops | macOS or Linux | the tests, and the simulated hardware |

Bare metal on a Pi is possible, but it gives up Linux, ROS and the Pi's drivers. The Pi
stays on Linux.

## The layers

![The firmware layers](img/rust-firmware.svg)

| Layer | What it is | Where | Tested by |
|---|---|---|---|
| Logic | the rules: modes, limits, debouncing, the encoder maths | `spine-core`, `aav-inputs` | `cargo test` on a laptop |
| Drivers | one per chip on the car: the Jrk G2 motor controllers, the throttle DAC, the PCA9555 expander, the iBUS radio receiver | `jrk-g2`, `ad5311`, `pca9555`, `ibus`, written against `embedded-hal` 1.0. The W5500 and the display: only if the board keeps them | `embedded-hal-mock`, which plays the chip on a laptop |
| Glue | spine-core's outputs to the devices, the devices to its inputs, in a safe order | `spine-board`, with a `Board` trait for what each chip must provide | `embedded-hal-mock` |
| Boards | one small program per board: pins, timers, the framework, then a loop that calls the glue | one crate per board, implementing `Board` (still to write: it waits on the chip) | on the bench, then on the car |

`firmware/spine/` is the Cargo workspace for the first two layers. Board crates sit beside
it, because each needs its chip's toolchain.

## The framework: the "RTOS" part

| Choice | What it is | Good for |
|---|---|---|
| **Embassy** (suggested) | an async framework for microcontrollers: tasks, timers, drivers that wait without blocking. The usual choice for new Rust projects in 2026 | every board here; it supports the RP2350, the ESP32 family (with `esp-hal`) and STM32 |
| RTIC 2 | interrupt-driven tasks with fixed priorities, for hard real-time | Cortex-M chips (Pico 2, STM32), if a timing need appears that Embassy can't meet |
| FreeRTOS, through ESP-IDF | Espressif's operating system, with Rust's standard library | ESP32 projects that need its WiFi and web stacks |
| A plain loop | read, call the logic, write, repeat | the simplest boards |

## Today's boards, and their Rust versions

| Board (2025-26, C++) | Does | Rust plan |
|---|---|---|
| `aav_umod_esp32` (ESP32) | drives the actuators: steering and brake (Jrk G2), throttle (DAC), the RC receiver | becomes the spine: `spine-core` plus a board crate, on the chip the team picks (Q10–Q13) |
| `wheel_encoder_pico2` (Pico 2) | counts wheel spokes, sends them over Ethernet | Rust on the same Pico 2: `aav-inputs` (lockout), the encoder maths in `spine-core`; or the spine reads the sensors itself |
| `aav_sentinel_pico2` (Pico 2) | a status display | Rust on the same Pico 2, if the display stays |

## Toolchains

| Chip | Rust target | In Pixi? | Flashing |
|---|---|---|---|
| Pico 2 (RP2350, ARM) | `thumbv8m.main-none-eabihf` | [[works]] all seven crates build for it; `pixi run test` checks it | its USB drive (UF2), or `probe-rs` |
| STM32-class ARM (Cortex-M4F, M7) | `thumbv7em-none-eabihf` | [[works]] the crates build for it too | `probe-rs` |
| ESP32-C3, C6 (RISC-V) | `riscv32imc` / `riscv32imac` | [[missing]] not in Pixi; `rustup` has them | `espflash` |
| Classic ESP32 (today's board) | Xtensa | [[missing]] needs Espressif's `espup` installer | `espflash` |
| Arduino (AVR) | `avr-*` | [[missing]] needs nightly Rust (`avr-hal`) | `ravedude` |

> An ARM chip (Pico 2 or STM32) keeps the whole toolchain inside Pixi. That's worth
> weighing in Q10–Q13.

## Done so far

| Crate | Does | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, watchdog, speed loop, encoder, CAN frames. Since 10 Oct, a stop brakes to a standstill instead of coasting (found on the bench) | 48 |
| `aav-inputs` (10 Oct) | clean inputs for every board: a `Debouncer` for switches and buttons, with separate times each way (an e-stop trips at once, and must stay released before it counts), and a `Lockout` for counting fast signals such as encoder spokes | 9 |
| `jrk-g2` (10 Oct) | the Pololu Jrk G2 over I2C: set target, stop, feedback, error flags. Checked against Pololu's guide | 14 |
| `ad5311` (10 Oct) | the throttle DAC (an AD5311; TI's DAC101C081 takes the same bytes), capped at 700 of 1023 | 10 |
| `pca9555` (10 Oct) | the 16-bit I/O expander: the direction output | 6 |
| `ibus` (10 Oct) | the FlySky receiver's iBUS frames, byte by byte; a silence timeout; the map to spine-core's `RcInput` | 24 |
| `spine-board` (10 Oct) | the glue: throttle off before the brake, the direction only at zero throttle, I2C errors as fault bits. The `Board` trait | 44 |

Both are `no_std` with no dependencies, pass `clippy` and `rustfmt`, and build for the
Pico 2 and STM32 targets.

## Next

| # | Step | Waits on |
|---|---|---|
| 1 | The spine's chip | Q10–Q13 |
| 2 | Embassy or RTIC | a short trial on a Pico 2 |
| 3 | A first board crate on a Pico 2: blink, then the encoder sensors through `aav-inputs`, then `spine-board` on real I2C | a Pico 2 on the bench |
| 4 | Confirm the calibrations: steering centre and scale, brake range, throttle cap, RC channels | the car (Q1-Q7) |
| 5 | Tune the speed loop: on the bench it lags a ramp by about a second | the car |
