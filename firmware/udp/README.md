# firmware/udp: the wheel encoder's UDP packet

## Overview

One file, `wheel_encoder_vectors.txt`: examples of the wheel encoder's UDP packet that
both sides must agree on. No code lives here.

| Side | Who |
|---|---|
| Sends | the wheel encoder's Pico 2 (`firmware/spine/boards/wheel-encoder-pico2`, logic in the crate `wheel-encoder`) |
| Receives | `aav_legacy`'s `encoder_udp`, on the Motor Pi (`legacy_protocol.py`) |

## Interface

The packet: 4 bytes, a big-endian signed 32-bit integer, the spokes since the previous
packet, positive forward (the 2025-26 `Wheel_Encoders` format).

Each line of the file: the spokes, then the packet's 4 bytes in hex. Lines starting with
`#` are comments.

```text
# spokes      bytes
-1            ffffffff
256           00000100
```

## Invariants

- Written by hand: there is no generator. Add a line, and both tests check it.
- The format stays the 2025-26 one, so the receiver needs no change.

## Side Effects

None: it is data.

## Verification

```sh
cd firmware/spine && cargo test -p wheel-encoder                      # tests/vectors.rs
cd ros/can_bridge/aav_legacy && python3 -m pytest -q test/test_legacy_protocol.py
```

`tools/test.sh` runs both.
