#!/bin/bash

# --- CONFIGURATION ---
EMAIL="your_email@example.com"
MOUNTPOINT="CanalTerris"
SERIAL_PORT="/dev/ttyACM0"
FRAME_ID="gps"

# --- AUTOMATION LOGIC ---

# 1. Start RTK Stream (Background)
echo "Starting RTK Stream (rtk2go)..."
str2str -in ntrip://${EMAIL}:none@rtk2go.com:2101/${MOUNTPOINT} -out tcpsvr://:4000 &
RTK_PID=$!  # Capture the Process ID

# Give it a moment to connect
sleep 2

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down..."

    # Kill the specific str2str process if it's running
    if kill -0 $RTK_PID 2>/dev/null; then
        echo "Stopping RTK Stream (PID $RTK_PID)..."
        kill $RTK_PID
    fi
}

# Trap the "Ctrl+C" signal (SIGINT) and call cleanup
trap cleanup EXIT

# 2. Start ROS 2 Driver (Foreground)
echo "Starting ZED-F9R Driver..."

# Source ROS 2 if not already sourced
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

# Launch the Python node with parameters
python3 gnss_node.py --ros-args -p port:=${SERIAL_PORT} -p frame_id:=${FRAME_ID}
