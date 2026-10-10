#!/usr/bin/env bash
# Record a drive. Raw inputs (to re-run localization: aav_bringup replay.launch.py),
# commands (to replay the drive: tools/replay_commands.sh), and what the stack
# decided (to see why it did what it did). No camera images: they are huge.
#
# usage: tools/record.sh [name]       -> bags/<date>_<name>/ (MCAP, Jazzy's default)
set -euo pipefail
cd "$(dirname "$0")/.."
name="${1:-drive}"
out="bags/$(date +%Y-%m-%d_%H%M%S)_${name}"
mkdir -p bags
# Through tools/ros.sh, which sources the workspace last: on a Mac, starting this script
# (/usr/bin/env bash) drops DYLD_LIBRARY_PATH, and then ros2 bag can't load our own
# messages (/vehicle/status).
exec tools/ros.sh ros2 bag record -o "$out" --topics \
  /vehicle/odom /vehicle/status /vehicle/joint_states \
  /imu/data_raw /imu/data /imu/mag /gps/fix /battery_status \
  /joy /estop /cmd_vel /cmd_vel/joy /cmd_vel/remote /cmd_vel/scripted /cmd_vel/nav \
  /ego/actuator_cmd /to_can_bus /from_can_bus \
  /odometry/local /odometry/global /odometry/gps /gps/filtered \
  /tf /tf_static /robot_description /plan /goal_pose /clock
