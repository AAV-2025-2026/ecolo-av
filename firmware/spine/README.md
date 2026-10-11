# firmware/spine: the spine's firmware, in Rust

Everything the spine board will run, except the board program itself, which waits on the
chip (Q10-Q13). Every crate is `no_std` and is tested on a laptop, without the board.

| Crate | What it is | Tests |
|---|---|---|
| `spine-core` | the spine's logic: modes, arming, the 200 ms watchdog, the speed loop, the encoder, the CAN frames | 48 |
| `aav-inputs` | clean inputs: debounced switches, an e-stop that trips at once, counting with a lockout | 9 |
| `jrk-g2` | the Pololu Jrk G2 motor controllers (steering, brake), over I2C | 14 |
| `ad5311` | the throttle DAC, over I2C | 10 |
| `pca9555` | the I/O expander (the direction output), over I2C | 6 |
| `mcp2515` | the CAN controller a Pico 2 needs, over SPI: bit timing from the crystal, filters, send, receive, error state | 34 |
| `ibus` | the FlySky RC receiver's iBUS frames | 24 |
| `spine-board` | the glue: spine-core's outputs to the devices, the devices to its inputs, and the `Board` trait a board program implements | 44 |

Each crate's own README has its API, and where its behaviour came from in the 2025-26 C++.

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
