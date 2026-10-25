# sentinel-pico2

The status display's board program, for a Raspberry Pi Pico 2 (RP2350). It is the Rust
version of the 2025-26 `AAV_sentinel` Pico 2: an I2C device at 0x42 that shows the car's
telemetry on a 16x2 LCD, an 8x8 LED matrix and a 10-LED bar, with a knob, a button and a
buzzer.

**Builds; never flashed.** The pin map, how to build and flash, and what is still
untested are in `docs/rust-firmware.md`.

| File | What |
|---|---|
| `src/main.rs` | the settings, the pin map in code, the loop, the I2C device, the knob sampler, the buzzer |
| `memory.x` | the RP2350's memory, from Embassy's RP2350 examples |
| `build.rs`, `.cargo/config.toml` | the linker scripts, the target, the probe-rs runner |
| `PROVENANCE.md` | the 2025-26 code it replaces, and what changed |

The logic (the packet, the pages, the beeps, the knob) is in the crate `sentinel`, and
the LCD's driver in `hd44780`, both tested on a laptop:
`cd firmware/spine && cargo test -p sentinel -p hd44780`.

```sh
pixi run sentinel-uf2     # build it, and make sentinel-pico2.uf2 here, to drag on
pixi run sentinel-flash   # or flash it through a debug probe (pixi run spine-tools first)
```
