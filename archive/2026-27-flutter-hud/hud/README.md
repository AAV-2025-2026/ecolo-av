# hud

## Overview

The 2025-26 team's touchscreen HUD, as they left it. Its back end is ported into ROS as
`ros/hud/aav_hud`. **The raylib HUD replaces it** (Ben, 15 Oct, Q29:
`ros/hud/aav_hud_raylib`). The app stays until the new one matches it.

`COLCON_IGNORE` keeps colcon out of this folder.

## Subdirectories & Boundaries

| Folder | What it is |
|---|---|
| [flutter_pi](./flutter_pi/README.md) | the Flutter app: a dashboard window and a map window (camera on top). Talks to `aav_hud` over Socket.IO and HTTP |
| [scripts](./scripts/README.md) | the 2025-26 UI Pi's systemd start-up scripts (Flask, Flutter, OSRM). Reference only: ours are in `tools/screens/` |

## Invariants

- The app only **sets** the e-stop, never clears it.
- Its event names match `ros/hud/aav_hud/aav_hud/events.py` (a test checks).
- Both folders hold inherited code: record every change in their `PROVENANCE.md`.

## Side Effects

- `POST /receive` sends the car somewhere; `POST /estop` brakes it.
- Network to the back end (port 5000), OSRM (5001) and the tile server (8080).

## Verification

- Run: `pixi run hud-test` (needs `pixi run get-flutter` once).
