# IMU - Yahboom 10 Axis
This package provides a ROS2 node to interface with the Yahboom 10 Axis IMU sensor. It reads data from the sensor over a serial connection and publishes it as ROS2 messages.
Data Frequency: 200Hz (Needed for SLAM)

## Overview
The `imu_node` subscribes to the serial port where the Yahboom IMU is connected, parses the incoming data packets, and publishes the accelerometer, gyroscope, and magnetometer data as ROS2 messages. The node is designed to be efficient and runs in a separate thread to continuously read data from the sensor without blocking the main ROS2 event loop.

## Hardware Requirements
- Yahboom 10 Axis IMU sensor
- A computer with ROS2 installed
- Raspberry Pi 4 (Mandatory for this project)

## Software Requirements
- ROS2 Humble
- C++17 compatible compiler
- Serial communication library (e.g., `serial`)

Install ROS2 Dependency:
```bash
sudo apt install ros-humble-serial
```
## Repository Structure
```
yahboom_imu_cpp/
├── CMakeLists.txt          # CMake build configuration
├── package.xml             # ROS2 package manifest
├── src/                    # Source code for the node
|   ├── serial_port.cpp     # Serial port communication implementation
│   └── imu_node.cpp        # Main node implementation
├── include/
│   └── serial_port.hpp     # Header for serial port communication
├── .gitignore              # Git ignore file
├── raw_check.py            # Python script for raw data checking (Testing only)
└── README.md
```

## Building the Package
1. Clone the repository into your ROS2 workspace:
```bash
cd ~/Desktop
git clone https://github.com/AAV-2025-2026/yahboom-IMU.git
```
2. Source your ROS2 workspace and build the package:
```bash
source /opt/ros/humble/setup.bash
cd ~/Desktop/yahboom_imu_cpp
colcon build --packages-select yahboom_imu_cpp
source install/setup.bash
```
3. Run the node:
```bash
ros2 run yahboom_imu_cpp imu_node
```

## Topics Published
- `/imu/data_raw`: Publishes `sensor_msgs/msg/Imu` messages containing raw accelerometer and gyroscope data.
- `/imu/mag`: Publishes `sensor_msgs/msg/MagneticField` messages containing raw magnetometer data.

## Monitoring and Debugging
Check the ROS2 topics to verify that data is being published correctly:
```bash
ros2 topic echo /imu/data_raw
ros2 topic echo /imu/mag
```

Check IMU data frequency:
```bash
ros2 topic hz /imu/data_raw
ros2 topic hz /imu/mag
```

Monitor Data:
```bash
ros2 topic echo /imu/data_raw
ros2 topic echo /imu/mag
```

## Troubleshooting
- Ensure the IMU sensor is properly connected to the Raspberry Pi and the correct serial port is specified in the node parameters.
- Check the baud rate matches the sensor's configuration (default is 115200).
- Use the `raw_check.py` script to verify that raw data is being received correctly from the sensor before running the ROS2 node.
```bash
python3 raw_check.py
```
- If frequency is not 200Hz, the board needs to be configured using the config tool provided by the manufacturer and runs only on windows.

- Config Tool: [click here](https://drive.google.com/file/d/1xRnccb89AZ9f4Y-uGLmZZesawYQcrdst/view?usp=drive_link)
    
    - Download the zip file, extract it, run the file named "MiniMU.exe", connect the board to the computer, and set the data output rate to 200Hz using the the config panel on the task panel **ONLY**.