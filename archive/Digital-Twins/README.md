# Digital-Twins

# Description

Virtual simulation of AAV.

# Tools

1. Ubuntu Distribution 22.0.4
2. Packaged CARLA Simulator Version 0.9.15
3. ROS2 - Humble
4. Source CARLA Simulator Version 0.9.15
5. Unreal Engine 4.26

# Instructions

## 1. Launch CARLA
  - Open terminal and navigate to directory where Carla was downloaded and extracted (Digital_Twins/CARLA/CARLA_0.9.15 directory on Desktop in Bay 4)
  - cd /media/aav/DataDrive1/Digital_Twins/CARLA/CARLA_0.9.15
  - Use command ./CarlaUE4.sh to launch the simulator

## 2. Set up ROS2 Environment
  - Open new terminal and navigate to directory where ROS2 was installed (media/aav/DataDrive1/Digital_Twins/ros-bridge on Desktop in Bay 4)
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

## 6. Open Simulated P7 Environment
  - Have CARLA running on a separate terminal
  - Open new terminal and navigate to cd Digital_Twins/CARLA/CARLA_0.9.15/PythonAPI/util
  - Run this command python3 config.py --osm-path=/home/aav/Digital_Twins/p7.osm
  - Zoom into environment using W on key board and mouse to view the map

## 7. Important Notes
  - There are a series of text files in the Digital_Twins and DigitalTwins folders in media/aav/DataDrive1 detailing instructions for how to launch sensors and view them in Rviz, controlling simulation + physical vehicle with joystick, and how to load map files into CARLA.

  - Files:
  - important notes.txt
  - Carla-ROS-Commands.txt

    

