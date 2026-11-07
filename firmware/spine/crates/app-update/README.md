# app-update

## Overview

The checks around a firmware update over WiFi: the ESP32 board's `wifi-update` feature
(`boards/esp32-umod/src/update.rs`). The 2025-26 C++'s `/update` took any file from anyone,
at any time. Here a file is written only when every check below holds.

Plain `no_std` Rust, no dependencies, tested on a laptop. The board does the flash writes
and the restart.

## Interface

| Item | Does |
|---|---|
| `Guard::new(expected, example)`, `check(given, now_ms)` | the update password: `NotSetUp` if the build's is shorter than `MIN_PASSWORD_LEN` (12) or is the example's; `Wrong`; `LockedOut` for `LOCKOUT_MS` (10 s) after a wrong one. Compared in constant time |
| `CarState`, `may_update(&state)` | the car is parked: nobody driving, not armed, throttle 0, brake at least `BRAKED_AT_LEAST` (0.99); else `NotNow` with its `reason()` |
| `Expect { project, slot_len }`, `ImageCheck::new(expect)` | a streaming check of an ESP32 app image, fed in any chunks with `push` |
| `ImageCheck::ready_to_write()` | true once the header, the first segment and the app descriptor passed: nothing is written before |
| `ImageCheck::finish()` | the whole file: `ImageInfo { len, crc32, version }`, or an `ImageError` |
| `ImageError` | `NotAnImage`, `WrongChip`, `Segments`, `BadSegment`, `NoAppDescriptor`, `WrongProject`, `NoHash`, `Checksum`, `TooBig`, `TrailingBytes`, `Truncated` |
| `Crc32` | zlib's CRC-32, for the read-back |

What `ImageCheck` checks, from Espressif's image format:

| Part | Rule |
|---|---|
| header | magic `0xE9`, the chip ESP32 (`0x0000`), 1 to 16 segments, the SHA-256 appended |
| segments | each fits the slot |
| app descriptor | magic `0xABCD5432` at the start of segment 0; its project name is ours |
| checksum | the XOR of the segments' bytes, seeded `0xEF`, in the last byte of the 16-byte padding |
| the end | 32 bytes of SHA-256, nothing after; the slot's own SHA-256 check is the board's |

## Invariants

- Nothing is written before `ready_to_write()`, nor after any error.
- The example file's password never opens it.
- Checked again at every chunk: the car must stay parked.

## Side Effects

None: it parses and decides.

## Verification

```sh
cd firmware/spine
cargo test -p app-update
AAV_ESP32_APP_IMAGE=/tmp/app.bin cargo test -p app-update   # a real image from espflash save-image
```
