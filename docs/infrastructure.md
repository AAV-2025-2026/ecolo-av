# Infrastructure: how the project is put together

For whoever puts the whole thing together. [How it fits](how-it-fits.md) explains the
car's software: sensors, drivers, the mux, ego, backends. This page explains everything
around it: the repo, the environment, the contracts, the profiles, the computers, the
tests, and how a change goes from an idea to the car.

## The pieces at a glance

| Piece | What it is | Where |
|---|---|---|
| The car's software | ROS 2 Jazzy packages, one folder per layer | `src/` |
| The car's firmware | the CAN contract, the Rust spine logic, the 2025-26 boards' code | `firmware/` |
| The touchscreen app | the 2025-26 Flutter HUD, not yet ported | `hud/` |
| The environment | ROS, Gazebo, compilers, Python and Rust, all from Pixi | `pixi.toml`, `pixi.lock` |
| The tools | tests, the graph check, the network doctor, recording, docs, the mailer | `tools/` |
| The docs | short markdown pages, built into web pages and one PDF | `docs/` |
| The rules | names, units, secrets, git, testing | `CLAUDE.md` |
| The decisions | Decided, Tentative, Proposed, and Q1–Q34 | the design doc: summary in [Decisions](decisions.md) |

## The repo, folder by folder

```text
aav/
  CLAUDE.md           the rules, for people and Claude sessions alike
  README.md, TODO.md  the front page; the current work list
  pixi.toml           the environment, and the one-word tasks (pixi run <task>)
  pixi.lock           the exact version of every package: committed, so every laptop matches
  src/                ROS 2 packages (colcon builds these)
    aav_bringup/        whole-system launch profiles: turtle, sim, car, replay
    aav_description/    the car's model (URDF) and vehicle.yaml, the car's measurements
    aav_interfaces/     our own messages and actions
    sensors/            drivers that turn devices into standard messages
    localization/       the two EKFs and navsat_transform: configuration only
    drivers/            everything that proposes a command: teleop, scripted, Nav2
    mux/                twist_mux: picks one command
    ego/                the virtual car: one command into speed and steering
    backends/           whatever plays the car: the real car, Gazebo, turtlesim, CARLA
    perception/         parked: lanes, objects, YOLO (next year)
    hud/                the HUD's web server (maincar)
  firmware/           microcontroller code (colcon ignores it)
    can/                aav.dbc, the CAN contract, and its test vectors
    spine/              Rust: spine-core, the spine's logic, with its tests
    legacy/             the 2025-26 ESP32 and Pico code that runs the car today
  hud/                the 2025-26 Flutter app (colcon ignores it)
  examples/           rust-listener: a first ROS node in Rust
  tools/              scripts: see the table below
  docs/               these pages; docs/history/ keeps the Q&A, Ben's requests and the audits
```

## The three contracts

Three files say how the parts must talk. Change the contract first, then the code, and
the checks tell you if the two disagree.

| Contract | Holds | Checked by | After you change it |
|---|---|---|---|
| `docs/interfaces.yaml` | every topic: its type, who publishes it, who reads it, and in which profiles it must be live | `pixi run check <profile>` on a running system; `pixi run test` checks that the Topics page matches | `pixi run python tools/gen_interfaces_md.py > docs/interfaces.md` |
| `firmware/can/aav.dbc` | every CAN frame between ROS and the spine | test vectors, shared by the Python codec and the Rust tests | update `can_codec.py` and `protocol.rs`, run `firmware/can/gen_test_vectors.py`, run both test suites |
| `src/aav_description/config/vehicle.yaml` | every measurement of the car | its unit test; ego, the URDF, Nav2 and the adapters all read it | measure the car: [Car numbers](car_measurements.md) |

## The environment: Pixi

Pixi installs ROS 2 Jazzy and every tool into the repo's own `.pixi` folder, from
RoboStack and conda-forge. No admin rights, and the same versions on every computer,
because `pixi.lock` pins them all.

