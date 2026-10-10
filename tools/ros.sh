#!/usr/bin/env bash
# Run a command with this workspace's ROS packages on the path (sources install/setup.bash).
# The pixi tasks use it: `pixi run turtle` = tools/ros.sh ros2 launch aav_bringup turtle.launch.py
#
# --local, for the stand-ins (turtle, sim, bench, view): ROS discovery stays on this
# computer, so a pretend car never meets the real one on the same network and domain.
# Other terminals on this computer still see it. To share one on purpose, set
# ROS_AUTOMATIC_DISCOVERY_RANGE yourself: ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET pixi run sim
cd "$(dirname "$0")/.."
if [[ "${1:-}" == "--local" ]]; then
  shift
  if [[ -z "${ROS_AUTOMATIC_DISCOVERY_RANGE:-}" ]]; then
    export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
    unset ROS_STATIC_PEERS  # static peers reach other computers whatever the range says
  fi
fi
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
