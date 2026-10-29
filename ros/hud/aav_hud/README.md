# aav_hud

## Overview

The car's two screens, in Rust with raylib. Each is one program that is also its ROS
node (rclrs):

- `hud`, the in-car screen: speed, mode, the e-stop button, GO / STOP, steering,
  throttle and brake, GPS, topic health, the stop-sign alert and the camera;
- `map`, the big screen's map window: Nav2's map over an offline street map, the car,
  the plan, the goal, the distance left, and a place search.

It was called `aav_hud_raylib` until 25 Oct, when the 2025-26 Flutter app and its Flask
back end (then `aav_hud`) went to `archive/2026-27-flutter-hud/` and this package took
the name.

A Cargo workspace that colcon builds through `CMakeLists.txt`. More in docs/hud.md and
docs/car-screens.md.

## Interface

### Crates

| Crate | Holds |
|---|---|
| [`hud-core`](./crates/hud-core/README.md) | the HUD's logic: no ROS, no raylib |
| [`map-core`](./crates/map-core/README.md) | the map window's logic: no ROS, no raylib |
| `crates/hud-app` | binary `hud`: the window (`ui.rs`) and the node (`ros.rs`, feature `ros`) |
| `crates/map-app` | binary `map`: the same shape, plus the street map and place search |

### Node `hud` (topic names from `config/hud.yaml`)

| Direction | Parameter: default topic | Type |
|---|---|---|
| sub | `vehicle_status_topic`: `/vehicle/status` | aav_interfaces/VehicleStatus |
| sub | `gps_topic`: `/sensors/gps/fix`; `gps_filtered_topic`: `/localization/gps/fix` | sensor_msgs/NavSatFix |
| sub | `stop_sign_topic`: `/perception/stop_sign` | std_msgs/Bool |
| sub | `battery_topic`: `/vehicle/battery` | sensor_msgs/BatteryState |
| sub | `camera_topic`: `/sensors/camera/front_left/image_raw` | sensor_msgs/Image |
| sub | `source_topic`: `/system/source` (latched) | aav_interfaces/DataSource |
| sub | `watchdog_topic`: `/safety/sensor_watchdog/state` | std_msgs/String |
| sub | `output_mux_topic`: `/safety/output_mux/state` | std_msgs/String |
| pub | `estop_topic`: `/safety/estop` (only `true`) | std_msgs/Bool |
| pub | `heartbeat_topic`: `/hud/heartbeat` (10 Hz while it draws) | std_msgs/UInt64 |

Parameter `stale_after` (1.0 s): a quieter topic shows STALE.

### Node `map` (topic names from `config/map.yaml`)

| Direction | Parameter: default topic | Type |
|---|---|---|
| sub | `map_topic`: `/map` (latched) | nav_msgs/OccupancyGrid |
| sub | `odom_topic`: `/localization/odom/global` | nav_msgs/Odometry |
| sub | `plan_topic`: `/plan`; `street_route_topic`: `/drivers/nav/route/path` | nav_msgs/Path |
| sub, pub | `goal_topic`: `/goal_pose` (published after DRIVE HERE, then CONFIRM) | geometry_msgs/PoseStamped |
| sub | `source_topic`: `/system/source` | aav_interfaces/DataSource |
| sub | `watchdog_topic`: `/safety/sensor_watchdog/state` | std_msgs/String |

Other parameters: `stale_after` (1.0 s), `plan_stale_after` (3.0 s), `arrive_within`
(1.0 m), `street_map` (`maps/streets/ottawa.pmtiles`), `places` (`maps/places/ottawa.db`).

### Launch and commands

| Command | Starts |
|---|---|
| `pixi run hud [fullscreen:=true] [monitor:=HDMI-1]` | `hud.launch.py` |
| `pixi run map [fullscreen:=true] [monitor:=HDMI-1] [streets:=] [places:=]` | `map.launch.py`, with `vehicle.yaml` and `navsat.yaml` |
| `cargo run -p hud-app --no-default-features -- --demo` | the HUD with pretend data, no ROS |
| `cargo run -p map-app --no-default-features -- --demo` | the map with pretend data |

`sim.launch.py hud:=true` and `map:=true` start them too. On the car,
`tools/car_screen.sh` starts them at boot; `car.launch.py` does not.

## Invariants

- Topic names live only in `config/*.yaml`, never in Rust. They are built in as the
  defaults, so `--demo` shows the same names.
- raylib owns the main thread (macOS needs it); rclrs spins on a thread called `ros`
  and sends news over a channel.
- The e-stop button only ever publishes `true`: five, 0.1 s apart, reliable, from the
  ROS thread's 10 ms timer, so a slow frame can't delay it.
- A heartbeat goes out only while the drawn-frame count rises: it proves the screen
  and the e-stop timer both run. The sensor watchdog stops Nav2 without it.
- `/system/source` and `/map` are read transient local, so a late window still gets them.
- `map` publishes a goal only after DRIVE HERE then CONFIRM, and refuses one off Nav2's
  map or with no car position.
- The logic lives in `hud-core` and `map-core`, tested without ROS or a screen.

## Side Effects

- Opens a window: it needs a screen, and fails without one.
- Publishes `/safety/estop`, `/hud/heartbeat` and `/goal_pose` (a goal drives the car).
- `map` reads the PMTiles and SQLite files from disk.
- On Linux the build needs X11 and OpenGL headers; without them CMake skips this
  package with a warning.

## Verification

```sh
cd ros/hud/aav_hud && cargo test --locked -p hud-core -p map-core -p debug-core
```

`tools/test.sh` runs that; `pixi run test` runs everything. `colcon build` needs Rust
1.88 or newer (`pixi run build`).