| Platform in `pixi.toml` | Who uses it |
|---|---|
| `linux-64` | Linux laptops and oirp-spss |
| `linux-aarch64` | the car's ARM computers (Orin, Pis), to run Jazzy before a reflash |
| `osx-arm64`, `osx-64` | Macs, Apple Silicon and Intel (macOS 14 or newer) |

| Command | Does |
|---|---|
| `pixi install` | downloads and installs everything in `pixi.lock` (about 7 GB the first time) |
| `pixi run <task>` | runs a task inside the environment: see the next table |
| `pixi run <any command>` | runs any command inside it, e.g. `pixi run tools/ros.sh ros2 topic list` |
| `pixi shell` | a terminal inside it; then `source install/setup.zsh` (Mac) or `setup.bash` (Linux) |

!!! note "Macs only: GNU coreutils"
  On a Mac, macOS's System Integrity Protection deletes `DYLD_LIBRARY_PATH` whenever
  `/bin/sh` or `/usr/bin/env` starts, and ROS needs that setting to load our own messages.
  So the Mac environment adds GNU `coreutils` for `colcon test`, and scripts that run ROS
  commands go through `tools/ros.sh`. Details: [Your Mac](mac.md).

## The one-word tasks

All defined in `pixi.toml`. Run them from the repo's top folder.

| Task | Does |
|---|---|
| `build` | compiles our packages (`colcon build --symlink-install`) |
| `test` | every test: unit tests, the Rust spine, style, `colcon test` |
| `lint` | ROS's style rules on our Python |
| `turtle` | the stack, with turtlesim as the car |
| `keyboard` | drive from the keyboard (`--sim` with Gazebo) |
| `sim` | the stack, with Gazebo as the car (`gui:=false` on a Mac) |
| `gz-window` | Gazebo's window, for a simulator started with `gui:=false` |
| `car` | the real car: `pixi run car orin` (or `motor_pi`, `laptop`, `all`) |
| `view` | the car's model in RViz |
| `rviz` | RViz with the driving layout: map, costmaps, path, car |
| `graph` | rqt_graph: nodes and topics, live |
| `check` | the running graph against the contract: `pixi run check sim` |
| `estop`, `estop-clear` | stop every driver; let them go again |
| `doctor` | can this computer join the car's ROS network? |
| `rust-listener` | the Rust example: prints ego's commands |
| `docs` | rebuilds the docs pages and the PDF |

## The scripts in tools/

| Script | Purpose | How to run it |
|---|---|---|
| `test.sh` | the tests that don't need ROS: Python logic, Rust spine, the Topics page | inside `pixi run test` |
| `lint.sh` | `ament_flake8` and `ament_pep257` on our Python | `pixi run lint` |
| `ros.sh` | runs a command with the workspace sourced | used by most tasks |
| `keyboard.sh` | teleop_twist_keyboard into `/cmd_vel/remote` | `pixi run keyboard` |
| `check_graph.py` | compares a running system with `docs/interfaces.yaml` | `pixi run check <profile>` |
| `gen_interfaces_md.py` | makes the Topics page from the contract | see the contracts table |
| `doctor.py` | network checks for joining the car | `pixi run doctor` |
| `record.sh` | records a drive into `bags/` | `pixi run tools/record.sh <name>` |
| `replay_commands.sh` | plays a recorded drive's commands back into the mux | `pixi run tools/ros.sh tools/replay_commands.sh <bag>` |
| `make_map.py` | draws a Nav2 map from a short spec | `pixi run python tools/make_map.py <spec>` |
| `build_docs.py` | builds the docs pages and the PDF | `pixi run docs` |
| `progress_mail.py` | emails a red-and-white progress report | see its docstring |
| `udev/99-aav.rules` | stable device names on the car (`/dev/aav/imu`, ...) | install on the car's Linux computers |

## Launch profiles: the same nodes, a different car

