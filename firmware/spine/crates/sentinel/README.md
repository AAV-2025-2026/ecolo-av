# sentinel

The status display's logic: the Rust version of the 2025-26 "sentinel" Pico 2. Plain
`no_std` Rust with no hardware access; the board program is `boards/sentinel-pico2`.

## What it does

```text
  I2C write ---> Telemetry ---> Sentinel ---> the LCD: 2 x 16 characters, 13 pages
                                  ^  |   ---> the 8x8 matrix: mode and direction
  knob, buttons ---> Input -------+  |   ---> 10 LEDs: computers and ROS nodes up
                                     +-----> the buzzer: Beep
```

| Call | Does |
|---|---|
| `Sentinel::on_write(bytes, now_ms)` | one I2C write: a good packet replaces the last; may ask for a beep |
| `Sentinel::on_input(input, now_ms)` | a knob click, the knob's press (pin), the button (home) |
| `Sentinel::tick(now_ms)` | the page's 10 s timeout, and the link's 3 s watchdog |
| `screen()`, `pattern(now_ms)`, `leds()` | what the LCD, the matrix and the LED bar show |

## The packet

46 bytes, little-endian, from a computer on the car, as an I2C write to address 0x42. It
starts `AA 01` and ends in an XOR of the bytes before. The byte table is at the top of
`src/telemetry.rs`. `Telemetry::to_packet()` builds one, for whoever writes the sender.

## The pages

The knob turns through 13 pages; the knob's press pins one (a `*` in the corner); the
button goes home; an unpinned page goes home after 10 s.

| # | Page | Shows |
|---|---|---|
| 0 | Overview | `MODE:AUTO`, `STATE:FWD` |
| 1 | Drive | steering, speed, acceleration |
| 2, 3 | Steering Jrk, brake Jrk | OK or FAIL, the error flags in hex |
| 4, 5 | their flags | `AWT PWR DRV` / `FBK OVC SER`, or `---` when clear |
| 6 | Throttle | the DAC: OK, its value of 1023 |
| 7 | iBUS | the four RC channels |
| 8 | RC | the signal, and whether every channel is alive |
| 9 | Computers | `JET+ MPI+ RPI-`: `+` up, `-` down |
| 10 | Nodes | `IMU+ RDR+ LDR-`, `CAM+ GPS+` |
| 11 | GPS | latitude, longitude |
| 12 | Error | the code, and its meaning |

```sh
cargo test -p sentinel     # 40 tests
```
