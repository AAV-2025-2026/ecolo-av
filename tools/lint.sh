#!/usr/bin/env bash
# Check our Python against ROS's own style rules (ament_flake8 and ament_pep257).
# The inherited packages are left out until someone brings them in line.
# Needs a ROS environment: `pixi run lint`, or source ROS first.
set -e
cd "$(dirname "$0")/.."
OURS=(src/aav_bringup src/aav_description src/backends src/drivers src/ego src/localization
      src/mux src/sensors/aav_sensors tools firmware/can firmware/spine/crates/legacy-link/gen_vectors.py
      src/perception/aav_yolo/aav_yolo src/perception/aav_yolo/launch
      src/perception/aav_yolo/test src/perception/aav_yolo/setup.py src/bench/aav_bench
      src/perception/aav_lane_finder
      src/hud/aav_hud src/hud/aav_hud_raylib/launch)
ament_flake8 "${OURS[@]}"
ament_pep257 "${OURS[@]}"
