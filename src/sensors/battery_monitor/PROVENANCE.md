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
- Still to do: port and baud are constants (`/dev/ttyUSB0`, 19200); make them parameters and add
  a udev rule so the name doesn't change between boots.
