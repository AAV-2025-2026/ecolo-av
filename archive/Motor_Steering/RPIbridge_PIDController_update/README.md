# AAV desired build set

Complete the missing Raspberry Pi side pieces for a first speed-control loop:

- `aav_speed_control/wheel_encoder_udp_node.py`
  - receives 4-byte big-endian signed spoke counts over UDP from the Pico/WizNet board
- `aav_speed_control/speed_estimator_node.py`
  - converts counts per window to RPM and speed in m/s
- `aav_speed_control/speed_pid_node.py`
  - closes a first speed loop on the Pi and publishes actuator-friendly Ackermann commands
- `aav_uart_bridge/ackermann_uart_bridge.py`
  - sends framed UART commands to the ESP32 and now publishes a small status topic

## Specs Assumptions, change as needed.

1. The Pico encoder sender sends one signed `int32` every `100 ms` to UDP port `5000`.
2. Encoder pulses per sensor revolution = `8`.
3. `sensor_revs_per_wheel_rev` is `1.0` unless the sensor is on a shaft with gearing.
4. `wheel_diameter_m` is **placeholder** and must be updated to your real wheel diameter.
5. The bridge uses `AckermannDriveStamped.drive.acceleration` as a **raw signed control effort**:
   - `> 0` => throttle magnitude
   - `< 0` => brake magnitude
6. Reverse driving is **not enabled by default** in the PID node. This first build is for forward-speed control and stopping.

## ROS graph

- higher-level nav / teleop publishes desired command to `/cmd_drive`
- PID node subscribes to `/cmd_drive` and measured speed
- PID node publishes actuator-friendly command to `/ackermann_cmd`
- UART bridge subscribes to `/ackermann_cmd` and sends frames to the ESP32