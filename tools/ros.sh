#!/usr/bin/env bash
# Run a command with this workspace's ROS packages on the path (sources install/setup.bash).
# The pixi tasks use it: `pixi run turtle` = tools/ros.sh ros2 launch aav_bringup turtle.launch.py
cd "$(dirname "$0")/.."
if [[ ! -f install/setup.bash ]]; then
  echo "Not built yet: run 'pixi run build' first." >&2
  exit 1
fi
source install/setup.bash
exec "$@"
