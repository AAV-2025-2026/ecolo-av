#!/bin/bash

# 1. configure variables
EMAIL="your_email@example.com"
MOUNTPOINT="CanalTerris"
SERIAL_PORT="/dev/zed_f9r"
FRAME_ID="gps"
ENABLE_SELF_TEST="false"
ENABLE_RTK="false"
echo "Starting ROS 2 GNSS Node..."

# 2. Start the rtk stream ONLY if enabled
if [ "$ENABLE_RTK" = "true" ]; then
    echo "RTK: Stream enabled. Starting background manager..."
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
else
    echo "RTK: Stream disabled via toggle."
    RTK_MANAGER_PID=""
fi

# 3. Setup cleanup
cleanup() {
    echo ""
    echo "Shutting down GPS Stack..."
    # Only try to kill the manager if we actually started it
    if [ -n "$RTK_MANAGER_PID" ]; then
        kill $RTK_MANAGER_PID 2>/dev/null
    fi
    pkill -f str2str 2>/dev/null
}
trap cleanup EXIT

# 4. Start gnss node
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

python3 src/gnss_node.py --ros-args \
    -p port:=${SERIAL_PORT} \
    -p frame_id:=${FRAME_ID} \
    -p enable_self_test:=${ENABLE_SELF_TEST} \
    -p enable_rtk:=${ENABLE_RTK}