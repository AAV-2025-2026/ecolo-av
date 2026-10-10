# AAV 2026–27 autonomy stack

The ROS 2 workspace and spine firmware for Carleton's autonomous vehicle capstone, built
by the 2026–27 team. Target: **ROS 2 Jazzy on Ubuntu 24.04** on every computer: the
Jetson AGX Orin, the Raspberry Pis, and laptops.

**Sensors become telemetry, drivers become one command, and ego moves the car.**

- Sensor drivers feed two EKFs (`robot_localization`), which say where the car is.
- Drivers each propose a velocity: joystick, keyboard, scripted, Nav2, and later AI.
- `twist_mux` picks one, by priority.
- **ego**, the virtual car, turns it into an Ackermann command (speed and steering
  angle) within the car's limits.
- Exactly one backend plays the car: the real car over the CAN spine, today's car over
  UART, turtlesim, or Gazebo.

The picture and a walk-through are in [docs/guide.md](docs/guide.md).

> **Status:** the structure, the interface contract and the core logic are in place,
> and the logic is unit-tested. Nothing has been built with colcon or run under ROS
> yet. What works, what's untested and what's missing: [docs/status.md](docs/status.md).

## Quick start

1. **Get Jazzy:** Ubuntu 24.04 (native or in a VM), or Pixi/RoboStack on a Mac. See
   [docs/platforms.md](docs/platforms.md).
2. **Build:** from the root of this repository, run:

   ```bash
   source /opt/ros/jazzy/setup.bash
   rosdep install --from-paths src --ignore-src -y
   colcon build --symlink-install
   source install/setup.bash
   ```

3. **Drive a turtle like a car.**
   - First terminal: `ros2 launch aav_bringup turtle.launch.py`
   - Second terminal: `tools/keyboard.sh`. Hold `i` to drive, and `u`/`o` to turn.
4. **Run the tests that need no ROS** (any OS with Python 3, pytest, PyYAML and Rust):
   `tools/test.sh`

Next steps: Gazebo, replay and the car are in [docs/simulation.md](docs/simulation.md)
and [docs/guide.md](docs/guide.md#on-the-car).

## What's where

| Folder | Diagram box | What's in it |
|---|---|---|
| `src/aav_interfaces/` | | our message and action: `VehicleStatus`, `ScriptedDrive` |
| `src/aav_description/` | vehicle URDF | `config/vehicle.yaml` (every measurement), the URDF, an RViz viewer |
| `src/sensors/` | wheel+steer, IMU, GPS | driver configs (`aav_sensors`); the reused IMU, radar and battery drivers |
| `src/localization/` | ekf_local, ekf_global | `robot_localization` configs: two EKFs and `navsat_transform` |
| `src/drivers/` | joystick, remote, scripted, nav_premade | `aav_teleop`, `aav_scripted` (ours), `aav_navigation` (Nav2 config, car behaviour trees, maps) |
| `src/mux/` | twist_mux | priorities and the e-stop lock |
| `src/ego/` | ego | Twist → Ackermann, limits, command timeout |
| `src/backends/` | real car, CARLA, Gazebo/turtlesim | `aav_spine` (CAN), `aav_legacy` (today's ESP32), `aav_turtlesim`, `aav_gazebo`, `aav_carla` (stub) |
| `src/aav_bringup/` | | launch profiles (`turtle`, `sim`, `car`, `replay`), one file per machine, RViz layout |
| `src/hud/`, `hud/` | HUD | the 2025-26 touchscreen app, not yet ported ([docs/hud.md](docs/hud.md)) |
| `src/perception/` | lidar, cams (next year) | inherited perception packages, parked with `COLCON_IGNORE` |
| `firmware/` | below "real car" | the CAN frame map (`can/aav.dbc`), the Rust `spine-core` library, the inherited C++ firmware ([docs/firmware.md](docs/firmware.md)) |
| `tools/` | | `test.sh`, `keyboard.sh`, `check_graph.py`, `record.sh`, `replay_commands.sh`, `make_map.py`, udev rules |
| `docs/` | | below |

## Documentation

| Doc | Read it for |
|---|---|
| [guide.md](docs/guide.md) | how the parts fit; ROS 2 concepts in our terms; the tools (`ros2`, rqt, RViz, Foxglove) |
| [simulation.md](docs/simulation.md) | running without the car: turtlesim, Gazebo, replay; CARLA status |
| [platforms.md](docs/platforms.md) | installing Jazzy (Ubuntu, VM, Mac), building, networking, cross-compiling |
| [firmware.md](docs/firmware.md) | the spine: the CAN contract, `spine-core`, today's firmware and its hazards |
| [interfaces.md](docs/interfaces.md) | every topic, service, action and frame (generated from `interfaces.yaml`) |
| [car_measurements.md](docs/car_measurements.md) | `vehicle.yaml`, the URDF, how to measure the car |
| [costmaps.md](docs/costmaps.md) | costmap sizes, map files, pinning a map to GPS |
| [hud.md](docs/hud.md) | the touchscreen app and its port |
| [status.md](docs/status.md) | what works, what's untested, what's missing, next steps |
| [history/conversation.md](docs/history/conversation.md) | how we got here: every question asked, and the answer |
| [CLAUDE.md](CLAUDE.md) | conventions: units, names, languages, secrets, testing, git |

Decisions and open questions (**Q1–Q34**) are in the team design doc,
*AAV 2026–27 Autonomy Stack — Architecture & Plan* (a Claude Doc).

## Where the code came from

New code was written for this design. Code reused from the 2025-26 team (GitHub org
`AAV-2025-2026`) and the 2024-25 team (`Carleton-AAV-Capstone`) carries a
`PROVENANCE.md`: the source repository, branch and commit, plus every change since.
Credentials committed to those public repositories were not copied. They still need to
be rotated (Q34).
