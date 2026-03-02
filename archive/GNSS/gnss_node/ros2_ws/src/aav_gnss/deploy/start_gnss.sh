#!/bin/bash

# 1. Source the main ROS 2 installation
source /opt/ros/humble/setup.bash

# 2. IMPORTANT: UPDATE USERNAME AND WORKSPACE TO PROPER VALUES
source /home/<USERNAME>/<WORKSPACE>/install/setup.bash

# 3. Launch the GNSS node and pass the real email argument
ros2 launch aav_gnss gnss.launch.py