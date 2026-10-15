# First flash on the bench: the Rust ESP32

The plan for the first time the Rust program (`firmware/spine/boards/esp32-umod`) goes onto
the car's ESP32 control board. Do it with Ben, **wheels off the ground**, with the C++
ready to go back on. What the program is: [Rust firmware](rust-firmware.md).

[[untested]] Nothing here has been done yet.

!!! warning "Before you start"
    - The car on stands: **all four wheels off the ground**.
    - A second person at the **red e-stop button**. It cuts power by itself, whatever
      the program does.
    - The RC transmitter on, override switch **off**.
    - Know how to roll back (the last section). Try it once before the first flash.

## What you need

| Thing | Why |
|---|---|
| A laptop with this repo, `pixi run esp-tools` done | builds and flashes |
| A USB cable to the ESP32 MicroMod's USB port | flashing and the log |
| The Motor-Pi running `aav_legacy` (`pixi run car` profile, or `legacy.launch.py`) | sends the frames |
| The RC transmitter | the override |
| A multimeter | the DAC output, the direction pin |

## 1. Build, and save the C++ first

| Step | Command | Check |
|---|---|---|
| 1 | `pixi run -e firmware legacy-esp32` | the C++ still builds: it is the way back |
| 2 | `vendor/cargo-tools/bin/espflash read-flash 0 0x400000 backup-esp32.bin` | a copy of what is on the board now (4 MB). Keep it off git |
| 3 | `pixi run esp-build` | `Finished`; the program is `firmware/spine/boards/esp32-umod/target/xtensa-esp32-none-elf/release/spine-esp32-umod` |

## 2. Flash

| Step | Command | Check |
|---|---|---|
| 1 | `vendor/cargo-tools/bin/espflash list-ports` | the board's port (a Mac: `/dev/cu.usbserial-…`) |
| 2 | `pixi run esp-flash` (add `--port <port>` if asked) | it flashes, resets, and shows the log |
| 3 | read the first lines | `spine-esp32-umod 0.1.0, link: Motor-Pi UART; the last reset: …` |

If it won't connect: hold the board's BOOT button while it starts flashing.

## 3. Checks, wheels off the ground

Do them in order. Stop at the first one that fails, and roll back.

| # | Do | Expect |
|---|---|---|
| 1 | Power on, nothing else | brake pulled (3500), steering centred (1950), DAC 0 V. Log: `STATUS mode=Manual … faults=0x0000`. Status LED blinks fast |
| 2 | Unplug a Jrk's I2C, then plug it back | the red LED and a fault bit (8 steering, 16 brake) while it is out |
| 3 | Start the Motor-Pi's bridge, with ego stale | the bridge sends stop frames: brake stays full |
| 4 | Drive slowly from ROS (keyboard or joystick, 0.3 m/s) | `mode=Computer`, green LED, brake lets go (400), the DAC rises smoothly (600 codes a second at most), the wheels turn **forward** |
| 5 | Steer left from ROS | the wheels turn **left**. If right: the steering sign (Q2), in `legacy.yaml` |
| 6 | Stop from ROS | throttle 0; the bridge's hold brake: target 1050, as the C++ gave it |
| 7 | Reverse slowly | the direction changes only with the DAC at 0; the wheels turn backwards |
| 8 | While driving, stop the bridge (Ctrl-C) | within 0.2 s: throttle 0, brake full, `faults` has 1 (timeout) |
| 9 | Start the bridge again | brake stays on until ego is stale or stops (a stop frame), then it drives again |
| 10 | RC override switch on, gear forward, a little throttle | `mode=Rc`, blue LED, wheels turn; ROS commands ignored |
| 11 | RC: switch the transmitter off | within 0.1 s: brake full, `faults` has 256 (RC lost) |
| 12 | RC override off | back to the computer, or Manual |
| 13 | The red e-stop button | the car stops by itself, as today |
| 14 | 10 minutes of 1 to 13, mixed | no unexpected resets in the log (`the last reset:` stays the power-on one) |

Compare with the C++ (the table "The C++ beside the Rust" in
[Rust firmware](rust-firmware.md)): the differences marked ⚠️ are expected.

## 4. Roll back to the C++

Any time something is wrong:

| Step | Command |
|---|---|
| 1 | press the e-stop; unplug the Motor-Pi's bridge |
| 2 | `pixi run -e firmware legacy-esp32 -t upload` (PlatformIO builds and flashes the C++; `src/secrets.h` for its WiFi) |
| 3 | or the backup: `vendor/cargo-tools/bin/espflash write-bin 0 backup-esp32.bin` |
| 4 | check the C++ is back: its log says `=== ESP32: AAV Controller ===` |

## After the bench

| When | Then |
|---|---|
| All 14 checks pass | the same on the ground, at walking speed, with Ben |
| Proven on the car | Ben decides: the C++ in `firmware/legacy/aav_umod_esp32` is removed, and `docs/firmware.md` updated |
