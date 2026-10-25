# ecolo-av: the AAV 2026–27 autonomy stack

Single code base for the Ecolo autonomous vehicle (SYSC 4907, Carleton University).
Goal for Gate 4 (26 Feb 2027): drive from GPS point A to B at 1 m/s and stop within 1 m.

**New here? Start with [docs/getting-started.md](docs/getting-started.md).**

The ROS 2 workspace and spine firmware for Carleton's autonomous vehicle capstone, built
by the 2026–27 team. Target: **ROS 2 Jazzy on Ubuntu 24.04** on the car's computers (the
Jetson AGX Orin and the Raspberry Pis); Pixi on Macs and other Linux machines.

**Sensors become telemetry, drivers become one command, and ego moves the car.**

> **The plan for the year:** [PROPOSAL.md](PROPOSAL.md): everything done so far, what's left, how sure we are. What's left to build, in order: [PLAN.md](PLAN.md).
>
> **Car day:** [READ-ME-CAR-DAY.md](READ-ME-CAR-DAY.md), the runbook: ten sessions at the
> car, in order, each with who, how long, the commands and what you should see. Before you
> leave: `pixi run car-day-build`, then `pixi run car-day-check` until it says 0 missing.
>
> **This Friday (16 Oct):** [FRIDAY-TODO.md](FRIDAY-TODO.md), the tick-list: log in to every
> machine and survey it. [READ-ME-FRIDAY.md](READ-ME-FRIDAY.md): the audit, the network,
> and our stack on the car, step by step.
> After it: [TEAM-TODO.md](TEAM-TODO.md), the team's work list (such as upgrading the Jetson,
> after its backup).
> Every test, in order: [READ-ME-TESTS.md](READ-ME-TESTS.md). Measuring the car, a sheet for the team:
> [READ-ME-MEASURE-THE-CAR.md](READ-ME-MEASURE-THE-CAR.md).
> The whole car in Gazebo, and what's missing: [READ-ME-FULL-SIMULATION.md](READ-ME-FULL-SIMULATION.md).
>
> **Read first, in this order** (pages in this folder, written for Ben, 15 Oct):
> 1. [READ-ME-HOW-IT-ALL-FITS.md](READ-ME-HOW-IT-ALL-FITS.md): the layers bottom-up, what
>    happens at start-up, and how to test each layer.
> 2. [READ-ME-SIMULATION-AND-THE-CAR.md](READ-ME-SIMULATION-AND-THE-CAR.md): Gazebo, the
>    bench and the car; what's simulated, what's real.
> 3. [READ-ME-MAPS-AND-POSITION.md](READ-ME-MAPS-AND-POSITION.md): the EKFs, the map
>    frame, OpenStreetMap and costmaps.
> 4. [READ-ME-A-TO-B.md](READ-ME-A-TO-B.md): driving straight from A to B, three ways.
> 5. [READ-ME-PERCEPTION-AND-HUD-MAP.md](READ-ME-PERCEPTION-AND-HUD-MAP.md): YOLO vs
>    OpenCV, the lidar, and a map on the HUD.

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

## What's where

| Folder | What's in it |
|---|---|
| `src/` | ROS 2 packages, one folder per layer: sensors, localization, drivers, mux, ego, backends, plus the interfaces, the car description and the launch profiles |
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
