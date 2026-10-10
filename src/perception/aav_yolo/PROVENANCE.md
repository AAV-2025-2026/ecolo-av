# Provenance

Copied on 2026-10-09 from github.com/Carleton-AAV-Capstone/camera_ros2_ws @ default branch (downloaded 2026-10-09), src/yolo_ros2.

Files, unchanged unless listed under Changes:

- `package.xml`
- `setup.cfg`
- `setup.py`
- `yolo_ros2/__init__.py`
- `yolo_ros2/yolo_inference.py`

`training/` came from a second repo: see `training/PROVENANCE.md`.

## Changes

- 2026-10-10: `yolo_ros2/yolo_inference.py` `.warn(` -> `.warning(` (deprecated in Jazzy).
- 2026-10-10: brought in from parked as `aav_yolo` (the name in docs/conventions.md).
  - The package, its folder and its module are renamed; `yolo_inference.py` is now
    `aav_yolo/detector.py`, and its executable `detector`.
  - `detector.py` is rewritten. It keeps the idea: camera images in, YOLO, results out.
    Changed:
    - the model file is a parameter, instead of `~/Yolo/Capstone/runs/detect/train7/weights/best.pt`;
    - it publishes `vision_msgs/Detection2DArray`, instead of only an annotated image;
    - the annotated image is still there, on `detections/image`, but no window opens
      (`cv2.imshow` is gone);
    - the confidence is a parameter, 0.5 by default. The old code used 0.81, tuned for its
      own model;
    - it keeps only the labels asked for, and picks the GPU: CUDA, else Metal, else the CPU.
  - New: `aav_yolo/boxes.py` (the logic, with tests), `launch/detector.launch.py`,
    `test/`, and the missing `resource/aav_yolo` marker.
  - `package.xml` and `setup.py` are rewritten with the real dependencies.
