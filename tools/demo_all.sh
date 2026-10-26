#!/usr/bin/env bash
# Start the whole simulated car on this computer, in one go:
#   Gazebo (the car), the nav screen (RViz), the HUD, and the street-map window.
#
# Everything runs localhost-only (tools/ros.sh --local), so it shares one ROS graph on
# this computer and never reaches the real car on the network.
#
#   pixi run demo                 # windowed
#   pixi run demo fullscreen      # HUD and map full-screen
#   Ctrl-C                        # stops all four
#
# Portable: bash 3.2 (a Mac), no GNU-only flags.
set -u

here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

full=false
[ "${1:-}" = "fullscreen" ] && full=true

pids=""
cleanup() {
  echo
  echo "stopping everything..."
  for p in $pids; do kill "$p" 2>/dev/null; done
  wait 2>/dev/null
}
trap cleanup INT TERM EXIT

start() { "$@" & pids="$pids $!"; }

echo "1/4  Gazebo (the car) — give it ~20s to spawn..."
start tools/ros.sh --local ros2 launch aav_bringup sim.launch.py
sleep 20

echo "2/4  nav screen (RViz: map, costmaps, path, car)..."
start tools/ros.sh --local rviz2 -d ros/bringup/aav_bringup/rviz/drive.rviz

echo "3/4  HUD (in-car screen)..."
start tools/ros.sh --local ros2 launch aav_hud hud.launch.py fullscreen:=$full

echo "4/4  street-map window..."
start tools/ros.sh --local ros2 launch aav_hud map.launch.py fullscreen:=$full

echo
echo "All four started, localhost-only (the real car is untouched)."
echo "Press Ctrl-C here to stop everything."
wait
