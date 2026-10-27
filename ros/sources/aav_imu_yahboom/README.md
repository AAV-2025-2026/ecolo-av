# aav_imu_yahboom

`imu_node`, in Rust (rclrs): the Yahboom 10-axis IMU on `/sensors/imu/data_raw` and
`/sensors/imu/mag`. A rewrite of the 2025-26 team's C++ driver (`yahboom_imu_cpp`, now
removed), with its node name, parameters, topics and units. Where it came from, and
how the two compared: [PROVENANCE.md](./PROVENANCE.md).

## Overview

A Rust package. CMake only runs `cargo` and installs the binary, so colcon, `ros2 run`
and launch files treat it like any other node. `aav_sensors`' `sensors.launch.py`
starts it on the car, with `aav_sensors/config/imu.yaml`.

| Crate | What | ROS? |
|---|---|---|
| `crates/yahboom-protocol` | the serial frames, checksums and units (`no_std`, no I/O) | no |
| `crates/imu-node` | the ROS node: reads the port, publishes each sample | yes |

## The frame

The IMU repeats a set of 11-byte frames. The angle frame closes a set.

| Byte | Holds |
|---|---|
| 0 | `0x55`, the header |
| 1 | the type: `0x51` acceleration (±16 g), `0x52` angular rate (±2000 °/s), `0x53` angles (closes a set), `0x54` magnetic field |
| 2 to 9 | four little-endian `i16` values |
| 10 | the checksum: the low byte of the sum of bytes 0 to 9 |

## Interface

### Node: `imu_node`

| Publishes | Type | Notes |
|---|---|---|
| `/sensors/imu/data_raw` | `sensor_msgs/Imu` | gyro (rad/s) and accel (m/s²), no orientation (covariance[0] = -1) |
| `/sensors/imu/mag` | `sensor_msgs/MagneticField` | raw counts, y negated, not tesla |

Subscribes to nothing.

| Parameter | Default | Means |
|---|---|---|
| `port` | `/dev/aav/imu` | the udev name (`tools/udev/99-aav.rules`) |
| `baud_rate` | 115200 | 0 leaves the speed alone (a pseudo-terminal in a test) |
| `frame_id` | `imu_link` | its mount is in `vehicle.yaml` |
| `gyro_stddev` | 0.02 rad/s | published as the covariance diagonal |
| `accel_stddev` | 0.2 m/s² | the same |

All are read-only once the node starts.

### `yahboom-protocol` (library)

| Item | Does |
|---|---|
| `Decoder::push(byte)` | finds frames one byte at a time; after a bad frame it resyncs at the next header inside it |
| `Event::Sample(Sample)` | an angle frame closed a set: publish it |
| `Event::BadChecksum` | a frame failed its checksum and was dropped |
| `Sample` | `accel` (m/s²), `gyro` (rad/s), `mag` (raw counts, y negated) |
| `checksum`, `frame` | one frame, without a decoder |
| `HEADER`, `FRAME_LEN`, `ACCEL`, `GYRO`, `ANGLE`, `MAG` | the constants above |

## Invariants

- `yahboom-protocol` is `no_std` with no ROS and no I/O.
- Its numbers match the C++ driver's bit for bit: `tests/cpp_vectors.rs` feeds the same
  46 chunks of bytes and expects the C++ driver's 46 samples.
- The covariances are never all zero: robot_localization would read that as a perfect
  sensor.
- The magnetometer stays in raw counts on purpose, as the C++ driver had it. So
  `imu_filter_madgwick` runs with `use_mag: false`. Convert and calibrate before using it.
- The topics are absolute: a namespace won't move them.
- The node exits with an error when the port goes away, so a launch `respawn` can bring
  it back. It stops cleanly on Ctrl-C.

## Side Effects

- Opens and reads the serial port. A thread reads and publishes; the main thread spins.
- Logs "Checksum mismatch" for bad frames.
- The IMU should send 200 sets a second. If `ros2 topic hz /sensors/imu/data_raw` shows
  less, set its rate with Yahboom's Windows tool, `MiniMU.exe` (see PROVENANCE.md).

## Verification

```sh
cd ros/sources/aav_imu_yahboom && cargo test -p yahboom-protocol
```

`tools/test.sh` runs this. `pixi run build` builds the node; `pixi run test` runs
everything. On the car: `ros2 topic hz /sensors/imu/data_raw`.
