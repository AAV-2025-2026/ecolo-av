# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/User-Interface @ main (e6e6b1e565),
ros2_ws/src/maincar. On 2026-10-10 the package was renamed `aav_hud` and ported to the
2026-27 topics (see "Port to the 2026-27 contract" below).

## Files

| Now | Came from | State |
|---|---|---|
| `package.xml`, `setup.py`, `setup.cfg` | the same files | rewritten for `aav_hud` |
| `resource/aav_hud` | `resource/maincar` | renamed (an empty marker) |
| `aav_hud/__init__.py` | `maincar/__init__.py` | renamed (empty) |
| `aav_hud/hud_server.py` | `maincar/ui_flask.py` | rewritten: the ROS node |
| `aav_hud/web.py` | `maincar/ui_flask.py` | new: its Flask and Socket.IO part |
| `aav_hud/events.py`, `route.py`, `trip.py`, `png.py` | none | new: the conversions, no ROS |
| `launch/hud.launch.py` | `launch/launch.py` | rewritten |
| `config/hud_server.yaml` | none | new: the parameters |
| `test/` | none | new |
| none | `maincar/ui_test.py` | deleted: the mock publisher |

## Changes

- `package.xml`: `<depend>flask</depend>` became `python3-flask`, the rosdep key that
  exists (`flask` doesn't resolve, so `rosdep install` failed).
- 2026-10-10, from the Jazzy port audit:
  - `ui_flask.py`: `mock_gps_altitude` -> `mock_gps_z` (NameError on `/`);
    `list_lastestRoute` -> `list_latestRoute` (the route was never stored);
    `socketio.run(..., allow_unsafe_werkzeug=True)`, without which Flask-SocketIO 5.3+
    won't start under systemd; `.warn(` -> `.warning(`.
  - `ui_flask.py`, `ui_test.py`: shut down cleanly (`ExternalShutdownException`,
    `destroy_node`, `rclpy.try_shutdown`).
  - `package.xml`: added `sensor_msgs`, `launch` and `launch_ros`; dropped the four
    test_depends (the tests weren't copied).
- 2026-10-10, the port (branch `hud-port`):
  - Renamed `maincar` -> `aav_hud` (docs/conventions.md). The executable `ui_flask` is
    now `hud_server`, and so is the node (it was `flask_ros2_node`, in namespace `ui`).
  - Deleted the mock inputs (`/mock_speed`, `/mock_gps`, `/mock_stop_sign_detected`) and
    their publisher `ui_test.py`. The bench mode's mock sensors replace them.
  - Moved the global variables into the node, and the conversions into modules with
    tests. It now passes `ament_flake8` and `ament_pep257`.
  - Stopped publishing `/ui/destination_point` and `/ui/route`.
  - Dropped the HTTP route `/gps`: it only showed the mock altitude.
  - `host` is now a parameter, default `127.0.0.1` (it was `0.0.0.0`): a locked route
    starts the car, so only the HUD's own computer may send one. The app connects to
    `127.0.0.1` anyway.
  - The MediaMTX address is now a parameter. Its default is `192.168.1.118`, as in the
    app's camera page; the old back end said `192.168.1.101`.
  - Werkzeug no longer logs every request: Socket.IO polling makes several a second.
  - If the web server can't start (the port is taken), the node stops with exit code 1.
    Before, it ran on with no server.
  - A refused route says why it may have been refused: Nav2 refuses goals until its
    lifecycle manager has activated the waypoint follower. The bench showed it.
  - A late answer to an older goal can no longer overwrite "nav2_not_running".
  - The camera: `/camera/latest.png` and `/camera/stream` serve `/camera/image_raw` as
    PNG pictures. The node subscribes only while someone fetches them. The old code had
    `/camera/cam1/image_raw` and `/camera/cam2/image_raw` commented out.

## Port to the 2026-27 contract

Done on 2026-10-10. Each 2025-26 input, and what replaced it:

| 2025-26 | type | now |
|---|---|---|
| `/rtos/speed` | Float32 | `/vehicle/status` `.speed` (aav_interfaces/VehicleStatus) |
| `/rtos/gear` | UInt8 | `/vehicle/status`: mode, armed, e-stop, sign of the speed |
| `/rtos/gps` | NavSatFix | `/gps/filtered` (launch argument `gps:=/gps/fix` for the raw fix) |
| `/aav/stop_sign_detected` | Bool | `/perception/stop` |
| `/camera/cam1/image_raw`, `/camera/cam2/image_raw` (commented out) | Image | `/camera/image_raw`, served at `/camera/latest.png` and `/camera/stream` |
| `/nav/path_distance`, `/nav/nav_status` | Float32, String | the feedback and result of the `/follow_gps_waypoints` goal |
| `/ui/destination_point`, `/ui/route` (published) | Point, String | a `/follow_gps_waypoints` goal (nav2_msgs/action/FollowGPSWaypoints) |

The Socket.IO events the app listens for keep their names and keys:

| Event | Keys the app reads | From |
|---|---|---|
| `mock_speed_update` | `mock_speed` | `/vehicle/status` |
| `mock_gps_update` | `mock_latitude`, `mock_longitude` | `/gps/filtered` |
| `mock_stop_sign_alert` | `mock_sign_detected`, `message` | `/perception/stop` |
| `nav_state` | `distance`, `status` | the Nav2 goal |

- The names still said "mock", but the data was real. Renamed with the app on
  2026-10-11 (below).
- New event `vehicle_status`: mode, armed, e-stop, a gear letter, faults. The app has
  no screen for it yet.
- Dropped `real_speed_update`, `real_gps_update`, `real_stop_sign_alert` and
  `real_gear_update`: the app never listened for them. Their gear codes also disagreed
  with the 2025-26 RTOS (the back end said 0 = drive, the RTOS 0 = park).
- 2026-10-10: `launch/hud.launch.py`: the launch argument `gps` is now `gps_topic`.
  Included launch files share their arguments, and bench.launch.py's localization takes
  `gps:=true`, so the HUD subscribed to a topic called `/true`.

## With the app's changes (2026-10-11)

The app and the back end changed together (docs/hud.md, "What changed in the app").

| Event (was) | Now | Keys (were) | Keys now |
|---|---|---|---|
| `mock_speed_update` | `speed` | `mock_speed` | `speed` |
| `mock_gps_update` | `position` | `mock_latitude`, `mock_longitude` | `latitude`, `longitude` |
| `mock_stop_sign_alert` | `stop_sign` | `mock_sign_detected`, `message` | `detected`, `message` |
| none | `battery` | none | `voltage`, `percentage` (0-100), `current`; null if not measured |

- `hud_server.py`: publishes `/estop` true for the app's e-stop button: at once, then
  every 0.1 s, five in all, reliable like the backends' subscriptions. It never
  publishes false. The press also cancels the HUD's route. If nothing subscribes
  to `/estop`, `POST /estop` answers 503, so the app never says "sent" to nobody.
- `web.py`: `POST /estop`, which can only set the e-stop. `POST /cancel` is now what the
  map page's Unlock and Clear send.
- `hud_server.py`, `events.py`: subscribes to `/battery_status` and sends `battery`.
- Dropped MediaMTX: the `stream_info` event, `GET /stream-info`, and the parameters
  `mediamtx_host`, `mediamtx_webrtc_port`, `mediamtx_rtsp_port`, `stream_path`. The
  camera page shows `/camera/latest.png` now.
- `/camera/latest.png` and `/camera/stream` serve no picture older than
  `camera_stale_after` (2 s): an old picture mustn't pass for a live one.
- `launch/hud.launch.py`: arguments `hud_host` and `hud_port`, so the bench can run the
  back end on another port (a Mac's AirPlay holds 5000).
- `test_events.py` checks that the app's `hud_events.dart` lists the same event names.

## Topic names by area (2026-10-15)

The topics move to their areas (docs/naming.md, Decided by Ben on 15 Oct). Only names
change, never the logic:

- `hud_server.py`, `events.py`, `web.py`, `config/hud_server.yaml`, `launch/hud.launch.py`,
  `package.xml`, `test/test_hud_server.py`: `/gps/filtered` -> `/localization/gps/fix`,
  `/perception/stop` -> `/perception/stop_sign`, `/battery_status` -> `/vehicle/battery`,
  `/camera/image_raw` -> `/sensors/camera/front_left/image_raw`, `/estop` ->
  `/safety/estop`. The HTTP routes (`POST /estop`, `/camera/...`) are unchanged.
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.
- 25 Oct 2026: `launch/hud.launch.py`: its docstring said car.launch.py includes it; only
  bench.launch.py `hud:=true` and sim.launch.py `hud_web:=true` do. Docstring only.
