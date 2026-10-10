# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/Lane_Detection_ROS2 @ main (345285860e), src/lane_geometry.

Files, unchanged unless listed under Changes:

- `CMakeLists.txt`
- `launch/control_test.launch.py`
- `msg/LaneGeometry.msg`
- `package.xml`
- `scripts/control_interface.py`
- `scripts/fake_lane_geometry_pub.py`
- `scripts/geometry_logger.py`

## Changes

- 2026-10-10: `CMakeLists.txt` `cmake_minimum_required` 3.8 -> 3.10;
  `scripts/control_interface.py` `.warn(` -> `.warning(` (deprecated in Jazzy).
