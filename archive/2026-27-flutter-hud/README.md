# archive/2026-27-flutter-hud

## Overview

The 2025-26 team's HUD, as we had ported it, put away on 25 Oct 2026 (Ben). The raylib
HUD (`ros/hud/aav_hud`) replaced it on 15 Oct (Q29: `docs/decisions.md`).

Reference only: nothing builds, tests or starts it. colcon skips it (`archive/COLCON_IGNORE`).

## Subdirectories & Boundaries

| Folder | What it was | Where it was |
|---|---|---|
| `hud/` | the Flutter touchscreen app (`flutter_pi`) and its boot scripts | `hud/` |
| `aav_hud/` | its back end: the ROS node `hud_server`, Flask and Socket.IO | `ros/hud/aav_hud` |
| `tools/` | `flutter.sh`, `get_flutter.sh`, `hud_test.sh`, `hud_fake_backend.py` | `tools/` |
| `img/` | two screenshots of the app | `docs/img/` |

Each keeps its own README and PROVENANCE.md, as they were on 25 Oct. Their paths and
links still point at the old places.

## What stayed in use

- `route.py` (a street route into Nav2 waypoints) moved to
  `ros/drivers/aav_routes/aav_routes/route.py`, with its tests.
- The place database `ottawa.db` still feeds the map window's search:
  `pixi run get-hud-map` downloads it into `maps/places/`.

## The original

The 2025-26 team's own repo is in `archive/User-Interface/`, with its history.
