# The HUD (in-car screen)

The 2025-26 team built a touchscreen app for the car. It is copied in unchanged and
**not yet connected to the new stack**: it still listens to the 2025-26 topic names, and
its speed and GPS only ever came from mock publishers.

## What it is

Three programs that run together on the UI Raspberry Pi (Ubuntu 22.04 in 2025-26, two
800x480 screens):

| Part | Where | What it does |
|---|---|---|
| Front end | `hud/flutter_pi/` (Flutter/Dart) | Screens: home (speed, gear, stop-sign alert), map with destination search, camera page. Talks to the back end over Socket.IO. |
| Back end | `src/hud/maincar/` (ROS 2 Python node + Flask) | A ROS node that subscribes to car topics and pushes them to the front end over Socket.IO (port 5000), and publishes the chosen destination and route. |
| Routing | OSRM in Docker (`hud/scripts/osrm_bootup.sh`) | Offline road routing for Ontario on port 5001. The map data file (`ontario-*.osrm`) was on the Pi, not in git. |

`hud/scripts/*.sh` are the systemd boot scripts the old Pi ran. They hard-code the old
user's home paths.

## How it would fit the new graph

The HUD is a reader of TELEMETRY and a source of goals. It is not a driver that steers:

- **Reads:**
  - `/vehicle/status`: speed, mode, armed, e-stop, faults;
  - `/gps/filtered` or `/gps/fix`: position on the map;
  - the feedback of the Nav2 action it started: distance remaining, state.
- **Starts:** a `follow_gps_waypoints` goal (`nav2_msgs/action/FollowGPSWaypoints`). Its
  points come from the OSRM route between the car and the destination.
- **Remote driving (later):** if the HUD ever drives, it publishes on `/cmd_vel/remote`
  (priority 90) like any other driver.

The exact topic changes are listed in `src/hud/maincar/PROVENANCE.md` under "Port to the
2026-27 contract".

## Options for the port

1. **Keep Flask and Flutter, and rewire the node.** Smallest change:
   - Replace the subscriptions with the topics above.
   - Use an action client for the GPS goal.
   - Delete the mock publishers.

   Flask and flask-socketio must come from apt on Ubuntu 24.04 (`python3-flask`,
   `python3-flask-socketio`), because 24.04 blocks `pip install` into the system Python.
2. **Drop Flask and talk to ROS directly from the browser or Flutter** through
   `rosbridge_server` (WebSocket, port 9090) or `foxglove_bridge` (port 8765). That
   removes one process, but the Flutter app needs a ROS client library.

Either way, start with **Foxglove** as the operator's screen while the HUD is ported.
Foxglove already shows speed, the map, paths and costmaps from `foxglove_bridge`, which
`car.launch.py` starts on port 8765.

## Before running it on the car

- The Firebase service-account keys and the GitHub token in the 2025-26 User-Interface
  repository are public. They were not copied here; revoke them (design doc Q34).
- 96% of that repository was `node_modules`, and only the Flutter app and the ROS node
  were copied.
