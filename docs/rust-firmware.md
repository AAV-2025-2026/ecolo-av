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
| The spine is already Rust | `spine-core`: modes, arming, the watchdog, the speed loop, the CAN frames (47 tests) |

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
| Drivers | one per chip on the car: the Jrk G2 motor controllers, the throttle DAC, the PCA9555 expander, the iBUS radio receiver, the W5500 Ethernet chip, the display | crates written against `embedded-hal` 1.0 (still to write) | `embedded-hal-mock`, which plays the chip on a laptop |
| Boards | one small program per board: pins, timers, the framework, then a loop that calls the logic | one crate per board (still to write) | on the bench, then on the car |

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
| Pico 2 (RP2350, ARM) | `thumbv8m.main-none-eabihf` | [[works]] `spine-core` and `aav-inputs` build for it | its USB drive (UF2), or `probe-rs` |
| STM32-class ARM (Cortex-M4F, M7) | `thumbv7em-none-eabihf` | [[works]] the same two crates build for it | `probe-rs` |
| ESP32-C3, C6 (RISC-V) | `riscv32imc` / `riscv32imac` | [[missing]] not in Pixi; `rustup` has them | `espflash` |
| Classic ESP32 (today's board) | Xtensa | [[missing]] needs Espressif's `espup` installer | `espflash` |
| Arduino (AVR) | `avr-*` | [[missing]] needs nightly Rust (`avr-hal`) | `ravedude` |

> An ARM chip (Pico 2 or STM32) keeps the whole toolchain inside Pixi. That's worth
> weighing in Q10–Q13.

## Done so far

| Crate | Does | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, watchdog, speed loop, encoder, CAN frames | 47 |
| `aav-inputs` (10 Oct) | clean inputs for every board: a `Debouncer` for switches and buttons, with separate times each way (an e-stop trips at once, and must stay released before it counts), and a `Lockout` for counting fast signals such as encoder spokes | 9 |

Both are `no_std` with no dependencies, pass `clippy` and `rustfmt`, and build for the
Pico 2 and STM32 targets.

## Next

| # | Step | Waits on |
|---|---|---|
| 1 | The spine's chip | Q10–Q13 |
| 2 | Embassy or RTIC | a short trial on a Pico 2 |
| 3 | The first driver: the Jrk G2, over I2C, tested with `embedded-hal-mock` | nothing |
| 4 | The iBUS receiver parser (the RC override) in `spine-core` | nothing |
| 5 | A first board crate on a Pico 2: blink, then the encoder sensors through `aav-inputs` | a Pico 2 on the bench |
