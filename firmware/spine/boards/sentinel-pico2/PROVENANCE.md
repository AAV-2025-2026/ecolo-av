# Provenance

A Rust rewrite (15 Oct 2026) of the 2025-26 team's status display, the "sentinel" Pico 2,
which was in `firmware/legacy/aav_sentinel_pico2` until then. Not a line-by-line port: the
same job and the same I2C packet, written the Rust way. Its logic is in the crates
`sentinel` and `hd44780`.

| | |
|---|---|
| Repo | github.com/AAV-2025-2026/AAV_cortex (public) |
| Branch | `6-pico2-aav-firmware` |
| Commit | `90de619e52` |
| Folder | `AAV_sentinel/AAV_sentinal_pico` |
| Files | `AAV_sentinal_pico.cpp`, `aav_telemetry.hpp`, `lcd_display.cpp`, `lcd_display.hpp`, `CMakeLists.txt`, `pico_sdk_import.cmake` |

Copied into this repo on 9 Oct 2026; replaced by this program and deleted on 15 Oct 2026.
The original stays on GitHub at that commit. Who sends it the packets isn't in any repo
we have: by its "Waiting Pi..." screen, a Raspberry Pi.

## What stayed the same

| Thing | Value |
|---|---|
| I2C | a device at 0x42 on I2C0: SDA GP0, SCL GP1, the internal pull-ups on |
| The packet | 46 bytes, packed, little-endian, starting 0xAA 0x01, ending in an XOR checksum (`sentinel::telemetry`) |
| The LCD | 16x2 HD44780, 4-bit: RS GP7, E GP8, D4-D7 GP9-GP12 |
| The matrix | MAX7219 on SPI1 at 1 MHz: CLK GP14, DIN GP15, CS GP13; brightness 8 |
| The LED bar | GP28, 27, 26, 22, 21, 20, 19, 18, 17, 16 (LED 0 to 9) |
| The knob | KY-040: CLK GP2, DT GP3, switch GP4 |
| The button, the buzzer, the LED | GP5, GP6, GP25 |
| The pages | the same 13, in the same order; the knob turns, its switch pins, the button goes home |
| Timings | home after 10 s unpinned; link lost after 3 s, warned again every 10 s; battery every 30 s; the matrix swaps every 0.8 s |
| The beeps and the pictures | the same patterns |

## What changed

| Change | Why |
|---|---|
| One knob click is one page | the old code moved a page on every pin change its loop saw: one click could move several |
| The buttons are debounced both ways | the old 200 ms lockout counted a long press twice (on release) |
| A beep never stops the program | the old one held its loop, with the GPIO interrupts off, while the buzzer sounded |
| An error beeps once, when it starts | the old one beeped on every packet while the error lasted |
| The LCD is written only when a line changes, at microsecond timing | the old driver waited 10 ms a nibble: about 0.7 s to redraw |
| Every line fits in 16 characters | two old pages lost their last character; the Jrk flag pages lost their title |
| The Jrk flags use Pololu's bits | five of the old six names were on the wrong bits (`sentinel::telemetry::JrkFlag`) |
| The e-stop's cross, and a lost link's "!", stay on the matrix | the old cross lasted 0.8 s; "!" was drawn but never used |
| A 0.5 s hardware watchdog | a hang resets the chip |
| Reads get zeros | the old code didn't answer reads at all |
