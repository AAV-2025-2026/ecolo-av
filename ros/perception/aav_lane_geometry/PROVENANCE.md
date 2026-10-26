# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/Lane_Detection_ROS2 @ main (345285860e), src/lane_geometry.

Files, unchanged unless listed under Changes:

- `CMakeLists.txt`
- `msg/LaneGeometry.msg`
- `package.xml`
- `scripts/control_interface.py`
- `scripts/fake_lane_geometry_pub.py`

## Changes

- 2026-10-10: `CMakeLists.txt` `cmake_minimum_required` 3.8 -> 3.10;
  `scripts/control_interface.py` `.warn(` -> `.warning(` (deprecated in Jazzy).
- 2026-10-10: brought in from parked as `aav_lane_geometry` (the name in
  docs/conventions.md). The package, its CMake project and its message's package are
  renamed, and the scripts import `aav_lane_geometry.msg`.
  - `scripts/control_interface.py` publishes `TwistStamped` on `/cmd_vel/ai`
    (twist_mux's slot for a learned driver), through a new `send()`, instead of `Twist` on
    `/control_cmd`. The lane-keeping logic is unchanged.
  - `launch/control_test.launch.py` (since removed): the package name follows.
  - New: `launch/lane_follower.launch.py` (the driver, with fake:=true for a pretend lane).
  - `scripts/control_interface.py`, `scripts/fake_lane_geometry_pub.py`: a quiet Ctrl-C.
    They ignore the second Ctrl-C while cleaning up, catch `ExternalShutdownException`, and
    call `rclpy.try_shutdown()` instead of `rclpy.shutdown()`, which raised when Jazzy's own
    handler had already shut down.
- 2026-10-11: `launch/lane_follower.launch.py`: its docstring names the lane finder
  (`aav_lane_finder`, ours) as what publishes `/lane_geometry`, and `fake:=true` as the
  pretend lane without a camera. The code is unchanged.

## Topic names by area (2026-10-15)

The topics move to their areas (docs/naming.md, Decided by Ben on 15 Oct). Only names
change, never the logic:

- `scripts/control_interface.py`: `/lane_geometry` -> `/perception/lane/geometry`,
  `/cmd_vel/ai` -> `/drivers/ai/cmd_vel`, `/lane_geometry_status` ->
  `/drivers/ai/lane_status`, `/vehicle_state` -> `/drivers/ai/lane_state` (control_interface
  is the AI slot's driver, so what it publishes goes under `/drivers/ai/`).
- `scripts/fake_lane_geometry_pub.py`, `scripts/geometry_logger.py` (since removed),
  `launch/lane_follower.launch.py`: `/lane_geometry` -> `/perception/lane/geometry`.
- 25 Oct 2026: `launch/control_test.launch.py` starts both scripts with
  `prefix='python3'`, as `lane_follower.launch.py` does (on a Mac, `/usr/bin/env` drops
  the library path their messages need: `docs/mac.md`). `scripts/geometry_logger.py`
  calls `rclpy.try_shutdown()`, as the other two scripts do, so a second Ctrl-C under
  launch doesn't raise.
- 26 Oct 2026: removed `launch/control_test.launch.py` and `scripts/geometry_logger.py`
  (and its line in `CMakeLists.txt`): 2025-26 test aids that nothing started.
  `lane_follower.launch.py fake:=true` does what the test launch did. The naming and
  cleanup audit, `docs/designs/2026-10-26_naming-and-cleanup.md`.
