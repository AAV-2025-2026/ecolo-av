# What each package does

Every ROS package in `src/`, layer by layer, with what it reads and writes. Then the
firmware, the HUD and the examples. 26 packages build today, and none is parked:
perception came in on 10 October, the lane finder on 11 October.

## At a glance

| Package | Layer | Does | Status | Origin |
|---|---|---|---|---|
| `aav_sensors` | sensors | starts the IMU, GPS, radar, battery and camera drivers, with their configs | [[untested]] needs the devices | new |
| `aav_imu_yahboom` | sensors | the Yahboom IMU over USB serial (Rust) | [[untested]] needs the device; the C++ driver's answers, bit for bit | new: Ben's rewrite of the 2025-26 `yahboom-IMU` C++ driver |
| `battery_monitor` | sensors | the Victron battery monitor | [[untested]] | 2024-25 `Battery-Monitor-ROS` |
| `ti_ros2_driver` | sensors | the TI mmWave radar, as point clouds | [[untested]] | 2025-26 `Nav_Radar` |
| `aav_description` | description | the car's model (URDF) and `vehicle.yaml` | [[works]] the numbers are guesses | new |
| `aav_localization` | localization | the two EKFs and `navsat_transform`: configuration only | [[works]] turtle, Gazebo and the bench | new |
| `aav_teleop` | drivers | joystick → `/drivers/joy/cmd_vel`, plus an e-stop button | [[untested]] | new; the button map from 2025-26 `joy_teleop_ackerman` |
| `aav_scripted` | drivers | scripted drives: speed up, hold, slow down | [[works]] turtle and the bench | new |
| `aav_language` | drivers | plain English: a local model plans drive tools, you say yes | [[works]] Gazebo and the turtle | new |
| `aav_navigation` | drivers | Nav2, set up for a car, and the maps | [[works]] goals reached in Gazebo | new |
| `aav_mux` | mux | twist_mux: the priorities and the e-stop lock | [[works]] | new |
| `aav_ego` | ego | one command → speed and steering the car can do | [[works]] | new |
| `aav_spine` | backends | the real car: ego's commands as CAN frames | [[works]] on the bench, against `spine_sim`; no spine board yet | new |
| `aav_legacy` | backends | today's car: the 2025-26 ESP32 over UART, and the wheel encoder | [[untested]] on the car | new, for the 2025-26 protocols |
| `aav_turtlesim` | backends | turtlesim, steered like the car | [[works]] | new |
| `aav_gazebo` | backends | Gazebo's car behind the real car's topics | [[works]] headless | new |
| `aav_carla` | backends | a CARLA adapter | [[stub]] never run | new |
| `aav_interfaces` | interfaces | our messages: `VehicleStatus`, `ScriptedDrive` | [[works]] builds | new |
| `aav_bringup` | bringup | the five profiles, perception on the car, the machine files, the RViz layout | [[works]] turtle, sim, replay, bench | new |
| `aav_yolo` | perception | YOLO on the camera's images, and the stop-sign watcher | [[works]] on the bench | 2024-25 `camera_ros2_ws` |
| `aav_radar_clusters` | perception | radar clustering (DBSCAN), with a box round each object (Rust) | [[works]] on the bench and in Gazebo | new: a rewrite of the 2025-26 `Nav_Radar` C++ node |
| `aav_lane_finder` | perception | the lane lines in the camera's pictures, as `/perception/lane/geometry` (OpenCV) | [[works]] on the bench | new |
| `aav_lane_geometry` | perception | lane keeping: a driver on `/drivers/ai/cmd_vel` | [[works]] on the bench, with `aav_lane_finder` | 2025-26 `Lane_Detection_ROS2` |
| `aav_hud` | hud | the HUD's web server (Flask, Socket.IO), on our topics | [[works]] on the bench, with the app's e-stop button | 2025-26 `User-Interface` |
| `aav_hud_raylib` | hud | the in-car screen in Rust: one raylib window that is the ROS node `hud` | [[works]] on a Mac: `--demo`, fed topics, bench mode. [[untested]] on a Pi and on the car | new |
| `aav_spine_sim` | bench | the spine on a laptop: the firmware's logic on a model car (Rust) | [[works]] | new |
| `aav_bench` | bench | pretend sensors: IMU, GPS, battery and camera | [[works]] | new |

