# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/User-Interface @ main (e6e6b1e565), scripts.

Files, unchanged unless listed under Changes:

- `README.md`
- `flask_bootup.sh`
- `flutter_bootup.sh`
- `osrm_bootup.sh`

## Changes

- 2026-10-10: `flask_bootup.sh` starts `ros2 launch aav_hud hud.launch.py`. The back end
  was renamed from `maincar` (its launch file was `launch.py`). The script still sources
  the old Humble workspace in `/home/aavui`: point it at this repo's
  `install/setup.bash` on the UI Pi.
