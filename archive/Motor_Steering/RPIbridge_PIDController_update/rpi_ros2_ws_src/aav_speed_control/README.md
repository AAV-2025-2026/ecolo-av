# aav_speed_control
This package adds the Pi-side speed loop pieces.

## Nodes

### `wheel_encoder_udp`
Receives the Pico/WizNet UDP packet:
- payload: 4-byte signed big-endian spoke count
- default bind: `0.0.0.0:5000`
- publishes `/wheel_encoder/count`

### `speed_estimator`
Converts spoke count per fixed window into:
- `/wheel_encoder/rpm`
- `/vehicle/speed_mps`
- `/vehicle/speed_kph`

### `speed_pid`
Subscribes to:
- desired drive command `/cmd_drive`
- measured speed `/vehicle/speed_mps`

Publishes:
- `/ackermann_cmd`

The published `AckermannDriveStamped.drive.acceleration` is a **raw signed control effort** for the bridge:
- positive => throttle magnitude
- negative => brake magnitude
