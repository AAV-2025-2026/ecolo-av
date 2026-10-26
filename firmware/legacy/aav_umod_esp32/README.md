# aav_umod_esp32: today's ESP32 firmware (2025-26, C++)

## Overview

The 2025-26 team's firmware for the car's control board: a SparkFun ESP32 MicroMod on
the AAV carrier. Arduino C++, built with PlatformIO. It is what drives the car today.

It takes commands from the Motor-Pi over UART, or from the RC transmitter when its
override switch is on, and drives the steering, the brake and the throttle.

**Inherited.** Where it came from, and every change since: `PROVENANCE.md`. Its Rust
replacement is `firmware/spine/boards/esp32-umod`; this folder stays until that one is
flashed and proven on the car.

## Interface

### What comes in

| Input | How |
|---|---|
| The Motor-Pi | UART1 on GPIO16 (RX) / 17 (TX), 115200 8N1: 13-byte frames from `aav_legacy`'s `legacy_uart_bridge` |
| The RC receiver | iBUS on UART2, GPIO32, 115200 (IBusBM library) |
| A browser | WiFi: a status page and a log, below |

The 13-byte frame: three little-endian `f32` (steering, speed, accel, each -1 to 1), then
the sum of bytes 0 to 11. No header. The Rust twin is `firmware/spine/crates/legacy-link`.

### What goes out

| Device | Bus | Address or pin |
|---|---|---|
| Jrk G2, steering | I2C, SDA 21, SCL 22 | 0x05 |
| Jrk G2, brake | I2C | 0x04 |
| DAC (throttle) | I2C | 0x0C |
| PCA9555 (direction on P00) | I2C | its default 0x20 |
| LEDs | GPIO | status 2, red 18, green 19, blue 14 |

### On the WiFi

| Where | What |
|---|---|
| port 80, `/` and `/status` | a status page |
| port 80, `/scan` | the I2C devices found |
| port 80, `/update` | an over-the-air firmware update, **with no password** |
| port 81 | a WebSocket: the same log as the USB cable |

### Files

| File | What |
|---|---|
| `src/main.cpp` | `setup()` and `loop()`: WiFi, the buses, the devices, RC or ROS each loop. The Motor-Pi UART's pins (16, 17) and baud (115200) are hard-coded here |
| `src/modules/globals.h` | the shared includes and the global objects (`extern`); `main.cpp` and every module include it |
| `src/modules/hardware_configs.h` | the other pins (iBUS, LEDs, direction, I2C), the I2C addresses, the RC channels, the Jrk and DAC limits |
| `src/modules/ros2_handler/` | `handleROS2Messages()`: the Motor-Pi's frames to targets |
| `src/modules/rc_handler/` | `handleRCMode()`: the RC sticks to targets |
| `src/modules/jrk_g2/`, `src/modules/dac/` | `setSteer`, `setBrake`, `jrkSafeStop`; `writeDAC`, `writeDACRamped`, `ext_digitalWrite` |
| `src/modules/web_handler/`, `src/modules/websoc_serial/` | the web pages, `publishStatus()`, the WebSocket log |
| `src/secrets.h.example` | the template for the WiFi details |
| `platformio.ini`, `extra_includes.py` | the build: `esp32dev`, espressif32 6.3.2, the libraries |

## Invariants

- **Secrets:** the WiFi name and password are two C string `#define`s in `src/secrets.h`.
  Git ignores that file; copy `src/secrets.h.example` and fill it in. Never commit it, and
  never copy a value into a doc. The old values are public in the 2025-26 history: change
  them on the router (Q34).
- RC drives while channel index 5 (the transmitter's CH6) reads between 1500 and 2200;
  otherwise the Motor-Pi's frames do.
- A frame with a bad sum drops one byte and resyncs; a value outside -1 to 1 is turned
  down and the throttle ramps to 0.
- A brake demand (accel below -0.05) cuts the throttle at once.
- Reference only for new work: fixes go into the Rust twin. Record any change here in
  `PROVENANCE.md`.

Known problems (`docs/firmware.md`): no command timeout, no RC timeout, an OTA page with
no password, no feedback to the computer, an unconfirmed steering sign, and more.

## Side Effects

- Moves the car: the steering and brake Jrk G2s, the throttle DAC, the direction pin.
- Joins the car's WiFi; serves HTTP on port 80 and a WebSocket on port 81. Anyone on the
  WiFi can flash it through `/update`.
- Logs to the USB cable and the WebSocket.
- Drives all 16 PCA9555 pins high at boot.

## Verification

```sh
pixi run -e firmware legacy-esp32             # build with PlatformIO
pixi run -e firmware legacy-esp32 -t upload   # build and flash: bench only
```

`tools/legacy_firmware.sh` copies the example to `src/secrets.h` if there is none: fine
for a test build, but that board can't join the car's WiFi. PlatformIO's downloads go into
`vendor/platformio/`.

`tools/tests/test_legacy_cpp.py` (in `tools/test.sh`) compiles `ros2_handler.cpp` and
`jrk_g2.cpp` on a laptop, and checks they set the same targets as the Rust
`legacy-link`. It is skipped where there is no C++ compiler.
