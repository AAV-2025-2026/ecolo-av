#!/bin/bash

# systemd is meant to execute this .sh script on pi startup

# Flask, Flutter and OSRM need to run in parallel for UI to work.
# these scripts are meant to be executed on startup using a systemd service.

# - Flask is the back-end
# - Flutter is the front-end
# - OSRM is the routing and map data that Flutter uses.


# this script is for Flutter's part.

# creates empty file on desktop for testing
cd /home/aavui/Desktop
touch systemd_flutter_test.txt

# fix for Flutter on some Linux environments
export GDK_BACKEND=x11

# go to flutter app location
cd /home/aavui/Desktop/User-Interface/flutter_pi

# run flutter
/home/aavui/flutter/bin/flutter run

