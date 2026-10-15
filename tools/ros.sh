#!/usr/bin/env bash
# Run a command with this workspace's ROS packages on the path (sources install/setup.bash).
# The pixi tasks use it: `pixi run turtle` = tools/ros.sh ros2 launch aav_bringup turtle.launch.py
#
# --local, for the stand-ins (turtle, sim, bench, view): ROS discovery stays on this
# computer, so a pretend car never meets the real one on the same network and domain.
# Other terminals on this computer still see it. To share one on purpose:
# AAV_DISCOVERY=SUBNET pixi run sim
# Not ROS_AUTOMATIC_DISCOVERY_RANGE itself: pixi's activation (ros_environment) already
# sets it to SUBNET before this script runs, so "keep the user's value" kept SUBNET and
# --local never was local (found 15 Oct, when a network blocked multicast).
cd "$(dirname "$0")/.."
local=false
if [[ "${1:-}" == "--local" ]]; then
  shift
  local=true
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
if [[ "$local" == true ]]; then
  # After sourcing: ROS's own setup scripts may set the range too.
  export ROS_AUTOMATIC_DISCOVERY_RANGE="${AAV_DISCOVERY:-LOCALHOST}"
  if [[ "$ROS_AUTOMATIC_DISCOVERY_RANGE" == LOCALHOST ]]; then
    unset ROS_STATIC_PEERS  # static peers reach other computers whatever the range says
  fi
fi
exec "$@"
