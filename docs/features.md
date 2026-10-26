# Features: what the car's software does, and why

Every feature of the car's software, one row each, grouped by type.
Add a row in the same commit as the feature (`CLAUDE.md`).
"Why" says the reason for the feature, not how it works. "Who" is the person (or team) who built it.

## Status values

| Status | Means |
|---|---|
| planned | agreed, not built yet |
| built | in the repo, with its unit tests |
| sim | works in Gazebo or the turtle (or bench mode) |
| car | has worked on the real car |

## Sensors

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| IMU driver in Rust (`aav_imu_yahboom`) | Our C++ moves to Rust; it gives the 2025-26 C++ driver's answers, bit for bit | Ben | 2026-10-10 | built |
| GPS driver: stock `ublox_gps`, with `nmea` or `ublox_dgnss` as options | A stock driver that installs with Pixi on every computer, while the receiver model is still open (Q18) | Ben | 2026-10-11 | built |
| TI radar driver (`ti_ros2_driver`) | The car's radar already worked with it, so we ported it to Jazzy instead of rewriting it | the 2025-26 team, ported by Ben | 2026-10-09 | built |
| Battery monitor (`battery_monitor`) | Shows the battery's state, so the team sees it before it runs flat | the 2024-25 team | 2026-10-09 | built |
| Roof lidar: the stock `velodyne` driver | The car's VLP-16 already speaks to this stock driver; it gives Nav2 a view all round the car | Ben | 2026-10-20 | built |
| Wheel speed from CAN (0x200, 0x201; `spine_bridge role:=sensors`) | The hardware lead's Arduino puts the wheel speeds on CAN; the Orin turns them into odometry | Ben | 2026-10-15 | sim |
| [Front camera streams](camera-pipeline.md) (`aav_camera_stream`) | H.264 from the camera Pi is about 10 times smaller than JPEG, so both front cameras fit the network | Ben | 2026-10-24 | built |
| Camera calibrations, and `pixi run calibrate-camera` | A calibrated lens turns pixels into metres, for the stop-sign distance and camera obstacles | the 2024-25 team; Ben | 2026-10-09 | built |

## Localization

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Two EKFs and GPS to map (robot_localization) | Stock filters replace the 2025-26 odometry: a smooth position for steering, a GPS-anchored one for planning | Ben | 2026-10-09 | sim |
| GPS outlier gate in `ekf_global` | A fix 10 sigma off is refused, so one bad GPS jump can't throw the car's position | Ben | 2026-10-15 | sim |
| Heading from the gyro and wheels | At walking pace GPS made the heading jump up to 76°; the gyro and wheels hold it steady | Ben | 2026-10-22 | sim |
| Heading from the GPS velocity (`aav_gps_heading`) | The receiver's Doppler velocity gives a good heading while moving, with no magnetometer | Ben | 2026-10-25 | sim |

## Perception

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| [Object detector](perception.md) (`aav_detector`): RF-DETR Nano, YOLO as an option | RF-DETR saw a stop sign from 20 m (YOLO11n: 10 m), with no false finds and an Apache-2.0 licence | Ben | 2026-10-20 | sim |
| One detector per computer: Core ML on a Mac | A laptop adds a second opinion over WiFi, at 21 ms a picture on a MacBook | Ben | 2026-10-11 | sim |
| Stop-sign watcher | Holds the drive commands so the car stops about 4.7 m before a stop sign | the 2024-25 team, rewritten by Ben | 2026-10-10 | sim |
| Lane finder (`aav_lane_finder`) | Classic OpenCV finds the lane in 0.78 ms a picture, with no model to train | Ben | 2026-10-10 | sim |
| Lane keeping (`aav_lane_geometry`) | Steers back to the lane's centre: on the bench, from 0.3 m off to within 5 cm | the 2025-26 team | 2026-10-10 | sim |
| Radar clustering in Rust (`aav_radar_clusters`) | Turns radar points into objects; our C++ moves to Rust, with the same answers bit for bit | Ben | 2026-10-15 | sim |
| Lidar to a 2D scan (`aav_lidar` `lidar_scan`) | Nav2's costmap and stop zone need a flat scan, without the car's own body in it | Ben | 2026-10-15 | sim |

