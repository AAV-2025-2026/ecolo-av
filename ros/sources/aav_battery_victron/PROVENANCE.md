# Provenance

Copied on 2026-10-09 from github.com/Carleton-AAV-Capstone/Battery-Monitor-ROS @ default branch (downloaded 2026-10-09), battery_monitor.

Files, unchanged unless listed under Changes:

- `aav_battery_victron/BatteryStatePublisher.py`
- `aav_battery_victron/HeartbeatPublisher.py`
- `aav_battery_victron/VEDirect.py`
- `aav_battery_victron/__init__.py`
- `aav_battery_victron/battery_monitor.py`
- `package.xml`
- `setup.cfg`
- `setup.py`
- `test/test_copyright.py`
- `test/test_flake8.py`
- `test/test_pep257.py`

## Changes (2026-10-09, porting to Jazzy so it runs)

- Added `resource/aav_battery_victron`; `setup.py` needs it and the build failed without it.
- `battery_monitor.py`: import `TimePublisher as HeartbeatPublisher` (the class was never
  called HeartbeatPublisher, so the node crashed on start); stamp `BatteryState.header`.
- `HeartbeatPublisher.py`: `self.publisher_` -> `self.publisher` (crashed on first publish).
- `package.xml`: declared rclpy, sensor_msgs, std_msgs and python3-serial.

## Changes (2026-10-10)

- All Python restyled to ROS's Python rules (ament_flake8, ament_pep257) with `ruff format` and isort-style import sorting, then the last errors by hand. Formatting only, except where listed:
  - `battery_monitor.py`: imports its modules as `battery_monitor.X`, so `setup.py` no
    longer copies them into `lib/`. `port` (default `/dev/aav/battery`, the udev name)
    and `baud` (19200) are parameters. The read loop stops on Ctrl-C and cleans up.
  - `VEDirect.py`: the loop variable `chr` is now `ch` (it hid the builtin).
  - `HeartbeatPublisher.py`: dropped an unused `import rclpy`.
- `setup.py`: `tests_require` -> `extras_require={'test': ['pytest']}`. setuptools 79
  ignores `tests_require`, so colcon ran no tests and failed. A real description.

## Topic names by area (2026-10-15)

The topics move to their areas (docs/naming.md, Decided by Ben on 15 Oct). Only names
change, never the logic:

- `aav_battery_victron/battery_monitor.py`: `/battery_status` -> `/vehicle/battery`,
  `/battery_monitor_heartbeat` -> `/vehicle/battery/heartbeat`.
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.
- 25 Oct 2026: `battery_monitor.py` publishes only when the newest block holds a
  reading (V, I, SOC or VS), so a history block no longer re-sends old readings;
  `VEDirect.py` keeps that block as `last_block`. Added `test/test_vedirect.py`.
- 25 Oct 2026: `package.xml`: a real description in place of "TODO: Package description".

## Renamed (2026-10-26)

- The package `battery_monitor` is `aav_battery_victron` (`aav_<kind>_<maker>`, `docs/conventions.md`):
  its folder, its module (`battery_monitor/` -> `aav_battery_victron/`), `resource/` marker,
  `package.xml`, `setup.py`, `setup.cfg`, and the imports in `battery_monitor.py` and
  `test/test_vedirect.py`. The paths in the list above are the new ones.
- Only names change: the executable `battery_monitor`, the nodes
  (`battery_state_publisher`, `heartbeat_publisher`) and the topics stay.
