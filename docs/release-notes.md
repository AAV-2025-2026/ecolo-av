# Release 0.1: the first pass

> **A snapshot from 11 October 2026.** What's true now: [Status](status.md) and [Features](features.md).

<p class="release-line">The AAV 2026–27 autonomy stack · 11 October 2026</p>

<div class="pitch"><p><b>The whole car's software, in one place, working end to end.</b>
Every driver, the virtual car (ego), localization, Nav2, perception and AI on every GPU,
the spine's firmware in Rust, three simulators and a full set of docs. It builds and
passes all of its tests, and it drives in simulation and on the bench. Next: the real
car.</p></div>

<div class="tiles">
<div class="tile"><b>26</b><span>ROS 2 packages, all building on Jazzy</span></div>
<div class="tile"><b>11</b><span>repos from the previous teams, merged into one workspace</span></div>
<div class="tile"><b>3</b><span>AI runtimes: PyTorch, Core ML on Macs, TensorRT on the Orin</span></div>
<div class="tile"><b>3</b><span>simulators: turtlesim, Gazebo and bench mode, plus replay</span></div>
<div class="tile"><b>0</b><span>failing tests: 291 colcon, 230 Python, 208 Rust</span></div>
<div class="tile"><b>2</b><span>platforms, one setup: Linux and macOS</span></div>
</div>

## Highlights

- **One workspace for the whole car.** Code from 11 of the previous teams' repos, merged
  and cleaned up, each with a record of where it came from. Six more were replaced by
  stock ROS packages.
- **One command path, from any driver to the wheels.** The joystick, the keyboard,
  scripted drives, Nav2 and lane keeping all go through one mux and **ego**, the virtual
  car, which keeps every command within what the car can really do.
- **AI on every GPU.** One YOLO detector per computer: Core ML on a MacBook (21 ms a
  picture; a stop sign seen from 20 m), TensorRT on the Orin, PyTorch anywhere else.
- **Navigation built for a car.** Nav2 with a planner for cars, no turning on the spot,
  GPS waypoints, and a stop zone that halts the car before an obstacle.
- **A CAN spine in Rust.** New firmware logic, five device drivers and a Pico 2 program,
  with watchdogs and a fail-safe e-stop input: 191 tests.
- **The whole car, tested without the car.** Bench mode runs the car's own software on
  one laptop and proves that it drives, stops for both e-stops, stops at a stop sign,
  keeps its lane and stops for an obstacle.
- **Macs are first-class.** One `pixi install` gives the same ROS 2 Jazzy, Gazebo and Nav2
  on a Mac as on Linux. No admin rights, no virtual machine.
- **Ready for AI tools.** A read-only MCP server lets Claude or another AI app read the
  docs, the contracts and the live graph, and never move the car.

## Everything in one workspace

**Merged in and cleaned up**, each with a `PROVENANCE.md` (its repo, its commit, every
change since):

- **The ESP32 actuator firmware** (AAV_cortex): it still drives today's car. Its protocol
  is rewritten in Python, and its device logic in Rust.
- **The wheel encoder** (Wheel_Encoders): a Pico 2 that counts spokes, read over Ethernet.
- **The IMU driver** (yahboom-IMU): fixed, then rewritten in Rust.
- **The TI radar driver and its clustering** (Nav_Radar).
- **Lane following** (Lane_Detection_ROS2), now with a lane finder of our own.
- **The in-car HUD** (User-Interface): the app and its back end, moved to our topics.
- **The steering geometry** (Motor_Steering) and **the joystick's button map**
  (joy_teleop_ackerman).
- **From the 2024-25 team:** the battery monitor, the camera calibrations, and the first
  YOLO stop-sign detector.

