# Overview: everything in aav

The whole project on one page: what's in the repo, the stock ROS packages and plugins it
uses, the code it took from the previous teams, and what's still missing. Each section
links to the page with the details. As of 10 October 2026.

## In numbers

| What | How many |
|---|---|
| ROS packages that build | 19: 10 in Python, 9 in CMake, plus 3 parked until next year |
| Rust firmware crates | 2: `spine-core` and `aav-inputs` |
| The previous team's firmware boards, in C++ | 3 |
| Launch profiles | 4: `turtle`, `sim`, `car`, `replay` |
| Computers in the machine files | 4: `orin`, `motor_pi`, `laptop`, `all` |
| Contracts | 3: the topics, the CAN frames, the car's measurements |
| Tests | 47 in Python and 56 in Rust without ROS; 77 in `colcon test` |
| Tools | 13 scripts and 17 `pixi run` tasks |

## The folders

| Folder | What's in it | More |
|---|---|---|
| `src/` | the ROS 2 packages, one folder per layer | [Packages](packages.md) |
| `firmware/` | the CAN contract, the Rust crates, and the 2025-26 C++ boards | [Firmware](firmware.md), [Rust firmware](rust-firmware.md) |
| `hud/` | the 2025-26 touchscreen app (Flutter), not yet ported | [HUD](hud.md) |
| `tools/` | tests, the graph check, the doctor, recording, maps, the docs, the mailer | [Infrastructure](infrastructure.md) |
| `examples/` | a first ROS node in Rust | |
| `docs/` | these pages, the topic contract, and the history | |
| `pixi.toml`, `pixi.lock` | the whole environment: ROS 2 Jazzy, Gazebo, Nav2, Rust, compilers | [Infrastructure](infrastructure.md) |

## Our own code

Written for 2026-27. Most packages are configuration around stock ROS packages; three
nodes hold real logic of our own (ego, the spine bridge, the scripted driver).

| Package | Does | Layer |
|---|---|---|
| `aav_ego` | ego: one command into a speed and steering angle the car can do | ego |
| `aav_mux` | twist_mux's settings: the priorities and the e-stop lock | mux |
| `aav_scripted` | scripted drives: speed up, hold, slow down | drivers |
| `aav_teleop` | the joystick's settings, and its e-stop button | drivers |
| `aav_navigation` | Nav2 set up for a car, and the maps | drivers |
| `aav_localization` | the two EKFs and GPS-to-map: settings only | localization |
| `aav_description` | the car's model and `vehicle.yaml` | description |
| `aav_sensors` | starts the sensor drivers, with their settings | sensors |
| `aav_interfaces` | our messages: `VehicleStatus`, `ScriptedDrive` | interfaces |
| `aav_spine` | the real car: ego's commands as CAN frames | backends |
| `aav_legacy` | today's car: the 2025-26 ESP32 and wheel encoder | backends |
| `aav_turtlesim`, `aav_gazebo`, `aav_carla` | the turtle, Gazebo's car, a CARLA stub | backends |
| `aav_bringup` | the four profiles, the machine files, the RViz layout | bringup |
| `firmware/can`, `spine-core`, `aav-inputs` | the CAN contract, the spine's logic, clean inputs | firmware |

## Stock ROS packages and plugins we use

"Prefer stock" is a ground rule: these do most of the work.

| Layer | Stock package | What it does for us |
|---|---|---|
| Sensors | `imu_filter_madgwick` | turns the IMU's raw readings into an orientation |
| Sensors | `ublox_dgnss` | the u-blox GPS. It isn't in Pixi, so it runs on the car only (Q18) |
| Description | `robot_state_publisher`, `joint_state_publisher`, `xacro` | the car's model and frames |
| Localization | `robot_localization`: `ekf_node` (twice) and `navsat_transform_node` | where the car is: `ekf_local` to steer, `ekf_global` to plan, GPS into map coordinates |
| Localization | `tf2_ros` | a fixed map-to-odom frame when there's no GPS |
| Drivers | `joy`, `teleop_twist_joy`, `joy_teleop` | the joystick, its deadman, its e-stop button |
| Drivers | `teleop_twist_keyboard` | driving from a laptop's keyboard |
| Drivers | Nav2: 8 servers (map, planner, controller, behaviours, navigator, waypoints, velocity smoother, lifecycle) | plans and drives to a goal |
| The mux | `twist_mux` | picks one command, by priority |
| Backends | `ros2_socketcan` | the CAN bus (Linux only) |
| Backends | `turtlesim`; `ros_gz` with Gazebo Harmonic | the turtle; the simulated car |
| Backends | `topic_tools` | renames CARLA's topics (stub) |
| Watching | `rviz2`, `rqt_graph`, `rqt_tf_tree` | the 3D view, the node graph, the frame tree |
| Watching | `foxglove_bridge` | Foxglove or Lichtblick on a laptop, on the car |
| Recording | `rosbag2`, with MCAP files | `tools/record.sh` and replay |
| Ready, not used yet | `rosbridge_server`, `nmea_navsat_driver` | for the HUD's port, and a second GPS option |

