# aav-inputs

## Overview

Clean digital inputs for every board: debounced switches and buttons, and edges with
a lockout for counting. Plain `no_std` Rust with no dependencies and no hardware
access. The board reads the pin and the clock, and calls `update`.

A switch or a relay contact bounces for a few milliseconds when it moves, and an IR
sensor flickers at the edge of a spoke. Read raw, one press looks like several. These
filters turn a raw level into clean changes.

| Used by | For |
|---|---|
| `spine-board` | the hardware e-stop: trips at once, releases after 50 ms closed |
| `sentinel` | the knob's press and the home button |
| `wheel-encoder` | the spoke sensors: a 10 ms lockout |

## Interface

| Item | Does |
|---|---|
| `Debouncer::new(initial, stable_ms)` | the same time both ways |
| `Debouncer::with_times(initial, to_high_ms, to_low_ms)` | its own time each way; 0 means at once |
| `Debouncer::update(raw, now_ms)` | feed the raw level; `Some(Edge)` when the output changed |
| `Debouncer::level()` | the cleaned-up level |
| `Lockout::new(initial, lockout_ms)` | for fast signals: reacts at once, then ignores the input for `lockout_ms` |
| `Lockout::update(raw, now_ms)`, `level()` | the same calls |
| `Edge` | `Rising` (low to high) or `Falling` |

| Filter | Delay | Good for |
|---|---|---|
| `Debouncer` | waits until the input has held still | switches, buttons, the e-stop |
| `Lockout` | none; then deaf for `lockout_ms` | counting spokes (the 2025-26 encoder used 10 ms) |

The e-stop, starting tripped so a reboot is safe:

```rust
let mut estop = aav_inputs::Debouncer::with_times(true, 0, 50);
assert!(estop.level());
```

## Invariants

- `no_std`, no allocator, no dependencies, no hardware access.
- Times are a free-running millisecond counter that may wrap (`wrapping_sub`).
- A `Debouncer` changes only after the raw input has held the new level, without a
  break, for that direction's time. A bounce back resets the wait.
- A `Lockout` never counts two changes closer than `lockout_ms`.
- `update` returns an edge only when the level really changed.

## Side Effects

None. Pure state machines: no pins, no clock, no allocation.

## Verification

```sh
cd firmware/spine
cargo test -p aav-inputs     # 8 tests and the doc example
```
