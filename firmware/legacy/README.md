# firmware/legacy

## Overview

Firmware inherited from the 2025-26 team, kept as it runs on the car today. Each folder
stays until its Rust replacement in `firmware/spine/` is flashed and proven on the car.

## Subdirectories & Boundaries

| Folder | What it is | Rust replacement |
|---|---|---|
| [aav_umod_esp32](./aav_umod_esp32/README.md) | the Arduino C++ ESP32 board that drives the car's actuators today: Motor-Pi UART frames or RC in; Jrks and the DAC out | [esp32-umod](../spine/boards/esp32-umod/README.md) |

## Invariants

- Reference only: fixes go into the Rust twin. Any change goes in the folder's `PROVENANCE.md`.
- Its WiFi credentials live in an untracked `secrets.h`. Never commit or quote them (Q34).
