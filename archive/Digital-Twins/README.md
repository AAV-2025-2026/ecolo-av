# Digital-Twins

# Description

Virtual simulation of AAV.

# Tools

1. Ubuntu Distribution 22.0.4
2. CARLA Simulator Version 0.9.16 
3. ROS2 - Humble

# Instructions

## 1. Launch CARLA
  - Open terminal and navigate to directory where Carla was downloaded and extracted (Home directory if in Bay 4)
  - Use command ./CarlaUE4.sh --ros2 to launch the simulator

## 2. Set up ROS2 Environment
  - Open new terminal and navigate to directory where ROS2 was installed
  - Write command source ./install/setup.bash
  - If working in Bay 4, use directory Digital_Twins/ROS2-Brdige-Attempt2

## 3. Spawn Example Vehicle
  - Using the same terminal, type command ros2 launch carla_ros_bridge carla_ros_bridge_with_example_ego_vehicle.launch.py

## 4. Launch rviz
  - In a new terminal, type command ros2 run rviz2 rviz2

