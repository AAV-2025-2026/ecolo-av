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
  /sensors/imu/data_raw /sensors/imu/data /sensors/imu/mag /sensors/gps/fix /vehicle/battery \
  /drivers/joy/joy /safety/estop /control/cmd_vel /drivers/joy/cmd_vel /drivers/keyboard/cmd_vel /drivers/scripted/cmd_vel /drivers/nav/cmd_vel \
  /ego/actuator_cmd /can/tx /can/rx \
  /localization/odom/local /localization/odom/global /localization/gps/odom /localization/gps/fix \
  /tf /tf_static /robot_description /plan /goal_pose /clock
