# wheel-encoder

The wheel's two spoke sensors, counted, and the packet that reports them. Plain `no_std`
Rust with no hardware access: the board reads the pins and the clock.

Two boards use it: the spine (`spine-board` re-exports `SpokeSensors` and `WheelCount`),
and the stand-alone wheel encoder Pico 2 (`boards/wheel-encoder-pico2`).

## API

| Item | Does |
|---|---|
| `SpokeSensors::TODAY` | the 2025-26 rule: 10 ms lockout, a 20 ms window for B |
| `SpokeSensors::update(a, b, now_ms)` | feed both sensors, about every millisecond; returns the `WheelCount` |
| `WheelCount` | the running counter (forward up, reverse down; it wraps) and the time of its last count |
| `Reporter::report(count)` | the spokes since the last report, as a `SpokeDelta` |
| `SpokeDelta::to_bytes()` | the UDP packet: 4 bytes, big-endian int32 |
| `SpokeDelta::from_bytes(b)` | reads one; anything but 4 bytes is `PacketError::Length` |
| `SpokeDelta::rpm(spokes_per_rev, interval_ms)`, `direction()` | for the logs |

## The packet

Byte for byte the 2025-26 one. The Motor Pi's `encoder_udp` (`aav_legacy`) reads it with
`encoder_counts()`. Both sides check the same examples, in
`firmware/udp/wheel_encoder_vectors.txt`:

| Spokes | Bytes |
|---|---|
| 1 | `00 00 00 01` |
| -3 | `ff ff ff fd` |
| 16909060 | `01 02 03 04` |

```sh
cargo test -p wheel-encoder     # 11 tests, and the shared examples
```
