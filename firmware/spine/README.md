# firmware/spine: the spine's firmware, in Rust

Everything the spine board runs. Every crate is `no_std` and is tested on a laptop, without
the board. The board programs: `boards/esp32-umod`, today's ESP32 control board (the
Rust replacement for `firmware/legacy/aav_umod_esp32`), and `boards/pico2`, a Pico 2 on
the bench.

| Crate | What it is | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, the 200 ms watchdog, the speed loop (closed, or open with no wheel speed), the encoder, the CAN frames, open-loop commands, and the three choices still open (below) | 64 |
| `legacy-link` | the 2025-26 UART link: the Motor-Pi's 13-byte frames, and the targets the C++ set for them | 31 |
| `aav-inputs` | clean inputs: debounced switches, an e-stop that trips at once, counting with a lockout | 9 |
| `jrk-g2` | the Pololu Jrk G2 motor controllers (steering, brake), over I2C | 14 |
| `ad5311` | the throttle DAC, over I2C | 10 |
| `pca9555` | the I/O expander (the direction output), over I2C | 6 |
| `mcp2515` | the CAN controller a Pico 2 needs, over SPI: bit timing from the crystal, filters, send, receive, error state | 34 |
| `ibus` | the FlySky RC receiver's iBUS frames | 24 |
| `spine-board` | the glue: spine-core's outputs to the devices, the devices to its inputs, the `Board` trait a board program implements, and the `CommandLink` trait: CAN or the UART | 61 |

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
standard library fails. It builds the board program too, and checks its UF2 file.

## Run it without a board

Bench mode runs `spine-core` on a laptop, on the CAN frames from `spine_bridge`, driving a
model car: `pixi run bench` (`docs/bench.md`).

## The board program: `boards/esp32-umod`

The spine on today's ESP32 control board (the SparkFun ESP32 MicroMod, Xtensa), with
Embassy: the Rust replacement for the C++ that drives the car today. The same pins and
devices; commands from the Motor-Pi's UART (default) or CAN (`--features can`). Its own
README has the details. It needs Espressif's Rust, which Pixi doesn't have:

| Command | Does |
|---|---|
| `pixi run esp-tools` | installs it for your user, once (needs rustup) |
| `pixi run esp-build` | builds the program |
| `pixi run esp-flash` | flashes it on the USB cable: bench only (`docs/esp32-bench.md`) |

Untested on the board: nothing has been flashed yet. The C++ stays until it is proven.

## The board program: `boards/pico2`

The spine on a Raspberry Pi Pico 2 (RP2350), with Embassy, for the bench. It implements
`spine_board::Board` (the clock, the e-stop input, the wheel's spoke sensors, CAN through
the MCP2515), then calls `SpineBoard::tick` every 10 ms. The car's chip is still Q10-Q13.

| Command | Does |
|---|---|
| `pixi run spine-uf2` | builds it, and writes `boards/pico2/spine-pico2.uf2`: hold BOOTSEL, plug in, drag it on |
| `pixi run spine-tools`, then `pixi run spine-flash` | or flash it through a debug probe, and see its logs |

It is a workspace of its own: it builds only for the RP2350. The pin map, the wiring rules
(the e-stop's among them), and what is untested: `docs/rust-firmware.md`.
Untested on a real Pico 2: nothing has been flashed yet.
