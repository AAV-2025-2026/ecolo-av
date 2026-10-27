# hud/scripts

Flask, Flutter and OSRM need to run in parallel for UI to work.
these scripts are meant to be executed on startup using a systemd service.

- Flask is the back-end
- Flutter is the front-end
- OSRM is the routing and map data that Flutter uses.

## Overview

The 2025-26 team's start-up scripts for their UI Raspberry Pi (Ubuntu 22.04). Three
systemd **system** services ran one script each, from `/home/aavui/Desktop`. They are
kept as they were, for reference, until the team agrees to switch (A8 in
`docs/car-screens.md`).

Our way is different: two systemd **user** units, no sudo, no Docker, release builds, a
restart after a crash (`tools/screens/`, `docs/car-screens.md`).

## Interface

| Script | Starts | Port |
|---|---|---|
| `flask_bootup.sh` | the back end: `ros2 launch aav_hud hud.launch.py` | 5000 |
| `flutter_bootup.sh` | the app: `flutter run` (a debug build) in `flutter_pi`, with `GDK_BACKEND=x11` | - |
| `osrm_bootup.sh` | OSRM in Docker: `osrm-routed --algorithm mld` on `ontario-251116.osrm` | 5001 (Docker's 5000 inside) |

Each takes no arguments. The paths are written in the scripts.

## Invariants

- The paths are the 2025-26 Pi's: `/home/aavui/Desktop/User-Interface/...`,
  `/home/aavui/flutter`, `/home/aavui/Downloads/Data`. They work on no other computer.
- `flask_bootup.sh` still sources the old Humble workspace in `/home/aavui`. Point it at
  this repo's `install/setup.bash` before using it on a Pi.
- The OSRM data file (`ontario-*.osrm`) was on the Pi, not in git.
- Inherited code: every change goes in `PROVENANCE.md`.

## Side Effects

- Each script writes an empty test file on the Desktop: `systemd_flask_test.txt`,
  `systemd_flutter_test.txt`, `systemd_osrm_test.txt`.
- `flask_bootup.sh`: starts the ROS back end, which serves HTTP and publishes ROS topics.
- `flutter_bootup.sh`: opens the app's windows.
- `osrm_bootup.sh`: runs a Docker container (`ghcr.io/project-osrm/osrm-backend`),
  through snap's `docker.wrapper`, on port 5001.

## Verification

No tests. These scripts only run on the 2025-26 Pi. The app they start is tested by
`pixi run hud-test` (`hud/flutter_pi`); the back end by its package tests
(`colcon test --packages-select aav_hud`).

## Known trouble (2025-26 notes)

`osrm_bootup.sh` says `sudo docker run -t -i` failed under systemd (exit status 125 or
126). `systemctl status ui_osrm.service` shows which error stopped it.
