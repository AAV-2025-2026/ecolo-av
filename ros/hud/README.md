# ros/hud

## Overview

The screens in the car. Two HUDs live here while the new one catches up with the old.

## Subdirectories & Boundaries

| Package | What it is |
|---|---|
| [aav_hud_raylib](./aav_hud_raylib/README.md) | **the new HUD** (Ben, 15 Oct, Q29): two Rust raylib screens, `hud` (status, e-stop, GO/STOP) and `map` (Nav2 map, place search, `/goal_pose`). Logic crates: [hud-core](./aav_hud_raylib/crates/hud-core/README.md), [map-core](./aav_hud_raylib/crates/map-core/README.md) |
| [aav_hud](./aav_hud/README.md) | the 2025-26 back end, ported: Flask and Socket.IO for the Flutter app in `hud/flutter_pi` |

## Invariants

- A HUD only **sets** the e-stop (`/safety/estop` true, 5 × 0.1 s), never clears it.
- A goal goes to Nav2 only after a person confirms it.
- In `aav_hud_raylib`, topic names live in config files, not in code. `aav_hud`'s
  `hud_server.py` hard-codes its topic and action names; only a launch remapping changes
  them (as `hud.launch.py` does for the GPS fix).

## Side Effects

- Opens windows (needs a screen) or a web server (127.0.0.1 by default).
- Publishes the e-stop, `/hud/heartbeat` and goals.

## Verification

- Run: `pixi run test` (also runs `cargo test -p hud-core -p map-core`).