## Drivers

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Keyboard driving (`teleop_twist_keyboard`) | Drive the turtle, Gazebo or the car from any laptop, with no joystick | Ben | 2026-10-09 | sim |
| Joystick with a deadman (`aav_teleop`) | The joystick can drive with no autonomy running, and letting go stops the car | Ben | 2026-10-09 | built |
| Scripted drives (`aav_scripted`) | Repeatable speed-up, hold and slow-down runs, for tests and the first drives | Ben | 2026-10-09 | sim |
| [Goto: GPS A to B](a-to-b.md) (`aav_goto`) | The Gate 4 goal: drive to a GPS point and stop within 1 m; in Gazebo it stopped within 0.4 m | Ben | 2026-10-15 | sim |
| [Plain English](plain-english.md) (`aav_language`) | Say "drive 10 m forward": a local model plans it, and asks before the car moves | Ben | 2026-10-15 | sim |
| RC via ROS (`rc_driver`) and a three-position mode switch | A person on the RC transmitter outranks every program, but still passes through ROS's safety checks | Ben | 2026-10-24 | built |

## Navigation

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Nav2 set up for a car (`aav_navigation`) | A car can't turn on the spot: SmacPlannerHybrid plans paths it can drive, with no Spin | Ben | 2026-10-09 | sim |
| [MPPI path follower](controllers.md), Pure Pursuit as an option | MPPI reached the first goal cleanly in 4 of 4 Gazebo runs; Pure Pursuit looped in 2 of 3 | Ben | 2026-10-22 | sim |
| Reversing, with a stop zone behind the car | Backing up allows a three-point turn, instead of getting stuck facing a wall | Ben | 2026-10-22 | sim |
| Obstacles in the costmap, and a stop zone (`collision_monitor`) | Radar and lidar points stop Nav2 before it hits something: 0.3-0.4 m short of a box on the bench | Ben | 2026-10-11 | sim |
| Plan around obstacles (`plan_around:=true`) | The planner sees the radar and lidar too, so it steers round a box instead of only stopping | Ben | 2026-10-22 | sim |
| [Street routes](routes.md) (`aav_routes`, Valhalla) | Turns a destination into GPS waypoints along real streets, for Nav2 to follow | Ben | 2026-10-16 | sim |

## Control

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| ego, the virtual car (`aav_ego`), with Ackermann output | Only ego talks to a backend, and every backend takes the same Ackermann message | Ben | 2026-10-09 | sim |
| Stale-command stop and a speed cap (`max_speed:=`) | The car stops when commands go stale, and stays at 1.0 m/s or less until the tests raise it | Ben | 2026-10-09 | sim |
| Car model and `vehicle.yaml` (`aav_description`) | One file holds every car measurement, so no number is copied or guessed twice | Ben | 2026-10-09 | sim |
| Body model: mass and curve speed | ego knows the car weighs about 181 kg, so it slows for tight turns and heavy loads | Ben | 2026-10-22 | sim |
| Jerk limit | A smoother start for the people in the car; braking is never softened | Ben | 2026-10-22 | sim |
| [Linear model of the car](vehicle-model.md) (`vehicle_model.py`) | Transfer functions and state space, to tune the loops and write the report in SYSC 3600's terms | Ben | 2026-10-24 | built |

