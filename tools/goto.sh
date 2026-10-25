#!/usr/bin/env bash
# Drive to one point and stop there (docs/a-to-b.md; aav_goto's goto_cli).
#
# usage: tools/goto.sh (--lat L --lon L | --x X --y Y | --ahead M [--left M]) [--speed V] [--sim]
#   --sim    Gazebo: this computer only (tools/ros.sh --local), on simulated time
#   neither  the real car: whatever shares this ROS domain, so NOT --local. It asks you to
#            type "goto" first; ego caps the speed at 1 m/s
#
# As tools/actuator_test.sh: only --sim keeps ROS on this computer, and the client itself
# checks /system/source and refuses a mismatch.
set -euo pipefail
cd "$(dirname "$0")/.."
local=()
for a in "$@"; do
  [[ "$a" == --sim ]] && local=(--local)
done
exec tools/ros.sh ${local[@]+"${local[@]}"} ros2 run aav_goto goto "$@"
