#!/usr/bin/env bash
# Drive a recorded drive again: play the bag's /cmd_vel (what ego obeyed last time)
# into twist_mux as /cmd_vel/replay (priority 40). The joystick still outranks it and
# /estop still stops it. Open loop: the car will drift from the original path.
#
# usage: tools/replay_commands.sh <bag directory> [extra ros2 bag play args, e.g. --rate 0.5]
#
# ego and twist_mux judge freshness by arrival time, so the bag's old stamps are fine.
set -euo pipefail
bag="${1:?usage: tools/replay_commands.sh <bag> [ros2 bag play args]}"
shift
exec ros2 bag play "$bag" --topics /cmd_vel --remap /cmd_vel:=/cmd_vel/replay "$@"
