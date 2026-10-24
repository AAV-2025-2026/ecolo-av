# First flash on the bench: the Rust ESP32

The plan for the first time the Rust program (`firmware/spine/boards/esp32-umod`) goes onto
the car's ESP32 control board. Do it with Ben, **wheels off the ground**, with the C++
ready to go back on. What the program is: [Rust firmware](rust-firmware.md).

[[untested]] Nothing here has been done on a board yet. The emulator has (next section).

!!! warning "Before you start"
    - The car on stands: **all four wheels off the ground**.
    - A second person at the **red e-stop button**. It cuts power by itself, whatever
      the program does.
    - The RC transmitter on, override switch **off**.
    - Know how to roll back (the last section). Try it once before the first flash.

## Before the board: the emulator

TODO 45 (Ben, 24 Oct): "if it doesn't get a heartbeat then it applys the breaks and stops
the acceleration". Proven first with no hardware at all: the same firmware, in
Espressif's ESP32 emulator (QEMU).

```text
 tools/esp32_qemu.py                         QEMU: an ESP32, running our firmware
   aav_legacy's frames, 50 Hz ──► UART1 ──► LegacyLink ──► spine-core ──► drivers
   reads the log          ◄────── UART0 ◄── EVENT / STATUS / DEVICES lines   │
                                                       stand-in Jrks, DAC ◄──┘
```

| Command | Does |
|---|---|
| `pixi run esp-qemu-tools` | downloads QEMU into `vendor/qemu` (once, 22 MB; macOS on Apple silicon) |
| `pixi run esp-qemu-check` | builds with `--features qemu`, boots it, runs 3 cycles, prints the table |

Each cycle: stop frames, drive frames (0.6 m/s), **silence**, then drive frames again
with no stop first.

### Results, 24 Oct (Ben's Mac)

| Cycle | Drove (DAC peak) | Timeout after the last frame | Full brake (3500) + DAC 0 | Fault bit 1 | Stays braked until a stop frame |
|---|---|---|---|---|---|
| 1 | yes (140) | 116 ms | 116 ms | yes | yes |
| 2 | yes (140) | 113 ms | 113 ms | yes | yes |
| 3 | yes (140) | 113 ms | 113 ms | yes | yes |

Over six runs: **111 to 120 ms**, every cycle passed. That is the 100 ms timeout, plus
up to two 10 ms ticks (the tick that reads the last frame, the tick that notices).
Within the 0.2 s of check 8 below. The check fails above 200 ms: a firmware built with a
400 ms timeout, on purpose, failed it (410-417 ms).

The times are the firmware's own clock. QEMU's clock follows the Mac's (no `-icount`):
over each run they agreed to 0.1 %.

### What it did and didn't exercise

| Part | In QEMU |
|---|---|
| spine-core, the 100 ms timeout, the latch, the re-arm | ✅ the real code |
| The UART link: frames, checksum, resync (`legacy-link`) | ✅ the real code, real bytes on UART1 |
| The Jrk, DAC and expander drivers, and their order | ✅ the real code; the bytes go to stand-ins |
| The hardware watchdog (TIMG1, 100 ms) | ✅ on and fed; it never fired |
| The Jrks, the DAC, the expander themselves | ❌ stand-ins (`spine_board::StandInBus`): QEMU can't add I2C devices |
| Embassy's timer and interrupts | ❌ a busy-wait tick instead: QEMU's interrupt matrix has no status registers |
| The RC receiver (iBUS), the LEDs, CAN | ❌ silent, unwired, not built |
| The real chip's timing, the Motor Pi, the cable | ❌ the bench, below |

### Found on the way

| What | Fixed |
|---|---|
| The firmware never turned the FPU on: it relied on the chip's reset state. QEMU starts with it off, and the first interrupt crashed (a double exception) | ✅ `enable_fpu()` in `main.rs`, on every build |
| The log had no times | ✅ `t=` (ms since boot) on every line, and an `EVENT` line at each change |

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
| 1 | Power on, nothing else | brake pulled (3500), steering centred (1950), DAC 0 V. Log: `STATUS t=… mode=Manual … faults=0x0000`. Status LED blinks fast |
| 2 | Unplug a Jrk's I2C, then plug it back | the red LED and a fault bit (8 steering, 16 brake) while it is out |
| 3 | Start the Motor-Pi's bridge, with ego stale | the bridge sends stop frames: brake stays full |
| 4 | Drive slowly from ROS (keyboard or joystick, 0.3 m/s) | `mode=Computer`, green LED, brake lets go (400), the DAC rises smoothly (600 codes a second at most), the wheels turn **forward** |
| 5 | Steer left from ROS | the wheels turn **left**. If right: the steering sign (Q2), in `legacy.yaml` |
| 6 | Stop from ROS | throttle 0; the bridge's hold brake: target 1050, as the C++ gave it |
| 7 | Reverse slowly | the direction changes only with the DAC at 0; the wheels turn backwards |
| 8 | While driving, stop the bridge (Ctrl-C) | within 0.2 s: throttle 0, brake full, `faults` has 1 (timeout). The `EVENT` line's `t=` says when (QEMU: 111-120 ms) |
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