## Sensors

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_sensors` | | | `sensors.launch.py imu:= gps:= radar:= battery:= gps_driver:=`; configs in `config/` |
| `aav_imu_yahboom`: `imu_node` | `/dev/aav/imu` | `/sensors/imu/data_raw`, `/sensors/imu/mag` | `/sensors/imu/mag` is in raw counts, not tesla, so it's unused |
| stock `imu_filter_madgwick` | `/sensors/imu/data_raw` | `/sensors/imu/data` | magnetometer off |
| stock `ublox_gps` (KumarRobotics' `ublox`) | `/dev/aav/gps` | `/sensors/gps/fix` | the default GPS driver, in Pixi too. Leaves the receiver's settings as they are. Tentative until Q18 |
| stock `ublox_dgnss` | a u-blox F9P on USB | `/sensors/gps/fix` | `gps_driver:=ublox_dgnss`. Not in Pixi: the car only |
| `ti_ros2_driver` | `/dev/aav/radar_cmd`, `/dev/aav/radar_data` | `/sensors/radar/points` | its configs are indoor demos |
| `battery_monitor` | `/dev/aav/battery` | `/vehicle/battery` | |
| stock `usb_cam` (`cameras.launch.py`) | `/dev/aav/camera_left`, `_right` | `/sensors/camera/front_left/image_raw`, `/sensors/camera/front_left/camera_info` | Linux only; the 2024-25 calibrations |
| stock `nmea_navsat_driver` (`gps_nmea.launch.py`) | `/dev/aav/gps` | `/sensors/gps/fix` | `gps_driver:=nmea`: any NMEA receiver |

## Description and localization

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_description` | `vehicle.yaml`, `/vehicle/joint_states` | `/robot_description`, `/tf`, `/tf_static` | `pixi run view` shows the model |
| `aav_localization`: `ekf_local` | `/vehicle/odom`, `/sensors/imu/data` | `/localization/odom/local`, odom → base_link | smooth; use it to steer |
| `aav_localization`: `ekf_global` | the same, plus `/localization/gps/odom` | `/localization/odom/global`, map → odom | stays near the truth; use it to plan |
| `aav_localization`: `navsat_transform` | `/sensors/gps/fix`, `/sensors/imu/data`, `/localization/odom/global` | `/localization/gps/odom`, `/localization/gps/fix` | the datum in `navsat.yaml` is a placeholder near Carleton |

## Drivers, the mux and ego

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_teleop` | `/drivers/joy/joy` | `/drivers/joy/cmd_vel` (while the trigger is held), `/safety/estop` | the button numbers are still TODO |
| keyboard (`tools/keyboard.sh`) | your keys | `/drivers/keyboard/cmd_vel` | `pixi run keyboard` |
| `aav_scripted` | `/localization/odom/local` | `/drivers/scripted/cmd_vel` | the action `/scripted_drive` |
| `aav_language` | your words; odometry, GPS, `/diagnostics`, `/vehicle/status` | `/safety/estop` (true only) | calls `/scripted_drive` and `/follow_gps_waypoints`; never publishes a velocity |
| `aav_navigation` | `/localization/odom/local`, `/map`, `/goal_pose` | `/drivers/nav/cmd_vel`, `/plan` | SmacPlannerHybrid and Regulated Pure Pursuit; GPS waypoints through `/follow_gps_waypoints` |
| `aav_mux` (twist_mux) | every `/drivers/<driver>/cmd_vel`, `/safety/estop` | `/control/cmd_vel` | priorities: [Build a driver](howto-driver.md) |
| `aav_ego` | `/control/cmd_vel` | `/ego/actuator_cmd`, 50 times a second | 1.0 m/s top speed, ±0.5 rad, brakes after 0.3 s without a command |

## Perception

[Perception](perception.md) has the details.

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_yolo`: `yolo_detector` | `/sensors/camera/front_left/image_raw` | `/perception/detections`, `/perception/detections/image` | a `.pt`, `.mlpackage` or `.engine` model; needs the `ml` environment |
| `aav_yolo`: `stop_sign_watcher` | `/perception/detections` | `/perception/stop_sign` | twist_mux's stop-sign lock, priority 30 |
| `aav_radar_clusters`: `radar_clusters` | `/sensors/radar/points` | `/perception/radar/clusters`, `/perception/radar/cluster_boxes` | DBSCAN, in Rust; eps 0.8 m, 15 points (5 on the bench and in Gazebo) |
| `aav_lane_finder`: `lane_finder` | `/sensors/camera/front_left/image_raw`, `/sensors/camera/front_left/camera_info` | `/perception/lane/geometry`, `/perception/lane/image` | a bird's-eye view, sliding windows, a curve per line; the camera's place from `vehicle.yaml` |
| `aav_lane_geometry`: `control_interface` | `/perception/lane/geometry` | `/drivers/ai/cmd_vel` | steers back to the lane's centre, measured 3 m ahead |

## Backends

Each backend reads `/ego/actuator_cmd` and reports the car's speed on `/vehicle/odom`.
Only one runs at a time.

| Package | Plays the car with | Also |
|---|---|---|
| `aav_spine` | CAN frames on `/can/tx` (through ros2_socketcan, Linux only) | `/vehicle/status`; the service `/spine/arm`; stops sending drive frames when ego goes quiet for 0.1 s |
| `aav_legacy` | 13-byte UART frames to today's ESP32 (`/dev/ttyAMA0`) | `encoder_udp`: the wheel encoder's UDP packets into `/vehicle/odom` |
| `aav_turtlesim` | `/turtle1/cmd_vel` | |
| `aav_gazebo` | `/gazebo/cmd_vel` | turns Gazebo's IMU and GPS into `/sensors/imu/data_raw` and `/sensors/gps/fix` |
| `aav_carla` | `/carla/ego_vehicle/ackermann_cmd` | a stub |

## Bench mode

