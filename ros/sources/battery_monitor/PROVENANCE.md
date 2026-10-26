# Provenance

Copied on 2026-10-09 from github.com/Carleton-AAV-Capstone/Battery-Monitor-ROS @ default branch (downloaded 2026-10-09), battery_monitor.

Files, unchanged unless listed under Changes:

- `battery_monitor/BatteryStatePublisher.py`
- `battery_monitor/HeartbeatPublisher.py`
- `battery_monitor/VEDirect.py`
- `battery_monitor/__init__.py`
- `battery_monitor/battery_monitor.py`
- `package.xml`
- `setup.cfg`
- `setup.py`
- `test/test_copyright.py`
- `test/test_flake8.py`
- `test/test_pep257.py`

## Changes (2026-10-09, porting to Jazzy so it runs)

- Added `resource/battery_monitor`; `setup.py` needs it and the build failed without it.
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

- `battery_monitor/battery_monitor.py`: `/battery_status` -> `/vehicle/battery`,
  `/battery_monitor_heartbeat` -> `/vehicle/battery/heartbeat`.
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.
- 25 Oct 2026: `battery_monitor.py` publishes only when the newest block holds a
  reading (V, I, SOC or VS), so a history block no longer re-sends old readings;
  `VEDirect.py` keeps that block as `last_block`. Added `test/test_vedirect.py`.
- 25 Oct 2026: `package.xml`: a real description in place of "TODO: Package description".
