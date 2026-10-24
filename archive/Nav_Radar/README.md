# Radar ROS2 Integration Package

## Overview
This repository contains the **ROS2 integration layer for the radar system**, not the radar implementation itself.

A separate radar repository exists which handles:
- hardware communication
- radar configuration
- low-level signal processing

This repo focuses only on:
- ROS2 communication
- data transformation
- integration with other system components (e.g., navigation)

---

## Purpose

Radar sensors output raw 3D point cloud data which is difficult for downstream systems to use directly.

This package converts:
Raw radar detections → clustered objects → navigation-ready data

---

## Pipeline

Mock / Real Radar → PointCloud2 → Obstacle Extractor → Navigation Output

### Topics

#### Raw Radar Data
- Topic: `/ti_radar_0/ti_mmwave_0`
- Type: `sensor_msgs/msg/PointCloud2`
- Description: Raw radar detections (many points)

#### Processed Object Points
- Topic: `/ti_radar_0/ti_mmwave_0_objects`
- Type: `sensor_msgs/msg/PointCloud2`
- Description: One point per detected object

#### Navigation Output (Main Output)
- Topic: `/navigation_objects`
- Type: `geometry_msgs/msg/PoseArray`
- Description: Clean object positions for navigation

---

## What This Repo Does

- Subscribes to radar point cloud data
- Clusters nearby points into objects
- Publishes object positions in a navigation-friendly format
- Provides mock data for testing without hardware

---

## Mock Testing (No Radar Required)

This package includes a mock radar publisher to simulate real radar data.

### Build

cd ~/radar_ws  
colcon build --packages-select ti_ros2_driver  
source install/setup.bash  

### Run

ros2 launch ti_ros2_driver mock_obstacle_demo.launch.py  

### View Output

ros2 topic echo /navigation_objects  

---

## Example Output

poses:  
- position:  
    x: 2.0  
    y: 1.0  
    z: 0.0  
- position:  
    x: 2.0  
    y: -1.0  
    z: 0.0  

Meaning:
- Objects are 2 meters ahead
- One on the left, one on the right

---

## Coordinate System

- x → forward  
- y → left  
- z → up  

Units: meters

---

## Design Notes

- Uses clustering (distance-based grouping)
- Reduces noise from raw radar points
- Outputs simplified object representation
- Designed for easy integration with navigation systems

---

## Important Clarification

This repository does NOT:
- control radar hardware
- decode radar signals
- configure radar firmware

It ONLY handles ROS2-side integration.

---

## Future Improvements

- Add velocity estimation  
- Improve clustering accuracy  
- Add confidence metrics  
- Integrate with sensor fusion systems  

---

## Summary

This package bridges the gap between radar perception and navigation by converting low-level sensor data into high-level, usable information for autonomous decision-making.