Everything above the backend is the same in every profile. Only what plays the car
changes.

| Profile | Start it with | The car is | Runs |
|---|---|---|---|
| `turtle` | `pixi run turtle` | the turtlesim turtle | mux, ego, scripted driver, the car's model, `ekf_local` |
| `sim` | `pixi run sim` | Gazebo | the whole stack: both EKFs, `navsat_transform`, Nav2 |
| `car` | `pixi run car <machine>` | the real car | the parts its machine file switches on |
| `replay` | `ros2 launch aav_bringup replay.launch.py`, with a bag playing | a recorded drive | localization (and Nav2) on real sensor data |

## The computers, and what runs where

The car runs one ROS graph across several computers. Each one starts `pixi run car
<machine>`, and `src/aav_bringup/config/machines/<machine>.yaml` switches its parts on.

| Machine | Runs | Today |
|---|---|---|
| `orin` (Jetson AGX Orin) | the car's model, mux, ego, scripted driver, IMU, GPS, localization, Nav2, Foxglove | Ubuntu 22.04 and Humble: it must move to Jazzy first (Q24) |
| `motor_pi` | the legacy bridges to today's ESP32 (UART) and the wheel encoder (UDP) | Humble |
| `laptop` | the safety driver's joystick | any laptop with Pixi |
| `all` | everything on one computer: for a bench test | |
| the spine | a microcontroller on CAN: throttle, brake, steering, watchdog | not built yet: Q10–Q17 |

The development computers:

| Computer | Use |
|---|---|
| oirp-spss | Ben's AlmaLinux workstation: builds and tests headless (no screen) |
| Ben's Mac | development, rqt_graph, Gazebo, RViz; one day, driving and watching the car |
| team laptops | the same, with Pixi: [Your first day](first-day.md) |

## How a change goes from an idea to the car

| # | Step | Where |
|---|---|---|
| 1 | Change the contract first, if the change touches one | the contracts table above |
| 2 | Write the logic in a plain module, with tests | `src/<layer>/<package>/` |
| 3 | Keep the node thin, with a docstring of what it reads and writes | the same package |
| 4 | Register it: a launch profile, the mux (drivers), `tools/test.sh` (tests) | [Build a driver](howto-driver.md) |
| 5 | `pixi run test`, then the turtle, then `pixi run check sim` in Gazebo | [Simulation](simulation.md) |
| 6 | Update the docs page, then `pixi run docs` | `docs/` |
| 7 | Commit small, each commit passing the tests; inherited code gets a `PROVENANCE.md` line | `git` |
| 8 | On the car: stands first, then the ground at walking pace, with a safety driver | the test ladder |

## Sharing the code, until there's a GitHub org

`main` stays local until the team picks a GitHub org (Q25). The previous teams' orgs are
public, so nothing is pushed there.

| Task | Command |
|---|---|
| Make a bundle to hand over | `git bundle create ../aav.bundle HEAD main` (keep `HEAD`, or a clone checks out nothing) |
| Start from a bundle | `git clone aav.bundle aav` |
| Take newer work from a bundle | copy the new bundle over the old one, then `git pull` |

!!! warning "What never goes in git"
  Build output (`build/`, `install/`, `log/`, `.pixi/`, `target/`), recordings (`bags/`),
  and secrets. `.gitignore` lists them. Downloaded third-party source, such as ROS's own
  code, belongs in a `vendor/` folder that git doesn't track: proposed, see
  [Decisions](decisions.md).

## Where to find what happened

| Want | Look in |
|---|---|
| Why something is the way it is | `docs/history/conversation.md`: the Q&A record, by topic, with its open threads |
| Ben's requests, word for word | `docs/history/messages-*.md` |
| The audits of the inherited code, the firmware and the live system | `docs/history/audit-2026-10-10-*.md` |
| What's next | `TODO.md` and [Work](work.md) |
| What changed, and why | `git log` |
