Steps to set up "ros2_ws" (ros2 workspace for maincar)

1. "ROS2: Humble" only works on Ubuntu 22.04. Ensure you have 22.04 by typing "lsb-version -a" in the terminal
1. After cloning this git repo, use the terminal and navigate to /ros2_ws   
2. while in /ros2_ws, type the command "colcon build" (this will use the "src" folder to create two new folders: "build" and "install")
3. In the new "install" folder, "setup.bash" file. Make sure you source that file within the terminal: $ source /ros2_ws/install/setup.bash

Now you are able to run ros2 nodes!

To do so:

$ ros2 pkg executables [package_name] (this will show all available nodes you can run in the package)
$ ros2 run [package_name] [node_name] (this will execute the desired node in your package)

Note: our package name is called "maincar", for the Ecolo