## Safety

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Command mux and e-stop lock (`aav_mux`, twist_mux) | One command wins by priority, and the e-stop locks every driver out | Ben | 2026-10-09 | sim |
| Four e-stops | The car's red button stays untouched; the joystick, `pixi run estop` and the HUD add three more | Ben | 2026-10-10 | sim |
| [Sensor watchdog](simulation.md#sensor-failures-on-purpose) (`aav_safety`) | When a sensor fails or freezes, Nav2 stops loudly and says why, instead of driving blind | Ben | 2026-10-15 | sim |
| Frozen-wheel cross-check | Wheels that stop reporting are caught by checking them against the IMU and GPS | Ben | 2026-10-15 | sim |
| HUD heartbeat and latch | The safety drivers rely on the screen, so a frozen HUD holds Nav2 until a person clears it | Ben | 2026-10-23 | sim |
| [Sensor mux and output mux](sources-and-targets.md) (`aav_io_mux`) | Simulated data can never drive the real car, and the spine won't arm while the gate is shut | Ben | 2026-10-23 | sim |
| The bridge won't arm while the safety gate is shut (`spine_bridge`, `/spine/arm`) | Arming said "armed" and did nothing while no commands could pass; now it refuses and says why | Ben | 2026-10-24 | sim |
| Orin-to-ESP32 heartbeat (serial frame version 2) | The ESP32 brakes when the Orin stops, even if the Motor Pi still sends: 111-120 ms in QEMU | Ben | 2026-10-24 | built |
| Stand-ins stay local (`tools/ros.sh --local`) | A pretend car in the turtle, Gazebo or bench mode can never reach the real one | Ben | 2026-10-10 | sim |

## Backends

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Turtlesim backend (`aav_turtlesim`) | A turtle that steers like the car: the first thing a new member drives | Ben | 2026-10-09 | sim |
| Gazebo backend (`aav_gazebo`) | The car in 3D with Ackermann steering, an IMU and GPS, to test Nav2 before the car | Ben | 2026-10-09 | sim |
| Today's car over UART (`aav_legacy`) | Drives the 2025-26 ESP32 through the Motor Pi, and reads its wheel encoder, before the CAN spine exists | Ben | 2026-10-09 | built |
| Uplink from the ESP32 (`legacy_uart_bridge`) | Brings the car's mode, faults, steering and brake positions and RC sticks back into ROS | Ben | 2026-10-24 | built |
| CAN spine bridge (`spine_bridge`): Rust by default, Python as an option | ego's commands become CAN frames, decoded by the firmware's own code at both ends | Ben | 2026-10-09 | sim |
| [CARLA adapter](carla.md) (`aav_carla`) | Realistic camera pictures, once the NVIDIA computer runs CARLA | Ben | 2026-10-15 | built |

## Firmware

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| CAN contract (`aav.dbc`, `can_codec.py`, test vectors) | One file defines every frame, tested from both sides against the same vectors | Ben | 2026-10-09 | sim |
| CAN v0.2.0: wheel-speed frames, a 100 ms timeout, `wheel-core` | Puts the wheel sensors on the bus, and stops the car within 100 ms of lost commands | Ben | 2026-10-15 | sim |
| `spine-core`: the spine's logic | Boots latched, arms only on request and brakes on a command gap, so a glitch never restarts the car | Ben | 2026-10-09 | sim |
| Spine device drivers and glue (`jrk-g2`, `ad5311`, `pca9555`, `ibus`, `mcp2515`, `spine-board`, `legacy-link`) | Each device the spine drives, tested against mocks before any board exists | Ben | 2026-10-10 | built |
| Pico 2 spine program (`boards/pico2`) | A spine on an ARM chip, with a 100 ms hardware watchdog and a fail-safe e-stop input | Ben | 2026-10-11 | built |
| ESP32 spine in Rust (`boards/esp32-umod`) | Replaces the C++ on today's control board with no new hardware; tested in QEMU | Ben | 2026-10-15 | built |
| ESP32 actuator firmware in C++ (`aav_umod_esp32`) | It drives today's car, so it stays until its Rust version is proven | the 2025-26 team | 2026-10-09 | car |
| Wheel encoder and status display Pico 2s in Rust | The 2025-26 C++ boards move to Rust, as decided, sending the same packets | Ben | 2026-10-15 | built |
| Speed loop's `smooth` profile | Today's gains overshoot about 15%; this one starts smoother, ready to try on stands | Ben | 2026-10-25 | sim |

## Simulation

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| [Gazebo road world](simulation.md) | Lane lines, a stop sign, an obstacle, and the car's camera, radar and roof lidar, to test the whole graph | Ben | 2026-10-11 | sim |
| Actuator model | Lag and limits between ego and Gazebo, so the simulated car answers like a real one | Ben | 2026-10-15 | sim |
| [Bench mode](bench.md) (`aav_bench`, `aav_spine_sim`) | The car's own software on one laptop, with the spine's logic and pretend sensors | Ben | 2026-10-10 | sim |
| The spine in the loop (`sim spine:=true`) | Gazebo drives through the spine's real logic, so its stops and e-stops get tested | Ben | 2026-10-15 | sim |
| `sim-check` and `bench-check` | One command proves the whole chain drives, stops and keeps its lane | Ben | 2026-10-10 | sim |
| Sensor failures on purpose (`pixi run sim-fault`) | Breaks a sensor in Gazebo, to prove the watchdog catches it | Ben | 2026-10-15 | sim |
| [Ghost obstacles](ghost-obstacles.md) (`aav_ghost`) | A pretend person only Nav2 sees, to test stopping with nothing real to hit | Ben | 2026-10-16 | sim |
| Record and replay a drive | A recorded drive runs through the EKFs again, to check them; they match within 0.03 m | Ben | 2026-10-09 | sim |

## HUD

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| HUD back end (`aav_hud`) | Keeps the 2025-26 touchscreen working, on our topics | the 2025-26 team, ported by Ben | 2026-10-10 | sim |
| Flutter HUD app: e-stop button, Cancel, camera | The app could never reach its back end; now its e-stop stops the bench car in 0.3 s | the 2025-26 team, changed by Ben | 2026-10-11 | sim |
| [Raylib HUD in Rust](hud.md) (`aav_hud_raylib`), with a SIMULATED banner | One program that is also its ROS node, and nobody mistakes simulated data for the car | Ben | 2026-10-15 | sim |
| GO / STOP panel | The safety drivers get one answer at a glance: may the car move, and if not, why | Ben | 2026-10-24 | built |
| Map window: offline street map and place search | A big-screen map of Nav2's plan over real streets, and a destination picked by name | Ben | 2026-10-15 | sim |
| Car screens at login | The HUD and the map start on the car's two screens by themselves | Ben | 2026-10-15 | built |

## Tools

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| Live graph check (`pixi run check`) | Compares the running graph with `docs/interfaces.yaml`, so a wrong topic shows at once | Ben | 2026-10-09 | sim |
| Network doctor, network map and machine survey | Tells whether a laptop can join the car's network, and records what's on each computer, read-only | Ben | 2026-10-10 | car |
| Read-only [MCP server](mcp.md) | An AI app can read the docs, contracts and live graph, but never move the car | Ben | 2026-10-10 | built |
| Car kit (`pixi run car-kit`) | Installs our Jazzy on the car's ARM computers from a USB stick, with no internet or admin rights | Ben | 2026-10-15 | built |
| [Car-day kit](car-day.md): runbook and preflight | Ten sessions at the car, in order, and a check that the laptop has everything | Ben | 2026-10-24 | built |
| [Actuator tests](actuator-tests.md) (`aav_actuator_tests`) | Measures the throttle, brake and steering on stands, and gives the numbers for `vehicle.yaml` | Ben | 2026-10-15 | sim |
| Bandwidth, CAN load and timing tests | Checks each network link has room, and finds late messages and stalls | Ben | 2026-10-23 | sim |
| [Watch from a laptop](foxglove.md) (Foxglove and Lichtblick) | One bridge and three layouts to watch any profile from a laptop | Ben | 2026-10-24 | sim |

## Infrastructure

| Feature | Why | Who | Date | Status |
|---|---|---|---|---|
| One workspace with Pixi and RoboStack, Macs included | ROS 2 Jazzy, Gazebo, Nav2 and Rust on any Linux or Mac, with no admin rights | Ben | 2026-10-09 | sim |
| Cyclone DDS on every computer | Fast DDS delivered messages up to 0.48 s late beside Gazebo; Cyclone never over 0.05 s | Ben | 2026-10-23 | sim |
| Launch profiles and machine files (`aav_bringup`) | One command per profile (turtle, sim, bench, replay, car), and each computer picks its own parts | Ben | 2026-10-09 | sim |
| Topic contract and [topic names by area](naming.md) | Every topic's publisher, subscriber, type and QoS in one place, named so you see where it belongs | Ben | 2026-10-09 | built |
| CI: Linux and 64-bit ARM on every push, a Mac and Gazebo nightly | A break shows on the push that made it, including on the car's ARM computers | Ben | 2026-10-10 | built |
| Docs as HTML and PDF, with the Learn pages | Short pages with tables and pictures, for a dyslexic reader and new team members | Ben | 2026-10-09 | built |
| [Getting-started guide](getting-started.md) | A new laptop goes from nothing to driving the turtle in under 30 minutes (T1.1) | Arsh (arshjameel) | 2026-10-24 | built |
| The previous teams' 27 repos, imported with their history | All the older code and its history in one repo, to read and port from | Arsh (arshjameel) | 2026-10-24 | built |
| One team repo: `AAV-2025-2026/ecolo-av` | The team's own repo, keeping the whole history of both workspaces | Ben | 2026-10-25 | built |
| [CONTRIBUTING.md](../CONTRIBUTING.md) and the merge queue | One way into `main` for everyone: fork, branch, pull request, review, merge queue | Arsh (arshjameel) | 2026-10-25 | built |
