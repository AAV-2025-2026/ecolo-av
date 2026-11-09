#!/usr/bin/env bash
# The simulator's cameras (ros/sim/aav_sim_cameras): Bevy draws the world from each camera
# on the car, offscreen, and the pictures go out on Gazebo's camera topics.
#
#   pixi run sim-cameras                      # the test world, 10 s: the timing check, no ROS
#   pixi run sim-cameras --save /tmp/pics     # and keep each camera's first picture
#   pixi run sim-cameras --bench 300          # as fast as it can: the most pictures a second
#   pixi run sim-cameras --ros                # publish the camera topics, a scripted drive
#   pixi run sim-cameras --ros --pose truth   # draw where /vehicle/sim/truth says (sim time)
#
# Other arguments go to the program (--seconds S, --cameras a,b, --from X, --speed M/S...).
# --ros needs pixi run build first, and stays on this computer (tools/ros.sh --local):
# it publishes sensor topics, so it must never meet a real car.
#
# Needs a GPU: Metal on a Mac, Vulkan on Linux. Portable: bash 3.2 (a Mac), no GNU-only flags.
set -euo pipefail
cd "$(dirname "$0")/.."

manifest=ros/sim/aav_sim_cameras/Cargo.toml

case "${1:-}" in
  --ros) exec tools/ros.sh --local cargo run --release -q --manifest-path "$manifest" --features ros -- "$@" ;;
  *) exec cargo run --release -q --manifest-path "$manifest" -- "$@" ;;
esac
