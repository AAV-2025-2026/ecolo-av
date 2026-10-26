# examples

## Overview

Small programs to learn from. They are not part of the car, and no test or CI job
builds them.

## Subdirectories & Boundaries

| Folder | What it is |
|---|---|
| [rust-listener](./rust-listener/README.md) | a first ROS node in Rust (rclrs): subscribes to `/ego/actuator_cmd` and prints speed and steering. Publishes nothing |

## Invariants

- Examples only read: they never publish a command to the car.
- They follow the same rules as the real code: REP-103 units, topic names by area.

## Side Effects

- They join the ROS graph of whatever network they run on (through `tools/ros.sh`).

## Verification

- Run: `pixi run rust-listener` (builds it with Cargo, then runs it).
