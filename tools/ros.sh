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
#
# ROS's messages go through Cyclone DDS, the team's choice (Ben, 23 Oct; pixi.toml sets it
# too). On a Mac beside Gazebo, Fast DDS delivered some messages up to 0.48 s late while
# their publisher was on time; Cyclone, never over 0.05 s (22 Oct, docs/mac.md).
# AAV_RMW=fastdds goes back to Fast DDS for one run. Every program that talks to it needs
# the same: AAV_RMW=fastdds pixi run sim, and in the other terminal too.
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
case "${AAV_RMW:-}" in
  ""|cyclone) export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ;;
  fastdds) export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ;;
  *) echo "AAV_RMW=$AAV_RMW: use cyclone or fastdds" >&2; exit 2 ;;
esac
exec "$@"