### The plugins inside Nav2 and Gazebo

| Where | Plugin | Notes |
|---|---|---|
| Nav2 planner | `SmacPlannerHybrid` | plans paths a car can drive: no turning on the spot |
| Nav2 controller | `RegulatedPurePursuit` | follows the path. `MPPI` is configured but not loaded |
| Nav2 behaviours | `BackUp`, `DriveOnHeading`, `Wait` | no `Spin`: a car can't |
| Nav2 navigator | `NavigateToPose`, `NavigateThroughPoses` | with our car behaviour trees, adapted from Nav2's |
| Nav2 waypoints | `WaitAtWaypoint` | GPS waypoints come through the same server |
| Nav2 checkers | `SimpleGoalChecker`, `SimpleProgressChecker` | when a goal counts as reached |
| Costmaps | `StaticLayer`, `InflationLayer` | `ObstacleLayer` is written, and off until there's a lidar or radar |
| Gazebo | `AckermannSteering`, `JointStatePublisher`, `Imu`, `NavSat`, `Physics`, `SceneBroadcaster`, `UserCommands` | the simulated car, its sensors, and the world |

## Code from the previous teams

Each copy carries a `PROVENANCE.md`: where it came from, and every change since.

| Code | From | Now in | State |
|---|---|---|---|
| The Yahboom IMU driver (C++) | 2025-26 `yahboom-IMU` | `src/sensors/yahboom_imu_cpp` | ported, with fixes |
| The TI radar driver | 2025-26 `Nav_Radar` | `src/sensors/ti_ros2_driver` | ported; its settings are indoor demos |
| The battery monitor | 2024-25 `Battery-Monitor-ROS` | `src/sensors/battery_monitor` | ported |
| Camera calibrations | 2024-25 `cameras` | `aav_sensors/config/cameras` | copied |
| The HUD's back end (Flask) | 2025-26 `User-Interface` | `src/hud/maincar` | copied; still on the old topics |
| The HUD app (Flutter) and its boot scripts | 2025-26 `User-Interface` | `hud/` | copied; not ported |
| The ESP32 actuator firmware (C++) | 2025-26 `AAV_cortex` | `firmware/legacy/aav_umod_esp32` | runs today's car; its WiFi password moved out of git |
| The status display (Pico 2) | 2025-26 `AAV_cortex` | `firmware/legacy/aav_sentinel_pico2` | copied; not wired in |
| The wheel encoder (Pico 2) | 2025-26 `Wheel_Encoders` | `firmware/legacy/wheel_encoder_pico2` | runs today's car |
| Their UART and encoder protocols | 2025-26 `AAV_cortex`, `Wheel_Encoders` | `aav_legacy` | rewritten in Python |
| Lane keeping | 2025-26 `Lane_Detection_ROS2` | `src/perception/lane_geometry` | parked |
| Radar clustering | 2025-26 `Nav_Radar` | `src/perception/object_detection` | parked |
| A YOLO stop-sign detector | 2024-25 `camera_ros2_ws` | `src/perception/yolo_ros2` | parked |
| The car's geometry | 2025-26 `Motor_Steering` (`Ackermann.m`) | `vehicle.yaml`, `docs/reference/` | numbers carried over, still guesses |
| The joystick's button map | 2025-26 `joy_teleop_ackerman` | `aav_teleop` | carried over |
| CARLA's topic names | 2024-25 `carla_ros_bridge` | `aav_carla` | stub |

Replaced by stock packages instead of copied: the 2025-26 path planners, obstacle
avoidance, odometry and QNX layer. [The older code](older-code.md) has every repo.

## In progress, outside this copy

| What | Where | State |
|---|---|---|
| A Rust twin of the IMU driver, `aav_imu_yahboom` | on oirp-spss, not committed yet | it arrives with `aav/aav`, which is still downloading |

## What's missing

| Area | Missing | More |
|---|---|---|
| The spine | its board code, and the chip it runs on (Q10–Q13); the CAN wiring | [Rust firmware](rust-firmware.md) |
| Rust drivers | the Jrk G2s, the throttle DAC, the PCA9555, the iBUS receiver, the W5500, the display | [Rust firmware](rust-firmware.md) |
| Sensors | a GPS driver inside Pixi; lidar and camera drivers (next year); the magnetometer in real units | [Status](status.md) |
| The car | every measurement in `vehicle.yaml` (Q1); the steering calibration (Q2); Jazzy on its computers (Q24) | [Car numbers](car_measurements.md) |
| Navigation | the real test site's map (Q21); Nav2's lookahead (N7); obstacle inputs | [Costmaps](costmaps.md) |
| Drivers | a first real joystick test; an e-stop message that can't get lost (N2) | [Starting points](team.md) |
| The HUD | the port to the new topics (Q29); a download step for its 51 MB map database | [HUD](hud.md) |
| Simulation | CARLA (no Jazzy support yet); a bench mode for the real car's software (proposed) | [Simulation](simulation.md) |
| The team | owners (Q33), a GitHub org (Q25), the leaked secrets changed (Q34), backups before any reflash | [Work](work.md) |
