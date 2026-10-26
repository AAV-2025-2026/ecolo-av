# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/AAV_cortex @ 6-pico2-aav-firmware (90de619e52), AAV_uMod_Firmware.

Files, unchanged unless listed under Changes:

- `.gitignore`
- `extra_includes.py`
- `platformio.ini`
- `src/main.cpp`
- `src/modules/dac/dac.cpp`
- `src/modules/dac/dac.h`
- `src/modules/globals.h`
- `src/modules/hardware_configs.h`
- `src/modules/jrk_g2/jrk_g2.cpp`
- `src/modules/jrk_g2/jrk_g2.h`
- `src/modules/rc_handler/rc_handler.cpp`
- `src/modules/rc_handler/rc_handler.h`
- `src/modules/ros2_handler/ros2_handler.cpp`
- `src/modules/ros2_handler/ros2_handler.h`
- `src/modules/web_handler/web_handler.cpp`
- `src/modules/web_handler/web_handler.h`
- `src/modules/websoc_serial/websoc_serial.h`

## Changes

- `src/main.cpp`: the WiFi name and password were removed and are now read from
  `src/secrets.h` (not in git; copy `src/secrets.h.example`). The old values are
  still public in the 2025-26 repository history, so change them on the router.
- Added `src/secrets.h.example`.
- `extra_includes.py` (10 Oct 2026): asks PlatformIO where the Arduino framework is,
  instead of a folder name from one student's machine
  (`framework-arduinoespressif32@3.20009.0`). The same framework version, 3.20009.0.
- `platformio.ini` (10 Oct 2026): `lib_extra_dirs` uses `${platformio.packages_dir}`
  instead of `~/.platformio/...@3.20009.0`, so it works wherever PlatformIO keeps its
  packages (ours: `vendor/platformio/`).
- With those two, it builds from a clean checkout: `pixi run -e firmware legacy-esp32`
  (10 Oct 2026, on a Mac: 48 s with the downloads; RAM 14.3%, flash 63.4%).
- 15 Oct 2026: not changed, but `ros2_handler.cpp` and `jrk_g2.cpp` are now also
  compiled on a laptop by `tools/tests/test_legacy_cpp.py`, to prove the Rust
  replacement (`firmware/spine/boards/esp32-umod`) sets the same targets. This folder
  stays until the Rust one is flashed and proven on the car.
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.
- Nothing else changed. Known problems are listed in `docs/firmware.md`
  (no command timeout, unauthenticated `/update` page, no feedback to the computer).
