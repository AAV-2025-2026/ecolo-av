#!/usr/bin/env bash
# Make one of Gazebo's sensors fail on purpose, or mend it (READ-ME-FULL-SIMULATION.md
# step 6). Run it next to `pixi run sim`, on the same ROS domain.
#
# usage: pixi run sim-fault <sensor> <mode>
#   sensor: gps, imu, odom (the wheels), radar, camera (needs `pixi run sim faults:=true`)
#   mode:   ok (mended), stop, freeze, nan (gps, imu, odom), jump (gps only)
#   pixi run sim-fault gps stop      the GPS goes quiet
#   pixi run sim-fault gps ok        back to normal
#
# After a GPS jump, or wheels that disagree with the IMU (odom freeze while the car speeds
# up, brakes or turns), the sensor watchdog holds Nav2 until a person says all is right
# again: `pixi run sim-fault clear`.
set -euo pipefail
if [[ "${1:-}" == clear ]]; then
  exec ros2 service call /safety/sensor_watchdog/clear std_srvs/srv/Trigger
fi
if [[ $# -ne 2 ]]; then
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi
exec ros2 param set /gazebo_adapter "fault.$1" "$2"
