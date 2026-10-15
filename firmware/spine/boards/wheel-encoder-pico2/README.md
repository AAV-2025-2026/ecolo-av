# wheel-encoder-pico2

The wheel encoder's board program, for a Raspberry Pi Pico 2 (RP2350) with a WIZnet
W5500 Ethernet chip. It is the Rust version of the 2025-26 `Wheel_Encoders` Pico 2: it
counts the wheel's spokes, and sends the count to the Motor Pi over UDP every 100 ms,
byte for byte as before. `aav_legacy`'s `encoder_udp` reads it unchanged.

**Builds; never flashed.** The pin map, how to build and flash, and what is still
untested are in `docs/rust-firmware.md`.

| File | What |
|---|---|
| `src/main.rs` | the settings (MAC, addresses, ports), the pin map in code, the sampler, the sender, the watchdog |
| `memory.x` | the RP2350's memory, from Embassy's RP2350 examples |
| `build.rs`, `.cargo/config.toml` | the linker scripts, the target, the probe-rs runner |
| `PROVENANCE.md` | the 2025-26 code it replaces, and what changed |

The logic (the spoke counting, the packet) is in the crate `wheel-encoder`, tested on a
laptop: `cd firmware/spine && cargo test -p wheel-encoder`.

```sh
pixi run wheel-uf2     # build it, and make wheel-encoder-pico2.uf2 here, to drag on
pixi run wheel-flash   # or flash it through a debug probe (pixi run spine-tools first)
```
