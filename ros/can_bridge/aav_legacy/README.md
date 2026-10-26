# aav_legacy

## Overview

The interim backend for the 2025-26 hardware, until the CAN spine drives the car.
`legacy_uart_bridge` drives the ESP32 over UART from ego's commands. `encoder_udp`
turns the 2025-26 UDP wheel encoder into `/vehicle/odom`. `car.launch.py` starts the
bridge with `actuators:=uart` (today's wiring), on the Motor Pi.

**Read docs/firmware.md before driving.** The ESP32's 2025-26 C++ firmware has no
command timeout: if the bridge dies, the last throttle stays on.

## Interface

### Executables

| Executable | Runs on | Does |
|---|---|---|
| `legacy_uart_bridge` | the Pi wired to the ESP32 (`/dev/ttyAMA0`) | commands to serial frames; with `uplink`, the ESP32's frames back |
| `encoder_udp` | the Motor Pi (the encoder sends only there) | UDP spoke counts to speed. Off since 23 Oct: the wheels are on CAN |

### `legacy_uart_bridge` topics

| Direction | Topic | Type |
|---|---|---|
| sub | `/control/car/actuator_cmd` | ackermann_msgs/AckermannDriveStamped |
| sub | `/control/car/heartbeat` | aav_interfaces/Heartbeat |
| sub | `/safety/estop` | std_msgs/Bool |
| pub | `/system/source` (latched, REAL) | aav_interfaces/DataSource |
| pub, `uplink` only | `/vehicle/status` (10 Hz) | aav_interfaces/VehicleStatus |
| pub, `uplink` only | `/vehicle/steering`, `/vehicle/brake` | aav_interfaces/ActuatorState |
| pub, `uplink` only | `/vehicle/rc` | aav_interfaces/RcSticks |

`encoder_udp` publishes `/vehicle/odom` (nav_msgs/Odometry, forward speed only, in
`base_link`).

### Parameters (`config/legacy.yaml`)

| Node | Name | Value | Unit |
|---|---|---|---|
| bridge | `port`, `baud` | `/dev/ttyAMA0`, 115200 | |
| bridge | `rate_hz`, `cmd_timeout` | 50.0, 0.3 | Hz, s |
| bridge | `frame_version` | 1 today (C++ firmware); 2 for the Rust firmware | |
| bridge | `uplink`, `uplink_timeout` | false, 0.2 | s |
| bridge | `max_steering_angle` | from `vehicle.yaml` | rad |
| bridge | `steering_sign` | -1.0 (TODO check) | |
| bridge | `full_throttle_speed`, `stop_speed` | 3.0, 0.05 | m/s |
| bridge | `hold_brake`, `stop_brake` | 0.3, 1.0 | 0..1 |
| encoder | `port`, `bind_address` | 10111, 0.0.0.0 | |
| encoder | `wheel_diameter`, `counts_per_rev` | from `vehicle.yaml` | m, counts |
| encoder | `window_s`, `timeout_s` | 0.5, 0.3 | s |
| encoder | `speed_variance` (on `/vehicle/odom`) | 0.05 | (m/s)² |

### Launch

`legacy.launch.py [uart:=true] [encoder:=true] [rc:=true]`: the bridge, the encoder,
and `aav_rc`'s `rc_driver` beside the bridge.

### Modules

| Module | ROS? | Holds |
|---|---|---|
| `legacy_uart_bridge.py`, `encoder_udp.py` | yes | the nodes |
| `legacy_protocol.py` | no | the frames: `pack_frame` (v1, 13 bytes), `pack_frame_v2` (17 bytes), `unpack_uplink` (35 bytes), `UplinkParser`, `to_legacy`, `stop_command`, `EncoderSpeed` |
| `uart_relay.py` | no | `Relay`: what to write each tick |
| `uplink_reader.py` | no | `UplinkReader`, `status_fields`, `steering_state`, `brake_state`, `rc_fields` |

## Invariants

- Reads only `/control/car/actuator_cmd` (the output mux, target car), never
  `/ego/actuator_cmd`.
- A stale command (`cmd_timeout`) or an e-stop sends brake frames: throttle 0, brake full.
- The bridge only relays the Orin's heartbeat counter, never makes one up. The Rust
  ESP32 firmware brakes when it hasn't changed for 100 ms.
- Version 2 frames and the uplink use CRC-8/SAE-J1850, as `aav.dbc`. Both sides check
  `firmware/spine/crates/legacy-link/vectors.json`.
- ROS's steering is + left; `steering_sign` flips it for the ESP32.
- `encoder_udp` stops publishing after `timeout_s` of silence, rather than say 0 m/s.
- Never run `encoder_udp` where the `spine` part runs: two `/vehicle/odom` publishers
  stop the output mux.
- The logic modules have no ROS imports.

## Side Effects

- Writes and reads the serial port (pyserial).
- `encoder_udp` binds a UDP socket on port 10111.
- Drives the real car's throttle, brake and steering through the ESP32.

## Verification

```sh
pixi run build && colcon test --packages-select aav_legacy && colcon test-result --verbose
```

`pixi run test` runs every package's tests.
