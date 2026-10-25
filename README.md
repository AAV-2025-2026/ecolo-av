# ecolo-av: the AAV 2026–27 autonomy stack

Single code base for the Ecolo autonomous vehicle (SYSC 4907, Carleton University).
Goal for Gate 4 (26 Feb 2027): drive from GPS point A to B at 1 m/s and stop within 1 m.

**New here? Start with [docs/getting-started.md](docs/getting-started.md).**

The ROS 2 workspace and spine firmware for Carleton's autonomous vehicle capstone, built
by the 2026–27 team. Target: **ROS 2 Jazzy on Ubuntu 24.04** on the car's computers (the
Jetson AGX Orin and the Raspberry Pis); Pixi on Macs and other Linux machines.

**Sensors become telemetry, drivers become one command, and ego moves the car.**

Every page is in [`docs/`](docs/). The ones people ask for most:

| Page | What it's for |
|---|---|
| [The plan](docs/plan.md) | what's left to build, in order, by the gates |
| [Features](docs/features.md) | what the software does, why, and who built it |
| [Car day](docs/car-day.md) | the runbook at the car: `pixi run car-day-build`, then `pixi run car-day-check` until it says 0 missing |
| [Every test](docs/tests.md) | every test, in order: simulator, bench, stands, lot, the whole drive |
| [Measure the car](docs/measure-the-car.md) | the sheet for whoever measures the car |
| [Bottom-up](docs/start-up.md) | each layer from the device up, start-up, and testing each layer |
| [Sim and the car](docs/sim-and-car.md), [Full simulation](docs/full-simulation.md) | what's simulated, what's real, and what's missing |
| [Maps and position](docs/maps-and-position.md), [A to B](docs/a-to-b.md) | the EKFs and OpenStreetMap; driving from A to B |
| [Perception options](docs/perception-and-hud-map.md) | which model for which job, the lidar, a map on the HUD |

## Read the docs

Open **`docs/html/index.html`** in a browser: short pages with pictures. There's also a
single PDF, built by `pixi run docs` into `docs/html/aav-docs.pdf`.

The pages are made from the markdown in `docs/`. Edit those, then run `pixi run docs`.

## Your first day

New to the team? Do these in order, on a Mac or on Linux.
[Your first day](docs/first-day.md) walks through each step, with what you should see.

| # | Do this | How long |
|---|---|---|
| 1 | Mac only: `xcode-select --install` | a few minutes, once |
| 2 | Install Pixi: the `curl` line below, then open a new terminal | under a minute, once |
| 3 | Get the code: `git clone` it from GitHub (ask Ben to add you to `AAV-2025-2026/ecolo-av`) | seconds |
| 4 | `pixi install` | the first time, a few minutes: it downloads about 4 GB |
| 5 | `pixi run build`, then `pixi run test` | a few minutes the first time |
| 6 | `pixi run turtle`, or `pixi run sim` | ready |

The same steps, as commands:

```bash
xcode-select --install                        # 1. Mac only: Apple's git and compiler
curl -fsSL https://pixi.sh/install.sh | sh    # 2. Pixi; then open a new terminal
git clone git@github.com:AAV-2025-2026/ecolo-av.git ~/ecolo-av && cd ~/ecolo-av   # 3. the code
pixi install                                  # 4. ROS 2 Jazzy and every dependency
pixi run build && pixi run test               # 5. our packages, then every test
pixi run turtle                               # 6. terminal 1: a turtle that steers like the car
pixi run keyboard                             #    terminal 2: hold i to drive, u or o to turn
```

When something fails: [docs/run.md](docs/run.md).

## Set things up (once)

