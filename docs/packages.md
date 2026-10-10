# What each package does

Every ROS package in `src/`, layer by layer, with what it reads and writes. Then the
firmware, the HUD and the examples. 19 packages build today; 3 perception packages are
parked until next year.

## At a glance

| Package | Layer | Does | Status | Origin |
|---|---|---|---|---|
| `aav_sensors` | sensors | starts the IMU, GPS, radar and battery drivers, with their configs | [[untested]] needs the devices | new |
| `yahboom_imu_cpp` | sensors | the Yahboom IMU over USB serial (C++) | [[untested]] builds | 2025-26 `yahboom-IMU` |
| `battery_monitor` | sensors | the Victron battery monitor | [[untested]] | 2024-25 `Battery-Monitor-ROS` |
| `ti_ros2_driver` | sensors | the TI mmWave radar, as point clouds | [[untested]] | 2025-26 `Nav_Radar` |
| `aav_description` | description | the car's model (URDF) and `vehicle.yaml` | [[works]] the numbers are guesses | new |
| `aav_localization` | localization | the two EKFs and `navsat_transform`: configuration only | [[works]] turtle and Gazebo | new |
| `aav_teleop` | drivers | joystick → `/cmd_vel/joy`, plus an e-stop button | [[untested]] | new; the button map from 2025-26 `joy_teleop_ackerman` |
| `aav_scripted` | drivers | scripted drives: speed up, hold, slow down | [[works]] in the turtle run | new |
| `aav_navigation` | drivers | Nav2, set up for a car, and the maps | [[works]] goals reached in Gazebo | new |
| `aav_mux` | mux | twist_mux: the priorities and the e-stop lock | [[works]] | new |
| `aav_ego` | ego | one command → speed and steering the car can do | [[works]] | new |
| `aav_spine` | backends | the real car: ego's commands as CAN frames | [[untested]] no spine yet | new |
| `aav_legacy` | backends | today's car: the 2025-26 ESP32 over UART, and the wheel encoder | [[untested]] on the car | new, for the 2025-26 protocols |
| `aav_turtlesim` | backends | turtlesim, steered like the car | [[works]] | new |
| `aav_gazebo` | backends | Gazebo's car behind the real car's topics | [[works]] headless | new |
| `aav_carla` | backends | a CARLA adapter | [[stub]] never run | new |
| `aav_interfaces` | interfaces | our messages: `VehicleStatus`, `ScriptedDrive` | [[works]] builds | new |
| `aav_bringup` | bringup | the four profiles, the machine files, the RViz layout | [[works]] turtle, sim, replay | new |
| `maincar` | hud | the HUD's web server (Flask, Socket.IO) | [[untested]] not connected to the new stack | 2025-26 `User-Interface` |
| `lane_geometry` | perception | lane keeping (parked) | [[later]] | 2025-26 `Lane_Detection_ROS2` |
| `object_detection` | perception | radar point-cloud clustering (parked) | [[later]] | 2025-26 `Nav_Radar` |
| `yolo_ros2` | perception | a YOLO stop-sign detector (parked) | [[later]] | 2024-25 `camera_ros2_ws` |

Parked packages have a `COLCON_IGNORE` file, so colcon skips them.

## Sensors

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_sensors` | | | `sensors.launch.py imu:= gps:= radar:= battery:=`; configs in `config/` |
| `yahboom_imu_cpp` | `/dev/aav/imu` | `/imu/data_raw`, `/imu/mag` | `/imu/mag` is in raw counts, not tesla, so it's unused |
| stock `imu_filter_madgwick` | `/imu/data_raw` | `/imu/data` | magnetometer off |
| stock `ublox_dgnss` | the u-blox on USB | `/gps/fix` | not in Pixi: the car only. Q18 picks the driver |
| `ti_ros2_driver` | `/dev/aav/radar_cmd`, `/dev/aav/radar_data` | `/radar/points` | its configs are indoor demos |
| `battery_monitor` | `/dev/aav/battery` | `/battery_status` | |

## Description and localization

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_description` | `vehicle.yaml`, `/vehicle/joint_states` | `/robot_description`, `/tf`, `/tf_static` | `pixi run view` shows the model |
| `aav_localization`: `ekf_local` | `/vehicle/odom`, `/imu/data` | `/odometry/local`, odom → base_link | smooth; use it to steer |
| `aav_localization`: `ekf_global` | the same, plus `/odometry/gps` | `/odometry/global`, map → odom | stays near the truth; use it to plan |
| `aav_localization`: `navsat_transform` | `/gps/fix`, `/imu/data`, `/odometry/global` | `/odometry/gps`, `/gps/filtered` | the datum in `navsat.yaml` is a placeholder near Carleton |

