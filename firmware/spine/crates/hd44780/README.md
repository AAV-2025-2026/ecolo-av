# hd44780

## Overview

A character LCD with an HD44780 controller (16x2, 20x4), on six GPIO pins, 4-bit, write
only (R/W tied to ground). Plain `no_std` Rust against `embedded-hal` 1.0. The stock
`hd44780-driver` crate is still on `embedded-hal` 0.2, and this one is small.

It is the sentinel's display (`sentinel` draws the text, this crate shows it).

## Interface

| Call | Does |
|---|---|
| `Hd44780::new(Pins { rs, e, d4, d5, d6, d7 }, delay, Lines::Two)` | takes the pins |
| `init()` | wakes the controller into 4-bit mode from any state, display on, no cursor, clear |
| `write_line(line, bytes)` | a line from its first column |
| `set_cursor(column, line)`, `write_bytes(bytes)` | anywhere |
| `clear()`, `home()`, `set_display(on, cursor)` | as the datasheet's commands |
| `release()` | gives the pins and the delay back |

| Type | Holds |
|---|---|
| `Pins<P>` | the six output pins: `rs`, `e`, `d4` to `d7` |
| `Lines` | `Two`, or `Four { columns }` (lines 2 and 3 continue lines 0 and 1 in memory) |
| `Cursor` | `Hidden`, `Underline`, `Blinking` |

Timings from Hitachi's HD44780U datasheet: 1 us on E, 50 us a byte, 2 ms to clear. The
2025-26 C++ driver waited 10 ms a nibble.

## Invariants

- Write only: it never reads the busy flag, so it always waits the longest times
  above (with margin over the datasheet's 37 us and 1.52 ms).
- `init()` must run before anything shows. It works from any state the controller
  is in.
- Each byte goes as two nibbles, the high one first; the display latches as E falls.
- Pin errors come back as `Result`; nothing panics.

## Side Effects

- Drives six GPIO outputs, and blocks on the given delay (about 50 ms in `init()`).
- Changes what the LCD shows. Nothing else.

## Verification

```sh
cd firmware/spine
cargo test -p hd44780     # 5 tests, against a fake that records what the display latched
```