After [Your first day](#your-first-day), add only the parts you need:

| To use | Run once | More |
|---|---|---|
| The object detector (RF-DETR, YOLO) | `pixi run get-models` | [Perception](docs/perception.md) |
| The map window's street map and place search | `pixi run get-street-map`, `pixi run get-hud-map` | [HUD](docs/hud.md) |
| Street routes (Valhalla) | `pixi run -e routes get-routes` | [Street routes](docs/routes.md) |
| The camera stream check | `pixi run get-mediamtx` | [Camera pipeline](docs/camera-pipeline.md) |
| CARLA on Carleton's streets | `pixi run get-carla-osm` | [CARLA](docs/carla.md) |
| The Flutter HUD app | `pixi run get-flutter` (4.3 GB) | [HUD](docs/hud.md) |
| Flashing a Pico 2 with a debug probe | `pixi run spine-tools` | [Rust firmware](docs/rust-firmware.md) |
| The Rust ESP32 firmware | `pixi run esp-tools`, and `pixi run esp-qemu-tools` for the QEMU check | [ESP32 first flash](docs/esp32-bench.md) |
| ROS 2 and rclrs source, to look things up | `pixi run vendor` (560 MB) | `vendor/README.md` |
| A Mac on the car's network | `pixi run doctor`, then do what it says | [Your Mac](docs/mac.md) |
| The car's computers (offline, no sudo) | `pixi run car-kit`, copy `car-kit/` to a USB stick | [From a USB stick](docs/car-install.md) |
| Claude Code | start it in this folder: `CLAUDE.md` and the read-only MCP server (`.mcp.json`) load by themselves | [AI apps](docs/mcp.md) |
| Designs with the Elephant-Goldfish plugin | `claude plugin marketplace add google/elephant-goldfish-model && claude plugin install egm@egm` | `CLAUDE.md`, "Elephant-Goldfish" |

## Every command

Each one is `pixi run <command>`, from this folder. "This computer only" means it never
reaches a real car on the same network. The full list, with every option: `pixi task list`.

### Every day

| Command | What it does |
|---|---|
| `build` | compiles our ROS packages |
| `test` | every test and the style check, on this computer only |
| `lint` | checks our Python against ROS's style rules |
| `docs` | rebuilds the web pages and the PDFs in `docs/html/` |

### Try it, without the car (this computer only)

| Command | What it does |
|---|---|
| `turtle` | turtlesim plays the car |
| `keyboard` | drive from the keyboard (a second terminal, with `turtle` or `sim`) |
| `sim` | Gazebo plays the car (`world:=road`, `hud:=true`, `sim_speed:=3`...) |
| `demo` | the whole simulated car at once: Gazebo, RViz, the HUD and the map window (`demo fullscreen`) |
| `bench` | the real car's software, with stand-ins for the hardware |
| `view` | the car's model in RViz |
| `rviz` | RViz with the driving layout: map, costmaps, path, car |
| `gz-window` | Gazebo's window again, for a simulator already running |
| `goto` | drive to one point and stop smoothly: `goto --sim --ahead 20` |
| `ghost` | a pretend person in Nav2's view, to test stopping: `ghost ahead 10` |
| `sim-fault` | make a Gazebo sensor fail on purpose: `sim-fault gps stop`, then `sim-fault gps ok` |
| `carla-car` | CARLA plays the car: `carla-car host:=<the CARLA computer>` |
| `hud-demo`, `map-demo` | the in-car screen and the map window, with pretend data: no ROS |

### Check that it works

| Command | What it does |
|---|---|
| `check` | the running graph against the contract: `check turtle` (or `sim`, `road`, `spine`, `car`, `replay`, `bench`) |
| `bench-check` | starts bench mode and tests the whole graph: contract, drive, e-stops (2 min) |
| `sim-check` | starts Gazebo's road world headless and tests the whole graph in it (2 min) |
| `controller-compare` | Regulated Pure Pursuit against MPPI on the same routes, headless |
| `heading-check` | the global EKF's heading against Gazebo's truth, at walking pace |
| `timing-test` | are messages on time? 5 min parked, then 5 min driving |
| `stream-check` | the camera stream end to end, without the car (needs `get-mediamtx`) |
| `layout-check` | is every topic in our Foxglove layouts served? |
| `graph`, `graph-picture` | a live picture of the nodes and topics; save it to `docs/img/graph.svg` |
| `bandwidth` | every topic's rate, size and MB/s, biggest first |
| `can-load` | how busy the CAN bus is, frame by frame |

### At the car

| Command | What it does |
|---|---|
| `car` | the real car: `car orin` (or `motor_pi`, `laptop`, `all`) |
| `estop`, `estop-clear` | block every driver (the car brakes); clear it |
| `gate-clear` | a person reopens the output mux after it latched STOP |
| `watchdog-clear` | a person clears the sensor watchdog's latched faults |
| `hud`, `map` | the in-car screen and the map window, as ROS nodes (`fullscreen:=true`) |
| `actuator-test` | the actuator tests, on stands and in a lot: `actuator-test --list` |
| `calibrate-camera` | calibrate a streamed camera: `calibrate-camera board` prints the checkerboard |
| `doctor` | can this computer join the car's ROS network? Says what to fix |
| `net-map` | maps the network you're on: machines, ports, ROS domains. Read-only |
| `survey` | surveys every car computer over ssh, read-only: `survey ~/aav-audit/hosts.txt` |
| `shm-clean` | removes Fast DDS files left by ROS programs that died |

### Before car day

| Command | What it does |
|---|---|
| `car-day-check` | is this laptop ready? Run it until it says 0 missing |
| `car-day-build` | builds what the laptop takes to the car (the ESP32 firmware, the C++ way back...) |
| `car-kit` | makes `car-kit/`, to install our Jazzy on the car's computers from a USB stick |

### Firmware

| Command | What it does |
|---|---|
| `spine-uf2`, `wheel-uf2`, `sentinel-uf2` | build a Pico 2 program as a UF2 file: hold BOOTSEL, plug in, drag it on |
| `spine-flash`, `wheel-flash`, `sentinel-flash` | flash it through a debug probe, then show its logs (needs `spine-tools`) |
| `esp-build`, `esp-flash` | build, or build and flash, the Rust firmware for today's ESP32 board (bench only) |
| `esp-qemu-check` | boots the ESP32 firmware in QEMU: does it brake within 0.2 s when the heartbeat stops? |
| `-e firmware legacy-esp32` | builds today's C++ ESP32 firmware with PlatformIO (`-t upload` flashes it) |

### Perception, AI and maps

| Command | What it does |
|---|---|
| `detect` | the object detector on a picture or the cameras: `detect picture:=<file>` |
| `laptop-bench` | your laptop's own detector against bench mode |
| `talk` | tell the car what to do in plain English; a local model plans it (turtle, sim or bench only) |
| `llm-eval` | scores local models on the plain-English test set |
| `-e mcp mcp`, `-e mcp drive-server` | the MCP servers for Claude: read-only, and the drive tools. Claude starts them |
| `-e routes router` | the street router on 127.0.0.1:8002 (needs `get-routes`) |

### Learn

| Command | What it does |
|---|---|
| `vehicle-model` | the car as a linear model: poles, step responses, Bode margins |
| `state-space-demo` | the state-space primer's simulator |
| `rust-listener` | a Rust (rclrs) ROS node that prints ego's commands |
| `flutter`, `hud-test` | Flutter for the HUD app; its tests (needs `get-flutter`) |

## What's where

| Folder | What's in it |
|---|---|
| `ros/` | ROS 2 packages, one folder per area: sources (sensors), localization, perception, drivers, command_mux, io_mux, ego, can_bridge (the real car), sim, safety, hud; bringup has the launch profiles and the car description, ecolo_msgs the interfaces profiles |
| `firmware/` | the CAN contract (`can/aav.dbc`), the spine's Rust logic and device drivers (`spine/`), and the inherited C++ firmware (`legacy/`) |
| `tools/` | tests, keyboard, graph check, the network doctor, recording, the docs builder, the progress mailer, the MCP server for AI apps |
| `examples/` | small runnable examples: a first ROS node in Rust (`rust-listener`) |
| `docs/` | the docs (markdown sources, the HTML in `docs/html/`), the topic contract, and the history |
| `hud/` | the 2025-26 touchscreen app. Its back end is ported, as `ros/hud/aav_hud` |
| `models/` | the YOLO models, downloaded by `pixi run get-models` (not in git) |
| `vendor/` | the ROS 2 and ros2-rust source, for looking things up. Not ours, and not in git: `pixi run vendor` downloads it |

## Status

Everything builds on Jazzy, on Linux and on Macs, and every test passes. The turtle,
Gazebo and bench mode (the whole car's software, with stand-ins for the hardware) all
run. Nothing has run on the car yet. What works, what's untested and what's missing:
[docs/status.md](docs/status.md).

Decisions and open questions (**Q1–Q34**) are in the team design doc, *AAV 2026–27
Autonomy Stack — Architecture & Plan* (a Claude Doc). Conventions are in
[CLAUDE.md](CLAUDE.md).

## Credits

| Who | What |
|---|---|
| The 2026-27 AAV capstone team | this design, the new code, and every decision: see [Decisions](docs/decisions.md) |
| The 2025-26 team (GitHub org `AAV-2025-2026`) | the ESP32 actuator firmware, the Pico 2 wheel encoder, the IMU driver, the radar driver and its clustering, lane keeping, the HUD app, and the steering geometry |
| The 2024-25 team (`Carleton-AAV-Capstone`) | the battery monitor, the camera calibrations, and the first YOLO stop-sign detector |
| Open-source projects | ROS 2 Jazzy, Nav2, robot_localization, twist_mux, imu_tools, Gazebo, RoboStack and Pixi, rclrs (ros2-rust), Roboflow's RF-DETR (the car's object detector), Ultralytics YOLO, NVIDIA TensorRT, Apple's Core ML Tools, and Rust's embedded-hal |
| Claude (Anthropic) | an AI assistant that helped write code, tests and these docs, under the team's direction |

Each piece copied from the 2025-26 or 2024-25 team keeps a `PROVENANCE.md`, as the next
section says.

## Where the code came from

New code was written for this design. Code reused from the 2025-26 team (GitHub org
`AAV-2025-2026`) and the 2024-25 team (`Carleton-AAV-Capstone`) carries a
`PROVENANCE.md`: the source repository, branch and commit, plus every change since.
Credentials committed to those public repositories were not copied. They still need to
be rotated (Q34).
