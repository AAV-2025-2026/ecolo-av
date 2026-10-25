# Provenance

A Rust rewrite (15 Oct 2026) of the 2025-26 team's wheel encoder Pico 2, which was in
`firmware/legacy/wheel_encoder_pico2` until then. Not a line-by-line port: the same job
and the same wire format, written the Rust way.

| | |
|---|---|
| Repo | github.com/AAV-2025-2026/Wheel_Encoders (public) |
| Branch | `main` |
| Commit | `f824e9d805` |
| Files | `wiznet.ino` (the car's), `wiznet_demo.ino` (a 2 s debug copy), `udp_receiver.py`, `readme.md` |
| Authors | Collin Dang, Alex Tempel |

Copied into this repo on 9 Oct 2026; replaced by this program and deleted on 15 Oct 2026.
The original stays on GitHub at that commit.

## What stayed the same

| Thing | Value |
|---|---|
| The packet | 4 bytes, big-endian int32: spokes since the previous packet, positive forward |
| Rate | every 100 ms |
| To | 192.168.1.193 (the Motor Pi), UDP port 10111 |
| From | UDP port 11101 |
| Address | DHCP |
| MAC | 54:65:6d:70:65:6c (the bytes of "Tempel") |
| Counting | one count on A's rising edge; backwards if B rose in the last 20 ms and is still high |
| Debounce | 10 ms |
| Sampling | every 1 ms |
| Spokes a turn | 8 |
| Pins | sensor A on GP2, sensor B on GP10, W5500 chip select on GP17 |

## What changed

| Change | Why |
|---|---|
| The counter only runs on; the sender remembers what it last sent | the old one read the counter then set it to 0: fine with interrupts off, but now nothing can be lost by design |
| Waits for DHCP, and keeps trying | the old one stopped for good if the first DHCP try failed |
| No USB serial console | the old one waited for a serial monitor before it started counting |
| A 1 s hardware watchdog | a hang resets the chip |
| The debounce is `aav_inputs::Lockout` on both sensors | the same rule the spine uses (`wheel-encoder`'s `SpokeSensors`) |
| W5500 reset on GP20, interrupt on GP21 | `embassy-net-wiznet` needs both; on WIZnet's Ethernet HAT for the Pico they are wired there |

## Found in the old code

- `readme.md` gives sensor B as "GP14, pin 10", but `wiznet.ino` uses GPIO 10 (pin 14):
  the readme swapped the two columns. This program follows the code: GP10.
- The MAC is not a locally administered address; kept, so a DHCP reservation still works.
