# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/yahboom-IMU @ main (95469f1a63), /.

Files, unchanged unless listed under Changes:

- `CMakeLists.txt`
- `README.md`
- `include/yahboom_imu_cpp/serial_port.hpp`
- `launch/imu.launch.py`
- `package.xml`
- `raw_check.py`
- `src/imu_node.cpp`
- `src/serial_port.cpp`

## Changes

- `src/imu_node.cpp`: new parameters `gyro_stddev` (0.02 rad/s) and `accel_stddev`
  (0.2 m/s^2), published as the diagonal of `angular_velocity_covariance` and
  `linear_acceleration_covariance`. They were all zero, which robot_localization
  reads as a perfect sensor.

- `src/serial_port.cpp`: `B921600` is behind `#ifdef B921600`, so the package
  compiles on macOS, whose `termios.h` stops at `B230400` (2026-10-10).

- `src/imu_node.cpp`: the "Opened ... baud" log prints the baud as an `int` with `%d`.
  `%ld` with an `int64_t` is wrong where `long` isn't 64 bits: macOS warned, and
  32-bit Linux prints garbage (2026-10-10).

### 2026-10-10: lint and Jazzy fixes

- `include/`, `src/`: reformatted with `ament_uncrustify --reformat` (whitespace only).
- `src/imu_node.cpp`: the `port` parameter defaults to `/dev/aav/imu` (the udev name).
- `CMakeLists.txt`: `cmake_minimum_required` 3.8 -> 3.10 (CMake 4 warns below 3.10);
  `install (` -> `install(` for lint_cmake.
- `launch/imu.launch.py`: port `/dev/aav/imu`; two blank lines and a final newline.
- `raw_check.py`: dropped the unused `import time`; the port is an optional argument,
  default `/dev/aav/imu`.
- `package.xml`: exec_depend `launch` and `launch_ros`.
- `README.md`: ROS 2 Jazzy, not Humble; no `ros-humble-serial` (the code uses termios).
- Now `colcon test` passes: it failed 13 lint checks before.

## Known issues (not changed)

- `/imu/mag` is in raw counts (with y negated), not tesla, so `imu_filter_madgwick`
  runs with `use_mag: false` and yaw drifts. Convert to tesla and calibrate before
  using the magnetometer.
- Topics are absolute (`/imu/data_raw`, `/imu/mag`), so a namespace won't move them.
