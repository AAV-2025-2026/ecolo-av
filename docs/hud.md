# The HUD (in-car screen)

The 2025-26 team built a touchscreen app for the car. Its back end, `aav_hud`, is ported
to our topics (10 October): it shows real data from the graph, and a locked route drives
the car through Nav2. The app itself (Flutter) still needs a few small changes.

## What it is

Three programs that run together on the UI Raspberry Pi (Ubuntu 22.04 in 2025-26, two
800x480 screens):

| Part | Where | What it does |
|---|---|---|
| Front end | `hud/flutter_pi/` (Flutter/Dart) | Screens: home (speed, gear, stop-sign alert), map with destination search, camera page. Talks to the back end over Socket.IO. |
| Back end | `src/hud/aav_hud/` (ROS 2 Python node + Flask) | `hud_server`: reads the car's topics and pushes them to the app over Socket.IO (port 5000); sends a locked route to Nav2. |
| Routing | OSRM in Docker (`hud/scripts/osrm_bootup.sh`) | Offline road routing for Ontario on port 5001. The map data file (`ontario-*.osrm`) was on the Pi, not in git. |

## What the back end reads and sends

| Name | Type | Use |
|---|---|---|
| `/vehicle/status` | `aav_interfaces/msg/VehicleStatus` | reads: speed, mode, armed, e-stop, gear, faults |
| `/gps/filtered` | `sensor_msgs/msg/NavSatFix` | reads: the car on the map (`gps_topic:=/gps/fix` for the raw fix) |
| `/perception/stop` | `std_msgs/msg/Bool` | reads: the stop-sign alert |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | reads, only while someone watches the camera page |
| `/follow_gps_waypoints` | `nav2_msgs/action/FollowGPSWaypoints` | sends the locked route as GPS waypoints, and shows Nav2's progress |

It publishes no topics. The 2025-26 `/ui/*` and mock topics are gone.

## Socket.IO events and web routes

The app's four events keep their names and keys, so the app works unchanged.

| Event | Carries |
|---|---|
| `mock_speed_update` | the speed from `/vehicle/status` (real now, despite the name) |
| `mock_gps_update` | latitude and longitude |
| `mock_stop_sign_alert` | the stop-sign alert, sent when it changes |
| `nav_state` | distance and status, plus the waypoint number and a message |
| `stream_info` | the camera stream's addresses |
| `vehicle_status` (new) | mode, armed, e-stop, gear, steering, throttle, brake, faults |

| Route | Does |
|---|---|
| `POST /receive` | takes the app's route, and starts the Nav2 goal. 400 for a bad route, 503 when Nav2 isn't running |
| `POST /cancel` | cancels the goal |
| `/camera/latest.png`, `/camera/stream` | the camera's pictures |
| `GET /` | the latest copy of every event, as JSON |

## Run it

```bash
pixi run bench hud:=true                      # with everything else, on the bench
ros2 launch aav_hud hud.launch.py             # on its own, next to a running profile
```

- It listens on 127.0.0.1 only, by default: a locked route moves the car, so only the
  HUD's own computer can send one. `host:=0.0.0.0` opens it to the network.
- On a Mac, AirPlay holds port 5000 for the network, so `host:=0.0.0.0` fails there.
- 86 tests: `pixi run test` runs them.

## What the app still needs

| Change | Why |
|---|---|
| An e-stop button that publishes `/estop` | the app has none |
| Unlock and Clear send `POST /cancel` | today they don't stop the car |
| Remove two 3 s debug delays in `sendRouteToFlask` | Lock Route waits 6 s |
| The camera page shows `/camera/stream` | it plays WebRTC from a fixed address |
| Rename the `mock_*` events, in the app and the back end together | the data is real now |
| A screen for the battery and the vehicle status | the back end could send them |

Keep the Flutter app or not: Q29. Meanwhile, **Foxglove** works as the operator's screen:
`foxglove_bridge`, on port 8765, shows speed, the map, paths and costmaps.

## Before running it on the car

- The Firebase service-account keys and the GitHub token in the 2025-26 User-Interface
  repository are public. They were not copied here; revoke them (design doc Q34).
- `hud/scripts/flask_bootup.sh` still sources the old `/home/aavui` workspace.
- Waypoints must be inside Nav2's map, and Nav2 slows down at each one.
