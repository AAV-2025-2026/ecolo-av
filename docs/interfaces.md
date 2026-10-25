# Interface contract

<!-- Generated from interfaces.yaml by tools/contract_readme.py. Do not edit by hand. -->

Every topic between layers, with its rate and latency budget (proposal section 3.3).
The machine-readable source is [interfaces.yaml](interfaces.yaml); the contract test (T1.6)
reads that file. To change the contract, edit the YAML, then run `pixi run contract-readme`.

| Topic | Type | Transport | From | To | Rate (Hz) | Max latency (ms) | Notes |
|---|---|---|---|---|---|---|---|
| `/drivers/<name>/cmd` | `geometry_msgs/msg/TwistStamped` | ros | each driver | command mux | 20 | 50 |  |
| `/control/cmd` | `geometry_msgs/msg/TwistStamped` | ros | command mux | ego | 20 | 20 |  |
| `/vehicle/ackermann_cmd` | `ackermann_msgs/msg/AckermannDriveStamped` | ros | ego | output mux | 50 | 20 |  |
| `/vehicle/steer_cmd` | CAN frames | can | CAN bridge | spine | 50 | 10 |  |
| `/vehicle/brake_cmd` | CAN frames | can | CAN bridge | spine | 50 | 10 |  |
| `/vehicle/throttle_cmd` | CAN frames | can | CAN bridge | spine | 50 | 10 |  |
| `/vehicle/wheel_speed` | custom (both front wheels) | ros | wheel nodes | CAN bridge | 100 | 10 |  |
| `/vehicle/steer_angle` | custom (Float32 with header) | ros | spine | CAN bridge | 50 | 20 |  |
| `/vehicle/brake_pos` | custom (Float32 with header) | ros | spine | CAN bridge | 50 | 20 |  |
| `/sensors/imu` | `sensor_msgs/msg/Imu` | ros | IMU driver | sensor mux | 100 | 10 |  |
| `/sensors/gps/fix` | `sensor_msgs/msg/NavSatFix` | ros | GPS driver | sensor mux | 10 | 100 |  |
| `/sensors/lidar/points` | `sensor_msgs/msg/PointCloud2` | ros | lidar driver | perception | 10 | 100 |  |
| `/sensors/camera_*/image/compressed` | `sensor_msgs/msg/CompressedImage` | ros | camera Pi | perception | 15 to 30 | 100 |  |
| `/odometry/local` | `nav_msgs/msg/Odometry` | ros | local EKF | drivers, HUD | 50 | 20 |  |
| `/odometry/global` | `nav_msgs/msg/Odometry` | ros | global EKF | drivers, HUD | 20 | 20 |  |
| `/safety/state` | custom | ros | watchdog | HUD, ego | 10 | 100 |  |
| `/power/battery` | `sensor_msgs/msg/BatteryState` | ros | battery monitor | HUD | 1 | 1000 |  |
| `/hw/steer` | custom (goal and state) | ros | laptop or test script | CAN bridge | 50 | 20 | Both directions. Test mode only. |
| `/hw/brake` | custom (goal and state) | ros | laptop or test script | CAN bridge | 50 | 20 | Both directions. Test mode only. |
| `/hw/throttle` | custom (goal and state) | ros | laptop or test script | CAN bridge | 50 | 20 | Both directions. Test mode only. |
