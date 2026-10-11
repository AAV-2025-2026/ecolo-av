#!/usr/bin/env bash
# Build today's ESP32 firmware (firmware/legacy/aav_umod_esp32) with PlatformIO.
#
# usage: pixi run -e firmware legacy-esp32 [pio run options]   (-t upload flashes it)
#
# Its WiFi name and password live in src/secrets.h, which git ignores. Without one, the
# build uses the placeholders from secrets.h.example: fine for a test build, but a board
# flashed with it can't join the car's WiFi (for its update page).
set -euo pipefail
cd "$(dirname "$0")/../firmware/legacy/aav_umod_esp32"
if [[ ! -f src/secrets.h ]]; then
  cp src/secrets.h.example src/secrets.h
  echo "No src/secrets.h yet: using the placeholders from secrets.h.example." >&2
fi
exec pio run "$@"
