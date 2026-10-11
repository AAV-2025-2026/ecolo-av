# spine-pico2

The spine's board program, for a Raspberry Pi Pico 2 (RP2350) on the bench. It runs
`spine-board` and `spine-core` on the chip, with Embassy, and talks plain CAN to
`spine_bridge` through an MCP2515.

The pin map, how to build and flash, and what is still untested are in
`docs/rust-firmware.md`.

| File | What |
|---|---|
| `src/main.rs` | the settings, the pin map in code, the loop, the wheel sampler, the watchdog |
| `src/can.rs` | CAN through the MCP2515: send, receive, and keeping the chip up |
| `memory.x` | the RP2350's memory, from Embassy's RP2350 examples |
| `build.rs`, `.cargo/config.toml` | the linker scripts, the target, the probe-rs runner |

It is a workspace of its own, not a member of `firmware/spine`'s: it builds only for the
RP2350 (`thumbv8m.main-none-eabihf`), with Embassy's HAL for that chip.

```sh
pixi run spine-uf2         # build it, and make spine-pico2.uf2 here, to drag on
pixi run spine-flash       # or flash it through a debug probe (pixi run spine-tools first)
cd firmware/spine/boards/pico2 && cargo build --release   # pixi run test does this too
```
