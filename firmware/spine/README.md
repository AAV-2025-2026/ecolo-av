# firmware/spine: the spine's firmware, in Rust

Everything the spine board will run, except the board program itself, which waits on the
chip (Q10-Q13). Every crate is `no_std` and is tested on a laptop, without the board.

| Crate | What it is | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, the 200 ms watchdog, the speed loop, the encoder, the CAN frames, and the three choices still open (below) | 54 |
| `aav-inputs` | clean inputs: debounced switches, an e-stop that trips at once, counting with a lockout | 9 |
| `jrk-g2` | the Pololu Jrk G2 motor controllers (steering, brake), over I2C | 14 |
| `ad5311` | the throttle DAC, over I2C | 10 |
| `pca9555` | the I/O expander (the direction output), over I2C | 6 |
| `mcp2515` | the CAN controller a Pico 2 needs, over SPI: bit timing from the crystal, filters, send, receive, error state | 34 |
| `ibus` | the FlySky RC receiver's iBUS frames | 24 |
| `spine-board` | the glue: spine-core's outputs to the devices, the devices to its inputs, and the `Board` trait a board program implements | 49 |

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
standard library fails.

## Run it without a board

Bench mode runs `spine-core` on a laptop, on the CAN frames from `spine_bridge`, driving a
model car: `pixi run bench` (`docs/bench.md`).

## The board program, still to write

One small program for the chosen chip. It implements `spine_board::Board` (a millisecond
clock, the hardware e-stop pin, the wheel encoder's counter, and CAN), then calls
`SpineBoard::tick` about 100 times a second. `spine-board`'s README has the checklist.
