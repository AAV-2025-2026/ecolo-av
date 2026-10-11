# Release notes: the first pass, to 11 October 2026

Everything built from 9 to 11 October 2026, in point form: 168 commits on `main`.

- **"Works"** means it ran under ROS 2 Jazzy through Pixi, on Linux and on a Mac.
- **"On the bench"** means [Bench mode](bench.md): the car's own software, with stand-ins
  for the hardware.
- **Nothing has run on the car yet.** It still runs the 2025-26 software, on Humble.

## In numbers

| What | How many |
|---|---|
| ROS 2 packages | 26: 13 in Python, 13 in CMake (one of them Rust) |
| Rust firmware | 8 crates, plus the spine's program for a Pico 2 |
| The 2025-26 C++ boards, kept running | 3 |
| Launch profiles | 5: `turtle`, `sim`, `bench`, `replay`, `car` |
| Machine files | 4: `orin`, `motor_pi`, `laptop`, `all` |
| Contracts | 3: the topics, the CAN frames, the car's measurements |
| Tests | 230 Python, 208 Rust, 291 in `colcon test`, the HUD app's own, the bench checks |
| Docs | 29 pages, as HTML and one PDF, with 11 pictures |
| Tools | 26 scripts, 34 `pixi run` tasks, 5 Pixi environments |

## The previous teams' projects: merged in, or replaced

**Merged in** (each copy has a `PROVENANCE.md`: the repo, the commit, every change since):

