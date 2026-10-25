#!/bin/bash

# systemd is meant to execute this .sh script on pi startup

# Flask, Flutter and OSRM need to run in parallel for UI to work.
# these scripts are meant to be executed on startup using a systemd service.

# - Flask is the back-end
# - Flutter is the front-end
# - OSRM is the routing and map data that Flutter uses.

# this script is for the Flask part.

# creates empty file on desktop for testing
cd /home/aavui/Desktop
touch systemd_flask_test.txt

# runs Flask
source /home/aavui/Desktop/User-Interface/ros2_ws/install/setup.bash
ros2 launch maincar launch.py
