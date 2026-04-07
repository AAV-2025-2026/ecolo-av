# Lane Geometry & Control ROS2 Package

## Overview

This repository contains a ROS2-based implementation of a lane-following control pipeline for an autonomous vehicle system. It bridges the gap between lane perception outputs and vehicle control commands.

## System Architecture

Lane Geometry → Control Interface → Vehicle Commands

## ROS2 Topics

### Subscribed
- /lane_geometry (LaneGeometry)

### Published
- /control_cmd (geometry_msgs/msg/Twist)
- /vehicle_state (std_msgs/msg/String)
- /lane_geometry_status (std_msgs/msg/String)

## Control Output

- linear.x → forward velocity  
- angular.z → steering  

angular.z > 0 → left  
angular.z < 0 → right  

## Vehicle States

- LANE_KEEP  
- LANE_CHANGING  
- LANE_COMMITTED  
- NO_LANE_STOPPING  
- RESUMING  

## Build

mkdir -p ~/lane_geometry_ws/src
cd ~/lane_geometry_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select lane_geometry
source install/setup.bash

## Run

ros2 launch lane_geometry control_test.launch.py mode:=drift_right

## Test Modes

- straight  
- drift_right  
- drift_left  
- sine  
- sharp_curve  
- lane_change_right  
- lane_change_left  
- lane_loss  

## Purpose

Converts lane geometry into actionable vehicle commands in a ROS2 system.