- **AAV_cortex (2025-26):** the ESP32 actuator firmware that drives today's car, in
  `firmware/legacy/`. Its WiFi password moved out of git. Its UART protocol was rewritten
  in Python (`aav_legacy`), and its device logic in Rust (the spine's drivers).
- **Wheel_Encoders (2025-26):** the Pico 2 that counts wheel spokes. Its UDP messages are
  read by `encoder_udp`.
- **yahboom-IMU (2025-26):** the C++ IMU driver, with fixes (`yahboom_imu_cpp`), and Ben's
  Rust version of it (`aav_imu_yahboom`).
- **Nav_Radar (2025-26):** the TI radar driver (`ti_ros2_driver`) and its object
  clustering (`aav_object_detection`).
- **Lane_Detection_ROS2 (2025-26):** lane following (`aav_lane_geometry`). The lane finder
  was never in their repo: we wrote our own.
- **User-Interface (2025-26):** the in-car HUD. The Flutter app is in `hud/`; its Flask
  back end is `aav_hud`, moved to our topics.
- **Motor_Steering (2025-26):** the steering geometry (`Ackermann.m`), in `vehicle.yaml` and
  `docs/reference/`.
- **joy_teleop_ackerman (2025-26):** its joystick button map, in `aav_teleop`.
- **2024-25:** the battery monitor, the camera calibrations, and a YOLO stop-sign detector
  (rewritten as `aav_yolo`).

**Replaced by stock ROS packages:**

- **Odometry** → robot_localization (two EKFs).
- **The path planners** (A*, D* Lite, the local path generators) → Nav2.
- **Obstacle_Avoidance_logic** → Nav2's obstacle layer and `collision_monitor`.
- **Real-Time-OS (QNX)** → `twist_mux`, the spine's watchdog and `ros2 bag`.
- **joy_teleop_ackerman** → the stock `teleop_twist_joy`.

**Left out:**

- an empty repo, and one its own team abandoned;
- Motor-Control (a fork of the 2024-25 micro-ROS firmware): a reference only, as the only
  code that reads the steering's position;
- a few repos not surveyed yet: [Older code](older-code.md).

## The car's software, layer by layer

**Sensors** (`aav_sensors` starts them, with their settings):

- **IMU:** the Yahboom driver, C++ or Rust (`imu_driver:=rust`), then
  `imu_filter_madgwick` for the orientation.
- **GPS:** the stock `ublox_gps` by default (Tentative, Q18); `nmea` and `ublox_dgnss` are
  options.
- **Wheel speed:** the 2025-26 encoder Pico, through `encoder_udp`.
- **Radar:** the TI driver. Its settings are still indoor demos.
- **Cameras:** `usb_cam` with the 2024-25 calibrations. Off until the cameras are fitted
  (Q22).
- **Battery:** the 2024-25 battery monitor.

**Localization: the EKF filters** (robot_localization, settings only):

- **`ekf_local`:** wheel speed and the IMU → `odom → base_link`, smooth, for steering.
- **`ekf_global`:** the same, plus GPS through `navsat_transform` → `map → odom`, for
  planning.
- **Results:** 0.03-0.3 m from the truth on the bench; within 0.2 m parked in Gazebo; a
  replayed drive matches its recording within 0.03 m.

**The drivers** (each publishes a command; the mux picks one):

- **Joystick** (`teleop_twist_joy`): a deadman button and an e-stop button. Priority 100.
  Not yet tried with a real joystick.
- **Keyboard** (`teleop_twist_keyboard`): from any laptop. Priority 90. Works.
- **Scripted** (`aav_scripted`): speed up, hold, slow down. Works.
- **Nav2** (`aav_navigation`): a planner for cars (SmacPlannerHybrid), Regulated Pure
  Pursuit, no turning on the spot, GPS waypoints. Reached 8 m and 9.5 m goals in Gazebo,
  and 40 m past a stop sign on the bench.
- **Lane keeping** (`aav_lane_finder` and `aav_lane_geometry`): the "AI" slot. On the
  bench: from 0.3 m off the centre line back to within 5 cm in about 6 s.
- **The stop-sign watcher** (`aav_yolo`): stops the car at a stop sign. Works on the
  bench.
- **The e-stops:** the joystick's button, a laptop's `pixi run estop`, and the HUD's
  button. The car's own red button always stops it, whatever the software does.

**The mux** (`twist_mux`): one command wins, by priority, and the e-stop locks them all
out.

**Ego** (`aav_ego`, ours):

- Turns the winning command into a speed and steering angle the car can really do.
- The limits every driver gets: 1.0 m/s forward, 0.5 m/s reverse, 1.0 m/s² to speed up,
  2.0 m/s² to slow down, a steering rate limit.
- A stale command stops the car (0.3 s); a computer with the wrong clock gets a warning.

**The Ackermann model:**

- **Today:** ego works out the steering angle from the speed, the turn rate and the
  wheelbase, for the middle of the front axle. It sends Ackermann commands
  (`AckermannDriveStamped`), never twists.
- **Gazebo:** its car has Ackermann steering.
- **In progress:** both front wheels' real angles, reversing, and the steering curve from
  the 2025-26 `Ackermann.m`.

**Backends and bridges** (exactly one backend runs at a time):

- **`spine_bridge`:** ego's commands → CAN frames, from our CAN contract; the car's status
  back. Works on the bench, against a pretend spine.
- **`legacy_uart_bridge` and `encoder_udp`:** today's car: the 2025-26 ESP32 over UART
  (115200 baud), and the wheel encoder over Ethernet. Not yet tried on the car.
- **The turtle, Gazebo** (`ros_gz_bridge`), **CARLA** (a stub).
- **The HUD's back end:** our topics ↔ the app, over Socket.IO on a WebSocket.
- **`foxglove_bridge`:** Foxglove or Lichtblick on a laptop.

**Perception:**

- **The detector** (`aav_yolo`): one per computer with a GPU, each under its own name
  (`yolo_detector_orin`, `yolo_detector_laptop`). The stop-sign watcher hears both.
- **The lane finder** (`aav_lane_finder`, new): the camera's picture → the lane lines →
  `/lane_geometry`, with OpenCV, in 0.78 ms a picture.
- **The radar clustering** (`aav_object_detection`): works on the pretend radar.
- **Obstacles in Nav2:** the radar in the local costmap, and `collision_monitor`'s stop
  zone. On the bench it stops the car 0.3-0.4 m before a box as wide as the lane. The
  cameras' layer is off until they're calibrated (Q22).

**The HUD:**

- **The 2025-26 app**, changed for our back end: an e-stop button, Cancel, the camera page,
  the car's status, the OpenStreetMap credit. On the bench, its e-stop stopped the car in
  0.3 s.
- **A bug fixed:** the app could never connect to its back end. It now uses WebSocket only.
- **The place database** (51 MB): `pixi run get-hud-map`.
- **Raylib: decided 11 October.** The HUD becomes one Rust program, raylib and rclrs, that
  is also its ROS node. Not started yet.

## Models used

| Model | What it does | Where it runs |
|---|---|---|
| YOLO11 nano (`yolo11n.pt`, Ultralytics, AGPL-3.0) | knows 80 everyday things, the stop sign among them | anywhere, with PyTorch: `pixi run get-models` |
| The same, for Core ML (`.mlpackage`) | the same | a Mac: 21 ms a picture; saw the stop sign from 20 m |
| The same, for TensorRT (`.engine`) | the same | the Orin, built there after its reflash |
| `best.pt` (the 2024-25 team's) | stop signs only | missing: probably on the team's NVIDIA Linux machine |
| The lane finder | classic OpenCV: no model to train | anywhere |
| The car model (URDF, from `vehicle.yaml`) | the car's frames and size | everywhere. Its numbers are guesses until the car is measured (Q1) |
| The bench's pretend sensors | GPS noise, the IMU, a drawn road for the camera, the radar against boxes | bench mode |

## Firmware

- **The CAN contract** (`firmware/can/aav.dbc`): every frame between ROS and the spine.
  Python and Rust both test against the same generated vectors.
- **`spine-core`** (Rust): the spine's logic. It boots latched, arms only when asked,
  stops on a 200 ms gap in the commands, and holds the e-stop. 54 tests.
- **The spine's device drivers** (Rust, `embedded-hal` 1.0):
  - `jrk-g2`: the steering and brake motor controllers;
  - `ad5311`: the throttle;
  - `pca9555`: the I/O expander;
  - `ibus`: the RC receiver;
  - `mcp2515`: the CAN chip;
  - `spine-board`: the glue to `spine-core`;
  - 137 tests, against pretend hardware.
- **The spine's Pico 2 program** (`boards/pico2`, Embassy): CAN, a 100 ms hardware
  watchdog, and the e-stop's spare contact (a cut wire reads as pressed). It builds
  (60 KB) and its UF2 file checks out; never flashed. `pixi run spine-flash` flashes it.
- **The 2025-26 C++ boards keep running today's car:** the ESP32, the wheel encoder Pico,
  the status display Pico. PlatformIO builds them, in the `firmware` environment.

## Porting to Rust

- **The rule** (Ben, 10 Oct): Rust for the firmware and the hardware drivers; our C++
  moves to Rust; each language written its own way, not C in Rust.
- **Done:**
  - the spine, all in Rust;
  - the ESP32's device logic, as Rust drivers;
  - Ben's Rust IMU driver (rclrs). `pixi run imu-compare` feeds both drivers the same
    bytes, and they agree;
  - a first Rust ROS node, as an example (`rust-listener`).
- **In progress:** the Rust IMU driver becomes the default, then the C++ one goes; the
  radar clustering becomes a Rust node.
- **Next:** the board drivers (the wheel encoder and display Picos); later, Python to
  Rust where it pays off.
- **micro-ROS:** none for now. We think again once we see the hardware.

## Simulators and bench mode

- **turtlesim** (`pixi run turtle`): a turtle that steers like the car. The first thing to
  try.
- **Gazebo** (`pixi run sim`): the car in 3D, with Ackermann steering, an IMU and GPS.
  Nav2 drives it to goals. Its window works on a Mac.
- **Bench mode** (`pixi run bench`): the whole car's software on one computer:
  - a pretend spine;
  - pretend GPS, IMU, wheel speed, camera (a drawn road with lane lines and a stop sign)
    and radar (boxes);
  - `pixi run bench-check`: seven checks, plus `--perception`, `--lane` and `--obstacle`.
- **Replay:** a recorded drive, run through the EKFs again.
- **CARLA:** parked this year: no Jazzy support yet (Q31).
- **Safety:** the stand-ins stay on the computer they run on (`tools/ros.sh --local`), so a
  pretend car can never reach the real one.

## Macs, Pixi, Core ML and MCP

- **Pixi with RoboStack:** one `pixi.toml` gives the same ROS 2 Jazzy on a Mac and on any
  Linux, with no admin rights.
- **Five environments:** the default, `ml` (PyTorch, YOLO), `mcp`, `firmware`
  (PlatformIO), `docs`.
- **On a Mac (Apple silicon):**
  - it builds in about 15 s, and every test passes;
  - the turtle, Gazebo with its window, Nav2, the Rust example and recording all work;
  - `pixi run doctor` checks the network before you join the car.
- **Core ML on the Mac:**
  - `pixi run -e ml export-coreml` makes the model (12 s);
  - `pixi run -e ml laptop-bench` runs the laptop's own detector against the bench;
  - it reads the camera's JPEG pictures, as it will over the car's WiFi.
- **The MCP server** (`tools/mcp_server.py`): lets Claude or another AI app read the docs,
  the contracts and the live ROS graph. It only reads, and never writes to ROS: a test
  checks.

## Testing

- **`pixi run test`:**
  - it builds everything, then runs Python 230, Rust 208 (plus a build for the Pico 2) and
    `colcon test` 291: 0 failures, 5 skipped;
  - also the style check (ament_flake8, ament_pep257) and the HUD app's own tests.
- **The contract check** (`pixi run check`): the running graph against
  `docs/interfaces.yaml` (58 topics, 6 services, 5 actions, 9 frames). 0 failures for the
  turtle, Gazebo, replay and the bench.
- **The bench checks:**
  - seven by default: start-up, the contract, the scripted drive, the EKF, both e-stops;
  - then the stop sign, lane keeping and the obstacle.
- **CI** (GitHub Actions) is set up to run `pixi run test` on Linux for every push, and on
  a Mac every night.
- **Safety checks:** the stand-ins can't reach the car; the MCP server can't write.

## Documentation

- **29 pages:** markdown in `docs/`, built into HTML and one PDF by `pixi run docs`.
  Short pages, with tables and pictures.
- **Start with:** [Start here](index.md), [Your first day](first-day.md),
  [Starting points](team.md) (one per team member), and [Your Mac](mac.md).
- **The three contracts:**
  - `docs/interfaces.yaml`: every topic, service, action and frame;
  - `firmware/can/aav.dbc`: every CAN frame;
  - `vehicle.yaml`: every car measurement.
- **The decisions:** [Decisions](decisions.md): Decided, Tentative, Proposed, and Q1–Q34.
- **The history:** `docs/history/`: every question and answer, Ben's messages word for
  word, and three audits.
- **The rules:** `CLAUDE.md` (for people and AI alike) and [Conventions](conventions.md).
- **The work list:** `TODO.md`.

## Paused on 11 October, saved on branches

Not merged yet. Each branch's unfinished part is in its last commit, "Work in progress".
The next session finishes each one, runs its checks, and merges it.

| Branch | Done there (committed, checked) | Unfinished (its last commit) |
|---|---|---|
| `wt/sim-full` | the road world in Gazebo: lane lines, a stop sign, an obstacle, the car's camera and radar; the car's whole graph in `pixi run sim`, checked by `sim-check` | the Simulation page, and a picture |
| `wt/ackermann` | one reverse speed for the whole car: 0.5 m/s, from `vehicle.yaml` | reversing in Nav2: behaviour trees, settings, a test |
| `wt/rust-ports` | the Rust IMU driver is the default, and the C++ one is gone | the radar clustering as a Rust node (`aav_radar_clusters`) |

## Street view?

- Nothing by that name yet. The closest:
  - the HUD's offline map and place search (OpenStreetMap, Ottawa);
  - the HUD's camera page;
  - the bench's drawn road picture;
  - Gazebo's road world, in progress.

## What's left for the first pass

The first pass: the whole car driving on this software, from the joystick to Nav2.

**At home, no car needed:**

- Finish and merge the three paused pieces (above).
- Drive with W A S D: the car or the turtle.
- The board drivers in Rust: the wheel encoder and display Picos.
- The raylib HUD: the driving screen first (speed, mode, the e-stop button, the camera).
- Nav2: the car weaves up to 1.5 m off its line (N7); `collision_monitor` flickers at its
  zone's edge; a timing race between frames.
- A first test with a real joystick, on the turtle.
- The spine on a desk: needs a spare Pico 2 and a 3.3 V MCP2515 CAN module.

**At the car** (the hardware audit starts on Friday 16 October):

1. Back up (image) the Orin and the Pis, before anything is reflashed.
2. A read-only look at the car's network and computers.
3. Jazzy on the car: the Orin to JetPack 7.2, the Pis to Ubuntu 24.04 (Q24), and Pixi on
   each.
4. Measure the car: `vehicle.yaml` (Q1), the steering calibration (Q2), the radar's
   mount.
5. Phase 0: the `car` profile on stands, then on the ground at walking pace. Through
   today's ESP32 (`aav_legacy`) first, or the spine.
6. The sensors on the car: the IMU, GPS (Q18), the wheel encoder. Then the cameras (Q22),
   the Orin's TensorRT model, and `best.pt`.
7. The spine in the car: its chip (Q10–Q13), the CAN wiring, the e-stop's spare contact
   (Q6).
8. Phase 1: the scripted drive on the car, then GPS A→B.

**For the team:**

- The team's `ROS_DOMAIN_ID`, and an owner for each area (Q33).
- The leaked secrets in the old repos revoked and changed (Q34).
- The brake after boot: keep it on, or let it go?
- The repo public or private, and a licence.
