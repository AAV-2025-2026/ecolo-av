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
- Nothing else changed. Known problems are listed in `docs/firmware.md`
  (no command timeout, unauthenticated `/update` page, no feedback to the computer).
