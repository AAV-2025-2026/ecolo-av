# firmware/spine: the firmware, in Rust

Everything the spine board runs, the car's two other Pico 2s (the wheel encoder and the
status display, the sentinel), and the CAN wheel nodes' logic. Every crate is `no_std` and
is tested on a laptop, without a board. The board programs are in `boards/`.

| Crate | What it is | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, the 100 ms watchdog, the speed loop, the encoder, the CAN frames, and the three choices still open (below) | 59 |
| `wheel-core` | the front wheel nodes' logic: Hall sensor pulses to speed, and the WHEEL_SPEED frame | 9 |
| `aav-inputs` | clean inputs: debounced switches, an e-stop that trips at once, counting with a lockout | 9 |
| `jrk-g2` | the Pololu Jrk G2 motor controllers (steering, brake), over I2C | 14 |
| `ad5311` | the throttle DAC, over I2C | 10 |
| `pca9555` | the I/O expander (the direction output), over I2C | 6 |
| `mcp2515` | the CAN controller a Pico 2 needs, over SPI: bit timing from the crystal, filters, send, receive, error state | 34 |
| `ibus` | the FlySky RC receiver's iBUS frames | 24 |
| `spine-board` | the glue: spine-core's outputs to the devices, the devices to its inputs, and the `Board` trait a board program implements | 45 |
| `wheel-encoder` (15 Oct) | two spoke sensors, counted the 2025-26 way (the spine and the wheel encoder share it), and the wheel encoder's UDP packet | 12 |
| `sentinel` (15 Oct) | the status display's logic: its I2C packet, its 13 LCD pages, the knob, the beeps, the matrix | 40 |
| `hd44780` (15 Oct) | the sentinel's 16x2 character LCD, on six GPIO pins | 5 |

Each crate's own README has its API, and where its behaviour came from in the 2025-26 C++.

## Three choices still open

Each is one constant in `spine-core` (`src/spine.rs`), set to what `docs/firmware.md`
proposes. Change one only with the team; the board program and the bench both follow.

| Constant | Set to | The 2025-26 firmware |
|---|---|---|
| `ESTOP_STEERING` | `Hold`: on any stop the spine makes, the wheels stay where they are | centred them (`Centre`) |
| `IDLE_BRAKE` | `0.0`: with nobody driving, after boot too, the brake lets go once the e-stop input clears | kept it full on (`1.0`) |
| `RC_GEAR_BRAKE` | `SpeedZero`: the gear switch's brake position asks for zero speed | full brake at once (`FullBrake`) |

## Test it

```bash
pixi run test                          # all of it, with the rest of the repo
cd firmware/spine && cargo test        # just these crates
cargo build --target thumbv8m.main-none-eabihf -p spine-board   # for the Pico 2's chip
```

`pixi run test` also builds every crate for the Pico 2's chip, so a crate that pulls in the
standard library fails. It builds the three board programs too, and checks their UF2 files.

## Run it without a board

Bench mode runs `spine-core` on a laptop, on the CAN frames from `spine_bridge`, driving a
model car: `pixi run bench` (`docs/bench.md`).

## The board programs: `boards/`

Each is a workspace of its own: it builds only for the RP2350 (a Pico 2), with Embassy.
The pin maps, the wiring rules, and what is untested: `docs/rust-firmware.md`.
**None has been flashed yet.**

| Board | Does | Build a UF2 | Flash through a probe |
|---|---|---|---|
| `boards/pico2` | the spine, on the bench: `spine-board`, and CAN through an MCP2515, every 10 ms. The car's chip is still Q10-Q13 | `pixi run spine-uf2` | `pixi run spine-flash` |
| `boards/wheel-encoder-pico2` | the wheel encoder: spokes to the Motor Pi over UDP, through a W5500. Replaces the 2025-26 C++ one | `pixi run wheel-uf2` | `pixi run wheel-flash` |
| `boards/sentinel-pico2` | the status display: an I2C device at 0x42; an LCD, a matrix, LEDs, a buzzer. Replaces the 2025-26 C++ one | `pixi run sentinel-uf2` | `pixi run sentinel-flash` |

The UF2 file lands in the board's folder: hold BOOTSEL, plug the Pico 2 in, drag it on.
Flashing through a probe needs `pixi run spine-tools` once.
