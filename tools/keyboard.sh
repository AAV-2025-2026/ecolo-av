#!/usr/bin/env bash
# Drive from the keyboard: teleop_twist_keyboard into twist_mux as the "remote" driver
# (priority 90, so the joystick still outranks it). Hold a key to keep moving; let go
# and the car stops within about a second. Keys: i forward, u/o forward left/right,
# , reverse, k stop, q/z faster/slower.
#
# usage: tools/keyboard.sh [--sim]      --sim: use simulation time (Gazebo, replay)
set -euo pipefail
sim=false
if [[ "${1:-}" == "--sim" ]]; then sim=true; fi
exec ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -p stamped:=true -p use_sim_time:=$sim -r cmd_vel:=/cmd_vel/remote
