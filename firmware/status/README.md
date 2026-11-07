# firmware/status: the ESP32's status lines

## Overview

The contract for what the ESP32 reports as JSON, one object per line. The firmware writes it; the
web page, `hw_panel` and `tools/link_check.py` read it. Design:
`docs/designs/2026-11-07_esp32-debug-link_brief.md`. `golden.jsonl` holds one of each line, and every
reader and writer tests against it.

## Interface

| `t` | When | Holds |
|---|---|---|
| `hb` | Once a second | Alive: uptime, boot ID, build, features, last reset, mode |
| `status` | 5 to 20 times a second | The Pi's last frame, what went to each device, low and high since the last line, positions, link counts, RC, state, tick timing |
| `event` | At each change | What changed, from and to |

| Field in `status` | Means |
|---|---|
| `rx` | The last good frame: `v`, `counter`, `check` (its last byte), `steer`, `speed`, `accel` (-1..1), `age_ms`. `null` before the first |
| `out` | What the firmware asked of each device: `steer_counts`, `brake_counts`, `dac`, `reverse` |
| `low`, `high` | The lowest and highest of `steer_counts`, `brake_counts` and `dac` since the last line, so a short spike still shows |
| `pos` | Each Jrk's position in counts, `null` when not known. Throttle has no sensor, so it has none |
| `link` | `frames`, `bad`, `skipped`, `repeats` since boot |
| `rc` | `switch`, and the raw channels |
| `state` | `mode`, `armed`, `estop`, `faults` |
| `tick` | `worst_gap_us`: the longest gap between ticks since boot. `overruns`: ticks later than 10 ms |

## Invariants

- Every line has `t`, `schema`, `seq` and `up_ms`. A gap in `seq` means lost lines: draw a gap.
- A reader ignores fields it doesn't know. A reader that doesn't know the `schema` number says so,
  and treats the values as unknown.
- Change the schema number when a field changes meaning or goes away. Change this file and
  `golden.jsonl` first.
- No password, key or WiFi name ever goes in a line: anyone on the WiFi can read them.
- The firmware builds lines from values the tick already has. It never reads a device for them:
  reading a Jrk's errors clears them.
- A slow reader loses lines. It never slows the tick.

## Side Effects

None: a contract and test data.

## Verification

Each reader's and writer's own tests read `golden.jsonl`. `tools/test.sh` runs them.
