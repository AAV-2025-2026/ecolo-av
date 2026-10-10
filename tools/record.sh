#!/usr/bin/env bash
# Record a drive. Raw inputs (to re-run localization: aav_bringup replay.launch.py),
# commands (to replay the drive: tools/replay_commands.sh), and what the stack
# decided (to see why it did what it did). No camera images: they are huge.
#
# usage: tools/record.sh [name]       -> bags/<date>_<name>/ (MCAP, Jazzy's default)
set -euo pipefail
name="${1:-drive}"
out="bags/$(date +%Y-%m-%d_%H%M%S)_${name}"
mkdir -p bags
exec ros2 bag record -o "$out" \
  /vehicle/odom /vehicle/status /vehicle/joint_states \
  /imu/data_raw /imu/data /imu/mag /gps/fix /battery_status \
  /joy /estop /cmd_vel /cmd_vel/joy /cmd_vel/remote /cmd_vel/scripted /cmd_vel/nav \
  /ego/actuator_cmd /to_can_bus /from_can_bus \
  /odometry/local /odometry/global /odometry/gps /gps/filtered \
  /tf /tf_static /robot_description /plan /goal_pose /clock
