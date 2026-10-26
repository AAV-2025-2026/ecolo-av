# rust-listener: a first ROS 2 node in Rust

## Overview

Prints what ego tells the car to do (`/ego/actuator_cmd`), 50 times a second. An example
of a Rust ROS node (rclrs): it only listens.

```bash
pixi run turtle            # terminal 1: the stack, with turtlesim as the car
pixi run keyboard          # terminal 2: drive
pixi run rust-listener     # terminal 3: this node
```

## Interface

| Kind | Name | Type |
|---|---|---|
| Node | `rust_listener` | |
| Subscribes | `/ego/actuator_cmd` | `ackermann_msgs/msg/AckermannDriveStamped` |
| Prints | one line a message: `ego: speed +1.00 m/s, steering +0.100 rad` | |

No parameters, no services. One file: `src/main.rs`.

- `rclrs` (writing nodes) and `ros-env` (the message types) come from crates.io.
- The message code itself ships with Jazzy: `ros-env` finds it on `AMENT_PREFIX_PATH`,
  ours (`aav_interfaces`) included. So `use ros_env::aav_interfaces::msg::VehicleStatus;`
  works too.

## Invariants

- Read-only: it publishes nothing, so it can't move the car.
- Units as the topic: speed in m/s, steering in radians, positive = left (REP-103).

## Side Effects

- Joins the ROS graph it is started on, through `tools/ros.sh`, and prints to stdout.
- The first build downloads crates from crates.io into Cargo's cache.

## Verification

```bash
pixi run rust-listener     # builds it, then runs it
```

- It's plain Cargo: colcon doesn't build it. The first build downloads and compiles
  about 100 crates (under a minute); after that, a build takes seconds.
- No automatic test: neither `tools/test.sh` nor `pixi run test` builds it.
