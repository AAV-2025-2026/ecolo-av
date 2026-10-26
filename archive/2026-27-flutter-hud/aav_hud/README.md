# aav_hud

## Overview

The back end of the HUD's touchscreen app (`hud/flutter_pi`). One process: the ROS node
`hud_server` and a Flask and Socket.IO web server. It turns the car's topics into the
events the app shows, the route the app locks into a Nav2 goal, and the app's e-stop
button into `/safety/estop` true.

Inherited from the 2025-26 team (`AAV-2025-2026/User-Interface`), then ported to the
2026-27 topics: see [PROVENANCE.md](./PROVENANCE.md). The newer in-car screen is
[aav_hud_raylib](../aav_hud_raylib/README.md).

## Interface

### Node `hud_server`

| Direction | Name | Type |
|---|---|---|
| sub | `/vehicle/status` | aav_interfaces/VehicleStatus |
| sub | `/localization/gps/fix` (launch `gps_topic:=`) | sensor_msgs/NavSatFix |
| sub | `/perception/stop_sign` | std_msgs/Bool |
| sub | `/vehicle/battery` | sensor_msgs/BatteryState |
| sub | `/sensors/camera/front_left/image_raw` (only while someone watches) | sensor_msgs/Image |
| pub | `/safety/estop` (only `true`) | std_msgs/Bool |
| action client | `/follow_gps_waypoints` | nav2_msgs/action/FollowGPSWaypoints |

### Parameters (`config/hud_server.yaml`)

| Name | Default | Unit |
|---|---|---|
| `host`, `port` | 127.0.0.1, 5000 | |
| `max_event_rate` | 10.0 | Hz |
| `route_tolerance`, `waypoint_spacing` | 1.0, 5.0 | m |
| `camera_fps` | 5.0 | Hz |
| `camera_idle_timeout`, `camera_stale_after` | 5.0, 2.0 | s |

### Web server (`web.py`)

| Route | Does |
|---|---|
| `GET /` | the newest copy of every event, as JSON: a health check |
| `POST /receive` | the locked route, `[{lat, lon}, ...]`: Nav2 drives it |
| `POST /cancel` | stop following the route |
| `POST /estop` | `/safety/estop` true; 503 if nobody subscribes |
| `GET /camera/latest.png`, `/camera/stream` | the front left camera, as PNG |

Socket.IO events (`events.py`): `speed`, `position`, `stop_sign`, `battery`,
`vehicle_status`, `nav_state`. The app's `hud_events.dart` lists the same names.

### Launch

`hud.launch.py [gps_topic:=] [hud_host:=127.0.0.1] [hud_port:=5000]`. Started by
`bench.launch.py hud:=true` and `sim.launch.py hud_web:=true`.

### Modules

| Module | ROS? | Holds |
|---|---|---|
| `hud_server.py` | yes | the node |
| `web.py` | no | `HudWeb`: the routes and Socket.IO |
| `events.py` | no | messages to events: `speed_event`, `vehicle_event`, `position_event`, `stop_sign_event`, `battery_event`, `Throttle`; helpers `fix_position`, `gear`, `fault_names` |
| `route.py` | no | the app's route to waypoints: `simplify`, `space_out`, `headings`, `to_waypoints` |
| `trip.py` | no | `Trip`: the action's progress to `nav_state` |
| `png.py` | no | `encode`: a picture as PNG, standard library only |

## Invariants

- Publishes only `true` on `/safety/estop`: five times, 0.1 s apart, reliable. Clearing
  stays a person's act from a laptop, never this touchscreen.
- An e-stop press also cancels the route, so clearing it doesn't restart the trip.
- Listens on `127.0.0.1` by default: a locked route starts the car.
- No camera picture older than `camera_stale_after` is served.
- Event names change in this package and the app together (`test_events.py` checks).
- Waypoint headings are yaw in the map frame (ENU, 0 = east).
- The conversion modules have no ROS imports.

## Side Effects

- Listens for HTTP and Socket.IO on `host:port`.
- Sends Nav2 a `follow_gps_waypoints` goal, which drives the car.
- Exits with code 1 if the port is taken.

## Verification

```sh
pixi run build && colcon test --packages-select aav_hud && colcon test-result --verbose
```

`pixi run test` runs every package's tests. Without a car:
`ros2 launch aav_hud hud.launch.py`, then `curl http://127.0.0.1:5000/`.