**Replaced by stock ROS packages:** the odometry (robot_localization), the path planners
(Nav2), the obstacle avoidance (Nav2's costmaps and collision monitor), the QNX layer
(twist_mux, the spine's watchdog and `ros2 bag`), and the joystick driver
(teleop_twist_joy).

## Driving: one path from any driver to the wheels

- **Five drivers:** the joystick (with a deadman button), the keyboard (from any laptop),
  scripted drives, Nav2, and lane keeping.
- **twist_mux** picks one by priority. The e-stop locks them all out.
- **ego, the virtual car,** turns the winning command into a speed and steering angle the
  car can do. It limits speed, acceleration and steering rate, and stops the car when the
  commands go stale.
- **Ackermann all the way:** ego sends Ackermann commands, never raw twists, and
  Gazebo's car steers the same way.
- **One backend at a time:** the turtle, Gazebo, today's car (the 2025-26 ESP32, over
  UART), or the new CAN spine. A driver can't tell which one is running.

## Knowing where the car is

- **Two EKFs** (robot_localization): `ekf_local` (wheel speed and the IMU) for smooth
  steering, and `ekf_global` (adding GPS) for planning.
- **Accurate on the bench:** 0.03–0.3 m from the truth. A replayed drive matches its
  recording within 0.03 m.
- **GPS:** the stock u-blox driver by default, with NMEA and `ublox_dgnss` as options.

## Navigation built for a car

- **Nav2, set up for Ackermann steering:** SmacPlannerHybrid plans paths a car can drive,
  Regulated Pure Pursuit follows them, and there's no Spin behaviour.
- **GPS waypoints** go through the same server.
- **Obstacles:** the radar feeds the local costmap, and collision_monitor's stop zone
  halts the car 0.3–0.4 m before an obstacle on the bench.
- **Proven in Gazebo and on the bench:** goals of 8 m and 9.5 m in Gazebo, and a 40 m
  bench route that stops at a stop sign on the way.

## Perception and AI on every GPU

- **YOLO11** (Ultralytics) finds stop signs, cars, people: 80 kinds of everyday object.
- **One model, three formats:** `.pt` for PyTorch anywhere, `.mlpackage` for Core ML on a
  Mac, `.engine` for TensorRT on the Orin.
- **Core ML on a MacBook:** 21 ms a picture, so all 10 pictures a second, and the stop sign
  first seen 20 m away. One command makes the model: `pixi run -e ml export-coreml`.
- **TensorRT on the Orin:** a tool builds the engine on the Orin itself, ready for its
  JetPack reflash.
- **One detector per computer,** each under its own name. The stop-sign watcher hears them
  all, so a laptop can add a second opinion over WiFi.
- **A new lane finder** (OpenCV, 0.78 ms a picture). On the bench, lane keeping brings the
  car from 0.3 m off the centre line back to within 5 cm in about 6 s.
- **Radar clustering** turns the radar's points into objects.

## Firmware: a CAN spine, in Rust

- **The CAN contract** (`aav.dbc`): every frame between ROS and the spine, tested from both
  sides against the same vectors.
- **spine-core,** the spine's logic: it boots latched, arms only when asked, stops on a
  200 ms gap in the commands (100 ms since 15 Oct), and holds the e-stop. 54 tests.
- **Five device drivers and the glue** (embedded-hal 1.0): the steering and brake motor
  controllers, the throttle, the I/O expander, the RC receiver and the CAN chip. 137
  tests.
- **A Pico 2 program** (Embassy): CAN, a 100 ms hardware watchdog, and a fail-safe e-stop
  input (a cut wire reads as pressed). It builds, ready to flash.
- **Today's car keeps running:** the 2025-26 C++ boards build in their own Pixi
  environment, until each Rust version replaces them.

## From C++ to Rust

- **The rule:** firmware and hardware drivers in Rust, and our C++ moving to Rust, each
  written in Rust's own style.
- **Done:** the spine; the ESP32's device logic, as Rust drivers; a Rust IMU driver that
  gives the C++ one's answers, fed the same bytes (the comparison went with the C++ driver); and a first
  Rust ROS node.
- **In the works:** the Rust IMU driver as the only one, and the radar clustering as a
  Rust node.

## Simulation and bench mode

- **turtlesim:** a turtle that steers like the car. The first thing a new member drives.
- **Gazebo:** the car in 3D, with Ackermann steering, an IMU and GPS, driven by Nav2 to
  its goals. Its window works on a Mac.
- **Bench mode:** the car's own software on one laptop, with a pretend spine and pretend
  GPS, IMU, wheels, camera and radar. `pixi run bench-check` proves the whole chain.
- **Replay:** a recorded drive, run through the EKFs again.
- **Safe by design:** the stand-ins never leave the computer they run on, so a pretend car
  can never reach the real one.

## Macs are first-class

- **Pixi and RoboStack:** one `pixi.toml` gives the same ROS 2 Jazzy, Gazebo and Nav2 on a
  Mac and on any Linux, with no admin rights.
- **Fast:** the whole workspace builds in about 15 s on a MacBook Pro, and every test
  passes.
- **ML on the Mac:** the laptop runs its own Core ML detector against the bench
  (`pixi run -e ml laptop-bench`), reading the camera's JPEG pictures, as it will over the
  car's WiFi.
- **A network doctor:** `pixi run doctor` checks that a Mac is ready to join the car.

## The HUD

- **The 2025-26 touchscreen app,** connected to our topics: an e-stop button, the camera,
  the car's status and the map.
- **Fixed:** the app could never reach its back end. It now connects over WebSocket.
- **On the bench,** its e-stop button stopped the car in 0.3 s.
- **Next: one Rust program** (raylib and rclrs), decided on 11 October.

## Ready for AI tools: the MCP server

- **What it does:** lets Claude, or any AI app that speaks MCP, read the docs, the three
  contracts and the live ROS graph, check the graph against the contract, and run the
  tests.
- **What it can't do:** publish, call services or change parameters, so it can't move the
  car; or read anything outside git. A test checks both.

## Safety by design

- **Four e-stops:** the car's own red button (untouched: it always works), the joystick's
  button, `pixi run estop` from any laptop, and the HUD's button.
- **Watchdogs at every layer:** ego stops on stale commands (0.3 s), the spine on a
  200 ms gap (100 ms since 15 Oct), and the Pico 2's hardware watchdog after 100 ms.
- **The spine boots latched** and arms only on a deliberate request, so a reboot never
  restarts the car.
- **Start slow:** ego caps the car at 1.0 m/s until the test plan raises it.
- **No secrets in git:** checked across the whole history. The old repos' leaked
  credentials were never copied.

## Quality: tests, contracts and docs

- **`pixi run test`:** builds everything, then runs 291 colcon tests, 230 Python and 208
  Rust: 0 failures. The style check and the HUD app's own tests run too.
- **Contracts, checked live:** 58 topics, 6 services, 5 actions and 9 frames in
  `docs/interfaces.yaml`, and the running graph is checked against them. The CAN frames
  and the car's measurements each have a contract too.
- **CI:** GitHub Actions runs the suite on Linux for every push, and on a Mac every night.
- **29 pages of docs,** in HTML and one PDF, written to scan: a first-day guide, a page
  per area, the decisions, and every question answered.

## By the numbers

| What | How many |
|---|---|
| Built | 9–11 October 2026, about 170 commits |
| ROS 2 packages | 26: 13 in Python, 13 in CMake (one of them Rust) |
| Rust firmware | 8 crates, and a Pico 2 program |
| Launch profiles | 5: turtle, sim, bench, replay, car |
| Machine files | 4: the Orin, the Motor Pi, a laptop, everything |
| Tests | 291 colcon, 230 Python, 208 Rust, and the bench checks |
| Docs | 29 pages and 11 pictures |
| Tools | 26 scripts and 34 `pixi run` tasks |

## Coming next

- **16 October: the hardware audit** at the car, read-only first: backups, the
  inventory, the measurements.
- **Driving with W A S D,** the car or the turtle.
- **Jazzy on the car's computers,** then Phase 0: the car on stands, then at walking pace.
- **Ready to merge:** a road world in Gazebo, reversing in Nav2, and the radar clustering
  in Rust.
- **Then:** the board drivers in Rust, and the raylib HUD.

## Credits

- **The 2025-26 team** (AAV-2025-2026) and **the 2024-25 team** (Carleton-AAV-Capstone),
  whose code and lessons this release builds on.
- **Open-source projects:** ROS 2 Jazzy, Nav2, robot_localization, twist_mux, imu_tools,
  Gazebo, RoboStack and Pixi, rclrs, Ultralytics YOLO, embedded-hal and Embassy.
- **The full credits** are in the repository's README.
