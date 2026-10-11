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
- 2026-10-10: brought in from parked as `aav_lane_geometry` (the name in
  docs/conventions.md). The package, its CMake project and its message's package are
  renamed, and the scripts import `aav_lane_geometry.msg`.
  - `scripts/control_interface.py` publishes `TwistStamped` on `/cmd_vel/ai`
    (twist_mux's slot for a learned driver), through a new `send()`, instead of `Twist` on
    `/control_cmd`. The lane-keeping logic is unchanged.
  - `launch/control_test.launch.py`: the package name follows.
  - New: `launch/lane_follower.launch.py` (the driver, with fake:=true for a pretend lane).
  - `scripts/control_interface.py`, `scripts/fake_lane_geometry_pub.py`: a quiet Ctrl-C.
    They ignore the second Ctrl-C while cleaning up, catch `ExternalShutdownException`, and
    call `rclpy.try_shutdown()` instead of `rclpy.shutdown()`, which raised when Jazzy's own
    handler had already shut down.
- 2026-10-11: `launch/lane_follower.launch.py`: its docstring names the lane finder
  (`aav_lane_finder`, ours) as what publishes `/lane_geometry`, and `fake:=true` as the
  pretend lane without a camera. The code is unchanged.
