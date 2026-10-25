# legacy-link

The 2025-26 UART link, from the Motor-Pi to the ESP32 control board, in plain `no_std`
Rust. It lets the Rust ESP32 program be a drop-in for the C++.

```text
 byte  0..3      4..7     8..11    12
      steering  speed    accel    sum(bytes 0..11) & 0xFF      115200 baud, 8N1, no header
```

## API

| Item | Does | The C++ (`ros2_handler.cpp`) |
|---|---|---|
| `Frame::encode`, `Frame::decode` | 13 bytes ↔ three `f32` | `memcpy`, the sum |
| `Parser::push` | one byte in; a frame, a frame turned down, or nothing | the byte loop: a bad sum drops one byte |
| `Frame::check` | each value within -1..1 | `fabsf(...) <= 1.0f` |
| `Frame::targets` | the steering and brake Jrk targets, and the DAC (`Cut`, `Idle`, `Drive`) | the rest of `handleROS2Messages()`, with its `f32` maths |

## Version 2: the Orin's heartbeat (TODO 50)

```text
 byte  0     1   2..5      6..9   10..13  14       15     16
       0xA5  2   steering  speed  accel   counter  flags  CRC-8/SAE-J1850 of bytes 1..15
```

| Item | Does |
|---|---|
| `FrameV2::encode`, `FrameV2::decode` | 17 bytes ↔ the values, the counter, `Flags { armed, estop }`; a bad sync, CRC, version or flag is an error |
| `ParserV2::push` | finds frames by the sync byte; a bad frame: start again at the next `0xA5` in it |
| `Heartbeat::fresh` | the rule: true only when the counter changed (the first frame after boot only sets it) |
| `crc8` | CRC-8/SAE-J1850, the same as `aav.dbc`'s |

Why and how: [the heartbeat](../../../../docs/rust-firmware.md#the-heartbeat-version-2-of-the-serial-frame-24-oct).

`spine-board`'s `LegacyLink` turns the targets into a `spine_core::DirectCmd`.

## Test vectors: three witnesses

`gen_vectors.py` makes the frames with `legacy_protocol.py` (the ROS side), and writes
`vectors.json` and `tests/vectors.rs`.

| Witness | Test |
|---|---|
| this crate | `cargo test -p legacy-link` |
| `legacy_protocol.py` | `ros/can_bridge/aav_legacy/test/test_legacy_protocol.py` |
| the C++ itself, compiled on the laptop with the stand-ins in `cpp_check/` | `tools/tests/test_legacy_cpp.py` |

After changing `legacy_protocol.py` or this crate:

```sh
python3 firmware/spine/crates/legacy-link/gen_vectors.py
tools/test.sh
```
