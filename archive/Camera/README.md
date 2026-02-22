# Camera
## Overview
The AAV Camera system handles real-time video streaming and object detection. It consists of three components:

- **MTX Server** — MediaMTX RTSP/WebRTC stream broker running on the camera host
- **Camera Decoder Node** — ROS2 C++ node that pulls RTSP streams via NVDEC hardware decoding and publishes frames
- **Stop Sign Detector Node** — ROS2 C++ node that runs YOLOv8 TensorRT inference on decoded frames and publishes detection events

Camera (CSI) → MediaMTX (RTSP :8554) → NvDecDecoder → ROS2
↓
YoloDetector (TensorRT FP16)
↓
/aav/stop_sign_detected (Bool)
/aav/stop_sign_confidence (Float32)
/aav/stop_sign_detections (Detection2DArray)

---

## Hardware Requirements
- NVIDIA Jetson Orin AGX (JetPack 6.x)
- Raspberry Pi 5 (MTX server)
- CSI cameras (cam1, cam2)
- Network connection between MTX server and Jetson

---

## Software Requirements
- ROS2 Humble
- JetPack 6.x (CUDA 12.x, TensorRT 10.x)
- OpenCV 4.x with GStreamer support
- FFmpeg with `h264_nvv4l2dec` support
- Python 3.10 (for model export only)

Install ROS2 dependencies:
```bash
sudo apt install \
    ros-humble-vision-msgs \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-compressed-image-transport
```

## Repository Structure
camera_decode/
├── include/camera_decode/
│   ├── nvdec_decoder.hpp       # RTSP NVDEC decoder interface
│   └── yolo_detector.hpp       # TensorRT YOLOv8 detector interface
├── src/
│   ├── nvdec_decoder.cpp       # FFmpeg + NVDEC hardware decode
│   ├── yolo_detector.cpp       # TensorRT FP16 inference
│   ├── camera_decoder_node.cpp # ROS2 node: decode + publish image
│   └── stop_sign_node.cpp      # ROS2 node: decode + infer + publish events
├── launch/
│   └── multi_camera.launch.launch.py        # Launch all nodes
└──config/
    └── cameras.yaml            # Camera parameters

engine/
└── tensorRT_engine.py             # Script to convert ONNX to TensorRT engine

model/
├── best.pt                 # YOLOv8 trained weights (PyTorch)
├── best.onnx               # Exported ONNX model
└── best.engine             # TensorRT FP16 engine (generated on Jetson)

## Model Export (One-Time Setup)
The TensorRT engine must be generated on the Jetson - it is hardware-specific and cannot be cross-compiled.
1. Train YOLOv8 model on your dataset (using Ultralytics or custom training)
2. Export to ONNX format:
```bash
python3 engine/tensorRT_engine.py
```
Output: `model/best.onnx`
3. Convert ONNX to TensorRT engine on Jetson:
```bash
/usr/src/tensorrt/bin/trtexec \
    --onnx=/home/aavjetson/Desktop/aav/Camera/model/best.onnx \
    --saveEngine=/home/aavjetson/Desktop/aav/Camera/model/best.engine \
    --fp16 \
    --memPoolSize=workspace:4096M
```
Output: `model/best.engine`

This takes 5–15 minutes on first run. Look for &&&& PASSED at the end.

## Running the System
1. Start the MTX server on the Raspberry Pi:
```bash
/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
```
Note: This should run automatically on boot, it is included in the systemd service file. (Skip this step if the MTX server is already running and streaming the cameras)

2. On the Jetson, source ROS2 and build the workspace:
```bash
source /opt/ros/humble/setup.bash
cd ~/Desktop/aav/Camera
colcon build
source install/setup.bash
```

3. Launch the camera system:
Launch all nodes (recommended):
```bash
ros2 launch camera_decode multi_camera.launch.py
```
This will start both the `camera_decoder_node` and `stop_sign_node` for all configured cameras.

Launch with display (for debugging):
```bash
ros2 launch camera_decode multi_camera.launch.py show_window:=true
```
This will also display the decoded video feed with detection overlays.

Run individual nodes (for testing):
```bash
# Decoder node — cam1
ros2 run camera_decode camera_decoder_node --ros-args \
    -p camera_name:=cam1 \
    -p rtsp_url:=rtsp://192.168.0.64:8554/cam1 \
    -p frame_rate:=30

# Decoder node — cam2
ros2 run camera_decode camera_decoder_node --ros-args \
    -p camera_name:=cam2 \
    -p rtsp_url:=rtsp://192.168.0.64:8554/cam2 \
    -p frame_rate:=30

# Stop sign detector
ros2 run camera_decode stop_sign_node --ros-args \
    -p rtsp_url:=rtsp://192.168.0.64:8554/cam1 \
    -p engine_path:=/home/aavjetson/Desktop/aav/Camera/model/best.engine \
    -p conf_thresh:=0.5 \
    -p show_window:=true
```

## Topics Published
camera_decoder_node publishes:
- `/aav/cam1/image_raw` (sensor_msgs/Image) - Decoded video
- (nth camera will publish to `/aav/cam{n}/image_raw`)

stop_sign_node publishes:
- `/aav/stop_sign_detected` (std_msgs/Bool) - True if stop sign detected
- `/aav/stop_sign_confidence` (std_msgs/Float32) - Confidence score of the detection
- `/aav/stop_sign_detections` (vision_msgs/Detection2DArray) - Bounding boxes and metadata of detected stop signs

## Monitoring and Debugging
Check the ROS2 topics to verify data flow:
```bash
ros2 topic list
```
Check frame rates:
```bash
ros2 topic hz /aav/cam1/image_raw
```
Check RTSP network bandwidth:
```bash
sudo iftop -i eno1 -f "port 8554"
```
Check ROS2 topic bandwidth:
```bash
ros2 topic bw /aav/cam1/image_raw
```
Monitor dectection live:
```bash
ros2 topic echo /aav/stop_sign_detected
ros2 topic echo /aav/stop_sign_confidence
ros2 topic echo /aav/stop_sign_detections
```

## Troubleshooting
OpenCV libopencv conflict warnings at build:
- Safe to ignore — two OpenCV versions coexist on Jetson (ROS2 Humble ships 4.5d, system has 4.8)
