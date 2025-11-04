### Steps to set up ros2 for UI after installing ros2

1. "ROS2: Humble" only works on Ubuntu 22.04. So make sure you have it by typing "lsb-version -a" in the terminal
1. After cloning this git repo, use the terminal to navigate to /ros2_ws   
2. while in /ros2_ws, type the command "colcon build" (this will compiles our UI nodes found in "src" folder by creating two new folders: "build" and "install")
3. In the new "install" folder, there is a "setup.bash" file. Make sure you source that file within the terminal: <br>**$ source /ros2_ws/install/setup.bash**<br>(Recommended: adding that specific command in "bashrc" will ensure that we don't always have to manually source it each time we open a new terminal. you can use: <br>**$ gedit ~/.bashrc**<br> to open "bashrc").

once /ros2_ws/install/setup.bash is sourced, <br>
Now you are able to run ros2 nodes!

To do so:

**$ ros2 pkg executables [package_name]** (this will show all available nodes you can run in the package) <br>
**$ ros2 run [package_name] [node_name]** (this will execute the desired node in your package)




Note 1: our package name is called "maincar", for the Ecolo <br>
Note 2: where it says [node_name] should actually be [executable_name] since it is possible to have 1 execution that runs 2+ nodes, but currently the executables I made so far is 1 command to execute 1 node. 
