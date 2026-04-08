# AAV Lane Detection — Jetson AGX Xavier

Dual IMX219 camera lane detection pipeline for ROS2 Humble on Jetson AGX Xavier.
Cameras stream via MediaMTX RTSP from a Raspberry Pi 5.

---

## What This Repo Contains

```
lane_stitcher/          ← dual camera pipeline
  camera_publisher.py       Opens both cameras via GStreamer/RTSP
  topic_bridge.py           Remaps /aav/cam* → /cam_left /cam_right
  image_stitcher.py         Fisheye undistort + BEV warp + feather blend
  dt_pham_wrapper.py        Improved thresholding + lane fitting
  homography_calibrator.py  Click 4 road points → H matrix
  config/homography.yaml    All camera + canvas config
  launch/stitch_and_detect.launch.py

lane_geometry/          ← geometry + control
  lane_geometry_node.py     Sliding window + polynomial fit + smoothing
  control_interface.py      PID + state machine (v3)
  geometry_logger.py        CSV logger
  msg/LaneGeometry.msg      Custom ROS2 message
  launch/geometry.launch.py
```

---

## Setup (One Time)

```bash
# 1. Clone Dt-Pham repo
git clone https://github.com/Dt-Pham/Advanced-Lane-Lines ~/Advanced-Lane-Lines

# Fix numpy compatibility
sed -i 's/np\.int\b/int/g' ~/Advanced-Lane-Lines/LaneLines.py
sed -i 's/np\.bool\b/bool/g' ~/Advanced-Lane-Lines/LaneLines.py

# 2. Clone this repo and build
cd ~/ros2_ws/src
git clone <THIS_REPO_URL> lane_detection_jetson
cp -r lane_detection_jetson/lane_stitcher .
cp -r lane_detection_jetson/lane_geometry .

cd ~/ros2_ws
colcon build --packages-select lane_stitcher lane_geometry
source install/setup.bash

# 3. Install Python deps
pip3 install "numpy==1.26.4" opencv-python-headless pyyaml scipy matplotlib
```

---

## Run

```bash
# Terminal 1 — cameras + stitcher + lane detection
export LANE_REPO=~/Advanced-Lane-Lines
ros2 launch lane_stitcher stitch_and_detect.launch.py

# Terminal 2 — geometry + control + logging
ros2 launch lane_geometry geometry.launch.py \
    metres_per_pixel_x:=0.020 \
    metres_per_pixel_y:=0.025 \
    base_speed:=2.0
```

## Monitor

```bash
ros2 topic echo /vehicle_state
ros2 topic echo /lane_geometry_status
```

---

## One-Time Road Calibration

```bash
# Calibrate homography — run on road, click 4 lane points
ros2 run lane_stitcher homography_calibrator --ros-args -p camera:=left
ros2 run lane_stitcher homography_calibrator --ros-args -p camera:=right
# Paste H matrices into config/homography.yaml then rebuild
```

---

## State Machine

```
LANE_KEEP ──► NO_LANE_STOPPING ──► RESUMING ──► LANE_KEEP
    │                                                 │
    └──► LANE_CHANGING ──► LANE_COMMITTED ────────────┘
```

---

*For dashcam/video testing on laptop see: AAV Lane Detection — Laptop repo*
