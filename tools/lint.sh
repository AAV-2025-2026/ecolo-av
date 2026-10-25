#!/usr/bin/env bash
# Check our Python against ROS's own style rules (ament_flake8 and ament_pep257).
# The inherited packages are left out until someone brings them in line.
# Needs a ROS environment: `pixi run lint`, or source ROS first.
set -e
cd "$(dirname "$0")/.."
OURS=(src/aav_bringup src/aav_description src/backends src/drivers src/ego src/localization
      src/mux src/safety src/sensors/aav_sensors src/sensors/aav_camera_stream tools firmware/can firmware/spine/crates/legacy-link/gen_vectors.py
      src/perception/aav_detector/aav_detector src/perception/aav_detector/launch
      src/perception/aav_detector/test src/perception/aav_detector/setup.py src/bench/aav_bench
      src/perception/aav_lane_finder
      src/hud/aav_hud src/hud/aav_hud_raylib/launch src/perception/aav_radar_clusters/launch
      src/perception/aav_radar_clusters/test)
ament_flake8 "${OURS[@]}"
ament_pep257 "${OURS[@]}"
