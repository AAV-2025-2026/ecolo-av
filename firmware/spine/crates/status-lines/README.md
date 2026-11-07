# status-lines

## Overview

The ESP32's JSON status lines, one object a line: the writer's side of the contract in
[`firmware/status`](../../../status/README.md). Plain `no_std` Rust: no allocator, no
dependencies, only `core::fmt`.

```text
 the tick's values ──► Line { seq, up_ms, body } ──► Display: a log line
                                                └──► write_to(&mut [u8]) / LineBuf: a socket
```

## Interface

| Item | Does |
|---|---|
| `Line { seq, up_ms, body }` | one line; `Display`, so `println!("{line}")` writes it |
| `Body::Heartbeat(Heartbeat)` | `hb`: `boot_id` (8 hex digits), `build`, `features`, `last_reset` |
| `Body::Status(Status)` | `status`: `rx` (`Rx`, or `null`), `out` (`Out`), `low`, `high` (`Levels`), `pos` (`Positions`), `link` (`LinkCounts`), `rc` (`Rc`, `Switch`), `state` (`State`, `Mode`), `tick` (`Tick`) |
| `Body::Event(Event)` | `event`: `what`, `from`, `to`; each a `Value`: `Text`, `Flag` or `Number` |
| `Body::Health(Health)` | `health` (7 Nov): `link` (a `Verdict`, or `null`), `age_ms`, `counter_moving`, the link's counts, `devices` (answered, expected, missing), `faults`, `mode`, `last_reset`, `build`, `boot_id` |
| `Body::Config(Config)` | `config` (7 Nov): the build, features, version, link, frame version, tick, watchdog, command timeout, `idle_brake`, `full_throttle_speed`, `i2c_khz`, `Addresses`, `SteeringLimits`, `BrakeLimits`, the full-throttle code, `last_reset` |
| `Body::Devices(DeviceList)` | `devices` (7 Nov): `answered`, `expected`, and a `list` of `DeviceSeen`: `name`, `address`, `answered`, `feedback` |
| `Line::write_to(&mut buf)` | the line into a byte slice, no newline; `Err(TooLong)` if it doesn't fit |
| `LineBuf<N>` | a line in its own `N`-byte buffer: `set`, `as_str`, `as_bytes` |
| `Spread` | the lowest and highest `Levels` between two status lines: `add` each tick, `take` at each line |
| `Trickle<SLOTS, N>` | lines queued for a slow serial log: `push` a line (a full queue drops it whole: `Dropped`, counted in `dropped()`), `next_chunk(max)` each tick; a chunk never spans two lines |
| `SCHEMA`, `MAX_LINE`, `MAX_CHANNELS` | 1; 832 bytes (the widest status line is 783); 14 |

| Value | Written as |
|---|---|
| `Mode` | `stopped`, `rc`, `computer`, `test` |
| `Switch` | `computer`, `via_ros`, `direct`, `no_signal` |
| `Verdict` | `no_frames`, `ok`, `stale`, `counter_frozen`, `bad_frames` (also `link.verdict` in `status`) |
| an `f32` | the shortest form that reads back the same (`0.0`, `-0.1`, `1e-7`); `null` if not finite |
| `None` | `null` |

## Invariants

- The fields come out in the contract's order, byte for byte as `golden.jsonl`.
- Every line has `t`, `schema`, `seq` and `up_ms`, in that order.
- Nothing allocates. A line too long for its buffer is an error, never a cut line.
- `Trickle` never cuts or mixes lines: a line goes out whole, in order, or not at all.
- Strings are escaped. Never pass a password, key or WiFi name: anyone on the WiFi
  reads the lines.
- It reads no device: the board gives it what the tick already had.

## Side Effects

None: it formats.

## Verification

```sh
cd firmware/spine
cargo test -p status-lines
```

The tests build each line of `firmware/status/golden.jsonl` and compare them byte for byte,
and check the widest line fits `MAX_LINE`.