[Bench mode](bench.md) runs the car's software with these stand-ins for the hardware.

| Package | Stands in for | Notes |
|---|---|---|
| `aav_spine_sim`: `spine_sim` | the spine board and the actuators | answers spine_bridge's CAN frames with spine-core's own logic; publishes `/vehicle/bench/truth` |
| `aav_bench` | the IMU, GPS, battery and camera drivers | `mock_imu`, `mock_gps`, `mock_battery`, `mock_camera`; the world is `config/bench.yaml` |

## Interfaces and bringup

| Package | Holds |
|---|---|
| `aav_interfaces` | `VehicleStatus` (mode, armed, e-stop, speed, steering, throttle, brake, fault bits) and the `ScriptedDrive` action |
| `aav_bringup` | the profiles `turtle`, `sim`, `car`, `replay`, `bench`; the machine files `orin`, `motor_pi`, `laptop`, `all`, which pick the car's parts, perception too; `rviz/drive.rviz` |

## Firmware

colcon ignores `firmware/`. It's built with cargo, PlatformIO or the Pico SDK.

| Part | What it is | Status |
|---|---|---|
| `can/aav.dbc` | the CAN contract: six frames between the Orin, the spine and the two wheel nodes | v0.2.0 (the KEFC plan), merged 15 Oct |
| `spine/crates/spine-core` | the spine's logic in Rust: modes, arming, the 100 ms watchdog, the speed loop, the encoder | [[works]] 70 tests, and the bench |
| `spine/crates/wheel-core` | the front wheel nodes' logic in Rust: pulses to speed, the WHEEL_SPEED frame | [[works]] 9 tests, and the bench; no board yet |
| `spine/crates/aav-inputs` | debounced switches, an e-stop that trips at once, counting with a lockout | [[works]] 9 tests |
| `spine/crates/jrk-g2` | the Pololu Jrk G2 (steering, brake) over I2C | [[works]] 14 tests, against mocks |
| `spine/crates/ad5311` | the throttle DAC over I2C | [[works]] 10 tests, against mocks |
| `spine/crates/pca9555` | the I/O expander (direction) over I2C | [[works]] 6 tests, against mocks |
| `spine/crates/ibus` | the FlySky RC receiver's protocol | [[works]] 24 tests |
| `spine/crates/mcp2515` | the MCP2515 CAN controller over SPI, since a Pico 2 has no CAN | [[works]] 34 tests, against mocks |
| `spine/crates/legacy-link` | the 2025-26 UART link: the Motor-Pi's 13-byte frames and the C++'s targets | [[works]] 31 tests, and against the C++ itself |
| `spine/crates/spine-board` | the glue: spine-core's outputs to the devices, the devices to its inputs, the `Board` trait, the `CommandLink` trait (CAN or UART) | [[works]] 57 tests, against mocks |
| `spine/boards/esp32-umod` | the spine on today's ESP32 control board (Embassy): the C++'s pins and devices; the Motor-Pi's UART or CAN | [[untested]] builds, never flashed |
| `spine/boards/pico2` | the spine's board program for a Pico 2 (Embassy): it implements `Board`, with a 100 ms hardware watchdog | [[untested]] builds, never flashed. The car's chip is Q10-Q13 |
| `spine/crates/wheel-encoder` | the spoke sensors (shared with the spine) and the wheel encoder's UDP packet | [[works]] 12 tests, with examples `aav_legacy` checks too |
| `spine/crates/sentinel` | the status display's logic: its I2C packet, 13 LCD pages, the knob, the beeps | [[works]] 40 tests |
| `spine/crates/hd44780` | a 16x2 character LCD on six GPIO pins | [[works]] 5 tests, against a fake |
| `spine/boards/wheel-encoder-pico2` | the wheel encoder in Rust: spokes to the Motor Pi over UDP, through a W5500 | [[untested]] builds, never flashed |
| `spine/boards/sentinel-pico2` | the status display in Rust: an I2C device at 0x42 | [[untested]] builds, never flashed; not wired in |
| `legacy/aav_umod_esp32` | the 2025-26 ESP32 that drives today's actuators | runs the car today: no timeout, an update page with no password. Stays until `boards/esp32-umod` is proven on the car |

## The HUD

| Part | What it is |
|---|---|
| `hud/flutter_pi` | the 2025-26 touchscreen app (Flutter): speed, map, camera; since 11 Oct an e-stop button, Cancel and the car's status. `pixi run hud-test` |
| `hud/scripts` | the old Pi's start-up scripts |
| `src/hud/aav_hud` | its ROS back end, on our topics: speed, mode, GPS, the stop sign and the camera in; a locked route out to Nav2's GPS waypoints, and the e-stop. [HUD](hud.md) has what's left |
| `src/hud/aav_hud_raylib` | the HUD in Rust (raylib and rclrs), to replace the two above: the driving screen, the e-stop button, GPS and topic health. `pixi run hud-demo` |

## Examples

| Example | What it is |
|---|---|
| `examples/rust-listener` | a first ROS node in Rust (rclrs): prints ego's commands. `pixi run rust-listener` |
