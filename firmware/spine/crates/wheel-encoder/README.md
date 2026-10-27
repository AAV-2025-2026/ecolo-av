# wheel-encoder

## Overview

The wheel's two spoke sensors, counted, and the packet that reports them. Plain `no_std`
Rust with no hardware access: the board reads the pins and the clock.

Two boards use it: the spine (`spine-board` re-exports `SpokeSensors` and `WheelCount`),
and the stand-alone wheel encoder Pico 2 (`boards/wheel-encoder-pico2`).

## Interface

| Item | Does |
|---|---|
| `SpokeSensors::TODAY` | the 2025-26 rule: 10 ms lockout, a 20 ms window for B |
| `SpokeSensors::new(lockout_ms, direction_window_ms)` | the same rule with your own numbers |
| `SpokeSensors::update(a, b, now_ms)` | feed both sensors, about every millisecond; returns the `WheelCount` |
| `WheelCount` | the running counter (forward up, reverse down; it wraps) and the time of its last count |
| `Reporter::new(now)` | call first: starts from the `WheelCount` as it is now |
| `Reporter::report(count)` | the spokes since the last report, as a `SpokeDelta` |
| `SpokeDelta::to_bytes()` | the UDP packet: `SpokeDelta::LEN` (4) bytes, big-endian int32 |
| `SpokeDelta::from_bytes(b)` | reads one; anything but 4 bytes is `PacketError::Length` |
| `SpokeDelta::rpm(spokes_per_rev, interval_ms)`, `direction()` | for the logs; `direction()` is a `Direction`: `Forward`, `Reverse`, `Stopped` |
| `SpokeSensors::count()` | the counter now, without feeding it |

## The packet

Byte for byte the 2025-26 one. The Motor Pi's `encoder_udp` (`aav_legacy`) reads it with
`encoder_counts()`. Both sides check the same examples, in
`firmware/udp/wheel_encoder_vectors.txt`:

| Spokes | Bytes |
|---|---|
| 1 | `00 00 00 01` |
| -3 | `ff ff ff fd` |
| 16909060 | `01 02 03 04` |

## Invariants

- `no_std`, no hardware access: the board reads the pins and the clock.
- One count a spoke, on A's rising edge, after a 10 ms lockout. Backwards if B rose
  in the 20 ms before and is still high.
- The counter runs on and wraps; `Reporter` subtracts, so no count is lost between
  packets.
- The packet is byte for byte the 2025-26 one: 4 bytes, big-endian `i32`, positive
  forward. `firmware/udp/wheel_encoder_vectors.txt` holds both sides to it.

## Side Effects

None. `boards/wheel-encoder-pico2` sends the packet over UDP (port 10111) to the
Motor Pi.

## Verification

```sh
cd firmware/spine
cargo test -p wheel-encoder     # 11 tests, and the shared examples
```

Where the rules came from: `PROVENANCE.md`.
