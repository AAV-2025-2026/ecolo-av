#!/usr/bin/env bash
# Run a command with this workspace's ROS packages on the path (sources install/setup.bash).
# The pixi tasks use it: `pixi run turtle` = tools/ros.sh ros2 launch aav_bringup turtle.launch.py
cd "$(dirname "$0")/.."
if [[ ! -f install/setup.bash ]]; then
  echo "Not built yet: run 'pixi run build' first." >&2
  exit 1
fi
if [[ -n "${CONDA_PREFIX:-}" && -f "$CONDA_PREFIX/setup.bash" ]]; then
  # Under pixi: this environment's ROS, then our packages on top. install/setup.bash would
  # bring back the environment the workspace was built in, so `pixi run -e ml` would run the
  # default environment's Python. Sourcing also restores what macOS strips (see docs/mac.md).
  source "$CONDA_PREFIX/setup.bash"
  source install/local_setup.bash
else
  source install/setup.bash
fi
exec "$@"
