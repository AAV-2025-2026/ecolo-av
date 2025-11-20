# Digital-Twins

# Description

Virtual simulation of AAV.

# Tools

1. Ubuntu Distribution 22.0.4
2. CARLA Simulator Version 0.9.15
3. ROS2 - Humble

# Instructions

## 1. Launch CARLA
  - Open terminal and navigate to directory where Carla was downloaded and extracted (Digital_Twins/CARLA/CARLA_0.9.15 directory on Desktop in Bay 4)
  - Use command ./CarlaUE4.sh --ros2 to launch the simulator

## 2. Set up ROS2 Environment
  - Open new terminal and navigate to directory where ROS2 was installed (Digital_Twins/CARLA-0.9.15-ROS2-Bridge on Desktop in Bay 4)
  - Write command source ./install/setup.bash
    
## 3. Spawn Example Vehicle
  - Using the same terminal, type command ros2 launch carla_ros_bridge carla_ros_bridge_with_example_ego_vehicle.launch.py

## 4. Control using ROS2 Commands
  - Open new terminal and go to directory where ROS2 environment is
  - Run python script using ros2 run my_vehicle_pkg ego_control

## 5. Launch rviz
  - In a new terminal, type command rviz2
  - Add Image, Topic rgb_view/Image/Camera
  - Add PointCloud2, Topic lidar/PointCloud2
  - Add TF, Topic odometry/Odometry

    