## Drivers, the mux and ego

| Package | Reads | Publishes | Notes |
|---|---|---|---|
| `aav_teleop` | `/joy` | `/cmd_vel/joy` (while the trigger is held), `/estop` | the button numbers are still TODO |
| keyboard (`tools/keyboard.sh`) | your keys | `/cmd_vel/remote` | `pixi run keyboard` |
| `aav_scripted` | `/odometry/local` | `/cmd_vel/scripted` | the action `/scripted_drive` |
| `aav_navigation` | `/odometry/local`, `/map`, `/goal_pose` | `/cmd_vel/nav`, `/plan` | SmacPlannerHybrid and Regulated Pure Pursuit; GPS waypoints through `/follow_gps_waypoints` |
| `aav_mux` (twist_mux) | every `/cmd_vel/<driver>`, `/estop` | `/cmd_vel` | priorities: [Build a driver](howto-driver.md) |
| `aav_ego` | `/cmd_vel` | `/ego/actuator_cmd`, 50 times a second | 1.0 m/s top speed, ±0.5 rad, brakes after 0.3 s without a command |

## Backends

Each backend reads `/ego/actuator_cmd` and reports the car's speed on `/vehicle/odom`.
Only one runs at a time.

| Package | Plays the car with | Also |
|---|---|---|
| `aav_spine` | CAN frames on `/to_can_bus` (through ros2_socketcan, Linux only) | `/vehicle/status`; the service `/spine/arm`; stops sending drive frames when ego goes quiet for 0.1 s |
| `aav_legacy` | 13-byte UART frames to today's ESP32 (`/dev/ttyAMA0`) | `encoder_udp`: the wheel encoder's UDP packets into `/vehicle/odom` |
| `aav_turtlesim` | `/turtle1/cmd_vel` | |
| `aav_gazebo` | `/gazebo/cmd_vel` | turns Gazebo's IMU and GPS into `/imu/data_raw` and `/gps/fix` |
| `aav_carla` | `/carla/ego_vehicle/ackermann_cmd` | a stub |

## Interfaces and bringup

| Package | Holds |
|---|---|
| `aav_interfaces` | `VehicleStatus` (mode, armed, e-stop, speed, steering, throttle, brake, fault bits) and the `ScriptedDrive` action |
| `aav_bringup` | the profiles `turtle`, `sim`, `car`, `replay`; the machine files `orin`, `motor_pi`, `laptop`, `all`; `rviz/drive.rviz` |

## Firmware

colcon ignores `firmware/`. It's built with cargo, PlatformIO or the Pico SDK.

| Part | What it is | Status |
|---|---|---|
| `can/aav.dbc` | the CAN contract: four frames between the Orin and the spine | draft v0.1.0 |
| `spine/crates/spine-core` | the spine's logic in Rust: modes, arming, the 200 ms watchdog, the speed loop, the encoder | [[works]] 47 tests |
| the spine's board code | the microcontroller program around `spine-core` | [[missing]] |
| `legacy/aav_umod_esp32` | the 2025-26 ESP32 that drives today's actuators | runs the car today: no timeout, an update page with no password |
| `legacy/wheel_encoder_pico2` | a Pico 2 that counts wheel spokes and sends them over UDP | runs the car today |
| `legacy/aav_sentinel_pico2` | a Pico 2 status display | not wired in |

## The HUD

| Part | What it is |
|---|---|
| `hud/flutter_pi` | the 2025-26 touchscreen app (Flutter): speed, map, camera |
| `hud/scripts` | the old Pi's start-up scripts |
| `src/hud/maincar` | its ROS back end. It still listens to the 2025-26 topic names; its `PROVENANCE.md` has the port plan |

## Examples

| Example | What it is |
|---|---|
| `examples/rust-listener` | a first ROS node in Rust (rclrs): prints ego's commands. `pixi run rust-listener` |
