# hd44780

A character LCD with an HD44780 controller (16x2, 20x4), on six GPIO pins, 4-bit, write
only (R/W tied to ground). Plain `no_std` Rust against `embedded-hal` 1.0. The stock
`hd44780-driver` crate is still on `embedded-hal` 0.2, and this one is small.

| Call | Does |
|---|---|
| `Hd44780::new(Pins { rs, e, d4, d5, d6, d7 }, delay, Lines::Two)` | takes the pins |
| `init()` | wakes the controller into 4-bit mode from any state, display on, no cursor, clear |
| `write_line(line, bytes)` | a line from its first column |
| `set_cursor(column, line)`, `write_bytes(bytes)` | anywhere |
| `clear()`, `home()`, `set_display(on, cursor)` | as the datasheet's commands |

Timings from Hitachi's HD44780U datasheet: 1 us on E, 50 us a byte, 2 ms to clear. The
2025-26 C++ driver waited 10 ms a nibble.

```sh
cargo test -p hd44780     # 5 tests, against a fake that records what the display latched
```
