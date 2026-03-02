#!/bin/bash

# 1. configure variables
EMAIL="your_email@example.com"
MOUNTPOINT="CanalTerris"
SERIAL_PORT="/dev/zed_f9r"
FRAME_ID="gps"

echo "Starting RTK Stream and GNSS Node"

# 2. Start the rtk stream. It is auto-recovering and will only start when an internet connection is established.
(
    while true; do
        echo "RTK: Waiting for internet connection..."
        while ! ping -c 1 -W 2 8.8.8.8 &> /dev/null; do
            sleep 5
        done

        echo "RTK: Network connected! Starting str2str..."
        str2str -in ntrip://${EMAIL}:none@rtk2go.com:2101/${MOUNTPOINT} -out tcpsvr://:4000

        echo "RTK: str2str crashed or disconnected. Retrying in 5 seconds..."
        sleep 5
    done
) &
RTK_MANAGER_PID=$!

# 3. Setup cleanup
cleanup() {
    echo ""
    echo "Shutting down GPS Stack..."
    kill $RTK_MANAGER_PID 2>/dev/null
    pkill -f str2str 2>/dev/null
}
trap cleanup EXIT

# 4. Start gnss node
echo "Starting Prototype ROS 2 GNSS Node..."

if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

python3 src/gnss_node.py --ros-args -p port:=${SERIAL_PORT} -p frame_id:=${FRAME_ID}
