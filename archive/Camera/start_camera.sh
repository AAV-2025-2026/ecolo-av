#!/bin/bash
cd ~/Desktop/Camera
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=10
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch camera_streamer_pkg usb_camera_gstreamer.launch.py
