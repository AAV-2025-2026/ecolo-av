## Steps to set up ros2 for UI after installing ros2

What you have after cloning the repo:
- **User-Interface**
  - **ros2_ws**
    - src
      - maincar (package name) 
   
<br>What you ultimately want on your local machine:
- **User-Interface**
  - **ros2_ws**
    - src
      - maincar (package name)  
    - install
    - build
<br>
We always have to write ros2 code in the "src" folder, and each time we want to test it, we have to always build/compile it by creating the "install" and "build" folder, which is automatically done by using a command called "colcon build".<br>
<br>Here's how we do that:<br><br>

1. "ROS2: Humble" only works on Ubuntu 22.04, so make sure you have it by typing "lsb-version -a" in the terminal
1. After cloning this git repo, use the terminal to navigate to /ros2_ws   
2. while in /ros2_ws, type the command "colcon build" (this will compile the code for the UI nodes found in "src" folder by creating two new folders: "build" and "install")
3. In the new "install" folder, there is a "setup.bash" file. Make sure you source that file within the terminal: <br>**$ source /ros2_ws/install/setup.bash**<br>(Recommended: adding that specific command in "bashrc" will ensure that we don't always have to manually source it each time we open a new terminal. you can use: <br>**$ gedit ~/.bashrc**<br> to open "bashrc").<br>

---

once /ros2_ws/install/setup.bash is sourced, <br>
now you are able to run ros2 nodes!<br>

To do so:<br>

The following command shows all available nodes you can run in the package: <br>
**$ ros2 pkg executables [package_name]**<br>

The following command will execute the desired node:<br>
**$ ros2 run [package_name] [node_name]**<br> 

Example:<br>
(in terminal 1): **$ ros2 run maincar ui_flask**<br>
(in terminal 2): **$ ros2 run maincar ui_test_publish**<br>

Result of the example:<br>
the node "ui_test_publish" constantly sends a randomized Float32 value to the topic called "/mock_speed"
the node "ui_flask" is actively keeps the flask server open and constantly fetches Float32 data from the topic called "/mock_speed"

## Notes
Note 1: Our package name is called "maincar" for the Ecolo. When we get to work on the XO, we could call it the "xo" package <br><br>
Note 2: Where it says [node_name] should actually be [executable_name] since it is possible to have 1 execution that runs 2+ nodes, but currently the executables I made so far involve 1 command per 1 node (1 terminal per 1 node). This means eventually it will be possible to eventually have 1 terminal to run 2+ nodes.<br><br>
Note 3: You can use the following command (a ros2 tool) to see a visual representation of active nodes:<br> **$ rqt_graph**<br><br>
