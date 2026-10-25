#!/bin/bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=10
export ROS_LOCALHOST_ONLY=0
source /opt/ros/humble/setup.bash
source ~/Desktop/aav/Camera/install/setup.bash
ros2 run camera_streamer_pkg camera_receiver
