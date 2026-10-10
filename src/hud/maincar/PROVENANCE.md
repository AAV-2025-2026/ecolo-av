# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/User-Interface @ main (e6e6b1e565), ros2_ws/src/maincar.

Files, unchanged unless listed under Changes:

- `launch/launch.py`
- `maincar/__init__.py`
- `maincar/ui_flask.py`
- `maincar/ui_test.py`
- `package.xml`
- `resource/maincar`
- `setup.cfg`
- `setup.py`

## Changes

- `package.xml`: `<depend>flask</depend>` became `python3-flask`, the rosdep key that
  exists (`flask` doesn't resolve, so `rosdep install` failed).

## Not copied

- `test/` (ament copyright/flake8/pep257 template tests), the empty `ui_fetch.py`
  and `ui_push.py`, `__pycache__/` and a committed colcon `log/`.

## Port to the 2026-27 contract (to do; see docs/hud.md)

This node still listens to the 2025-26 topics. Change these:

| 2025-26 topic | type | becomes |
|---|---|---|
| `/rtos/speed` | Float32 | `/vehicle/status` (aav_interfaces/VehicleStatus `.speed`) |
| `/rtos/gear` | UInt8 | `/vehicle/status` (`.mode`, sign of `.speed`) |
| `/rtos/gps` | NavSatFix | `/gps/filtered` (or `/gps/fix`) |
| `/nav/path_distance`, `/nav/nav_status` | Float32, String | feedback of the Nav2 action the HUD starts |
| `/ui/destination_point` | Point | a `follow_gps_waypoints` goal (nav2_msgs/action/FollowGPSWaypoints) |
| `/ui/route` | String (OSRM JSON) | the same goal: the route's points become the GPS waypoints |
| `/aav/stop_sign_detected` | Bool | perception, later |
