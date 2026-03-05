#!/bin/bash

# systemd is meant to execute this .sh script on pi startup

# Flask, Flutter and OSRM need to run in parallel for UI to work.
# these scripts are meant to be executed on startup using a systemd service.

# - Flask is the back-end
# - Flutter is the front-end
# - OSRM is the routing and map data that Flutter uses.

# this script is for the OSRM part.

# creates empty file on desktop for testing
cd /home/aavui/Desktop
touch systemd_osrm_test.txt

# runs OSRM
cd /home/aavui/Downloads/Data

#sudo docker run -t -i -p 5001:5000 -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/ontario-251116.osrm &
docker run --rm -p 5001:5000 \
-v /home/aavui/Downloads/Data:/data \
ghcr.io/project-osrm/osrm-backend \
osrm-routed --algorithm mld /data/ontario-251116.osrm
