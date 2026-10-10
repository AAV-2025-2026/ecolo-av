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

## Known issues (not changed)

- `/imu/mag` is in raw counts (with y negated), not tesla, so `imu_filter_madgwick`
  runs with `use_mag: false` and yaw drifts. Convert to tesla and calibrate before
  using the magnetometer.
- The port defaults to `/dev/ttyUSB0`, like the radar and the battery monitor. Use the
  udev names in `tools/udev/99-aav.rules`.
- Topics are absolute (`/imu/data_raw`, `/imu/mag`), so a namespace won't move them.
