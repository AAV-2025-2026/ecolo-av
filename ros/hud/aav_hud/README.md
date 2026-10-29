# aav_hud

## Overview

The car's screens, in Rust with raylib. Each is one program that is also its ROS
node (rclrs):

- `hud`, the in-car screen: speed, mode, the e-stop button, GO / STOP, steering,
  throttle and brake, GPS, topic health, the stop-sign alert and the camera;
- `map`, the big screen's map window: Nav2's map over an offline street map, the car,
  the plan, the goal, the distance left, and a place search;
- `debug_hud`, the debug screen: the lidar's cubes in 3D, where each localizer puts the
  car, Nav2's plan, and every sensor from its own topic. It only listens.

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
| [`debug-core`](./crates/debug-core/README.md) | the debug HUD's logic: cubes, frames, poses at a stamp, the camera; no ROS, no raylib |
| `crates/debug-app` | binary `debug_hud`: the window (`ui.rs`, instanced cubes), the node (`ros.rs`), `--demo` |

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

### Node `debug_hud` (topic names from `config/debug_hud.yaml`)

| Direction | Parameter: default topic | Type |
|---|---|---|
| sub | `lidar_topic`: `/sensors/lidar/points` (reliable, keep last 1) | sensor_msgs/PointCloud2 |
| sub | `local_odom_topic`: `/localization/odom/local`; `global_odom_topic`: `/localization/odom/global`; `truth_topic`: `/vehicle/gazebo/truth`; `wheel_odom_topic`: `/vehicle/odom` | nav_msgs/Odometry |
| sub | `amcl_topic`: `/localization/amcl/pose` | geometry_msgs/PoseWithCovarianceStamped |
| sub | `plan_topic`: `/plan` | nav_msgs/Path |
| sub | `tf_topic`: `/tf`; `tf_static_topic`: `/tf_static` (latched) | tf2_msgs/TFMessage |
| sub | `imu_topic`: `/sensors/imu/data`; `gps_topic`: `/sensors/gps/fix` | sensor_msgs/Imu, NavSatFix |
| sub | `wheels_topic`: `/vehicle/wheels`; `vehicle_status_topic`: `/vehicle/status` | aav_interfaces/WheelSpeeds, VehicleStatus |
| sub | `track_status_topic`: `/drivers/nav/track/status` | diagnostic_msgs/DiagnosticStatus |
| sub | `source_topic`: `/system/source` (latched) | aav_interfaces/DataSource |
| call | `track_parameters_service`: `/track/set_parameters` (keys 1-4: `tracker`; only while `/system/source` says SIM) | rcl_interfaces/SetParameters |

Other parameters: `odom_frame`, `base_frame`, `map_frame`; `stale_after` (1.0 s),
`cube_size` (0.2 m), `max_cubes` (20,000), `pose_window` (1.0 s), `ground_height` (0.25 m).

### Launch and commands

| Command | Starts |
|---|---|
| `pixi run hud [fullscreen:=true] [monitor:=HDMI-1]` | `hud.launch.py` |
| `pixi run map [fullscreen:=true] [monitor:=HDMI-1] [streets:=] [places:=]` | `map.launch.py`, with `vehicle.yaml` and `navsat.yaml` |
| `cargo run -p hud-app --no-default-features -- --demo` | the HUD with pretend data, no ROS |
| `cargo run -p map-app --no-default-features -- --demo` | the map with pretend data |
| `pixi run debug-hud`; `pixi run debugdemo` | `debug_hud.launch.py`; `demo` plus the debug HUD |
| `cargo run --release -p debug-app --no-default-features -- --demo [--bench-cubes 20000]` | the debug HUD with pretend data; the drawing test |

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
- The logic lives in `hud-core`, `map-core` and `debug-core`, tested without ROS or a screen.
- `debug_hud` publishes nothing and never touches an actuator. Its one call swaps a
  **simulated** trial tracker (keys 1-4), and only while `/system/source` says SIM.
- `debug_hud`'s clouds never go through the shared queue: a newest-only slot to the
  `cubes` thread, then a newest-only slot to the screen. Each is placed with the local
  EKF's pose at its own stamp.

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

The nodes themselves, with ROS (after `pixi run build`; each on its own domain and topics;
`LIBRARY_PATH` because ros-env links every message package in the workspace):

```sh
pixi run bash -c 'source install/setup.bash && export ROS_DOMAIN_ID=94 \
  LIBRARY_PATH=$(ls -d $PWD/install/*/lib | tr "\n" ":")$CONDA_PREFIX/lib \
  && cd ros/hud/aav_hud && cargo test --release -p hud-app -p debug-app'
```

`tools/test.sh` runs the logic's tests; `pixi run test` runs everything else.
`colcon build` needs Rust 1.88 or newer (`pixi run build`).
