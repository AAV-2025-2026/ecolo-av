# aav_sensors

The car's sensor drivers: their launch files and configs. Each driver publishes raw
data in its own frame. Nothing here fuses anything, and there is no code of our own:
only launch files, YAML, and the 2024-25 team's camera calibrations.

Run it on the computer the sensors are plugged into. `aav_bringup`'s `car.launch.py`
starts it.

## Overview

| Sensor | Driver (package) | Topic out | Frame |
|---|---|---|---|
| IMU | `imu_node` (`aav_imu_yahboom`), then `imu_filter_madgwick` | `/sensors/imu/data_raw`, then `/sensors/imu/data` | `imu_link` |
| GPS | one of three, picked by `gps_driver` (below) | `/sensors/gps/fix`, and more per driver (below) | `gps_link` |
| Radar | `pcl_pub` (`ti_ros2_driver`), node `radar`, `cfg/base.cfg` | `/sensors/radar/points` | `radar_link` |
| Lidar | `lidar_driver` (`velodyne_driver`), `lidar_cloud` (`velodyne_pointcloud`) | `/sensors/lidar/packets`, `/sensors/lidar/points` | `lidar_link` |
| Battery | `battery_monitor` | `/vehicle/battery` | none |
| Cameras | `usb_cam`, nodes `camera_left`, `camera_right` | `/sensors/camera/front_{left,right}/image_raw`, `camera_info` | `camera_{left,right}_link` |

| `gps_driver` | Driver | Also publishes | Notes |
|---|---|---|---|
| `ublox` (default) | `ublox_gps` (KumarRobotics) | `/sensors/gps/fix_velocity` | a u-blox on `/dev/aav/gps`, taken as it is set up. Tentative until Q18 |
| `nmea` | `nmea_navsat_driver`, node `gps_nmea` | `/sensors/gps/vel`, `/sensors/gps/time_reference` | any NMEA receiver (`gps_nmea.launch.py`) |
| `ublox_dgnss` | `ublox_dgnss` and `ublox_nav_sat_fix_hp` | | a u-blox F9P over libusb, the 2024-25 choice. apt only: the car, not Pixi |

## Interface

### Launch files

| File | Starts | Arguments |
|---|---|---|
| `launch/sensors.launch.py` | IMU, GPS, radar, lidar, battery | `imu` (true), `gps` (true), `radar` (false), `lidar` (false), `lidar_ip` (192.168.1.201), `lidar_port` (2368), `battery` (false), `gps_driver` (ublox), `use_sim_time` |
| `launch/gps_nmea.launch.py` | `nmea_navsat_driver` | `port` (`/dev/aav/gps`), `baud` (9600) |
| `launch/cameras.launch.py` | `usb_cam`, Linux only | `left` (`/dev/aav/camera_left`), `right` (empty: none) |

### Configs

| File | For |
|---|---|
| `config/imu.yaml` | `imu_node`: port `/dev/aav/imu`, 115200 baud, `gyro_stddev` 0.02 rad/s, `accel_stddev` 0.2 m/s² (to measure) |
| `config/imu_filter.yaml` | `imu_filter_madgwick`: `use_mag: false`, `publish_tf: false`, `world_frame: enu` |
| `config/ublox_gps.yaml` | `ublox_gps`: `config_on_startup: false`, 1 Hz |
| `config/cameras/*.ini` | the 2024-25 calibrations (1920 x 1080), from `Carleton-AAV-Capstone/cameras`: see its [PROVENANCE.md](./config/cameras/PROVENANCE.md) |

## Invariants

- Frames (`imu_link`, `gps_link`, `radar_link`, `lidar_link`) come from
  `aav_description`. Run its `description.launch.py` too, or nothing can place these
  readings on the car.
- `imu_filter_madgwick` never publishes TF: `robot_localization` owns the TF tree.
- `use_mag` stays false until the IMU's magnetometer is in tesla and calibrated. So the
  yaw is relative and the EKFs fuse the yaw rate.
- `ublox_gps` changes nothing that lasts on the receiver: nothing is saved to its flash.
- Device paths are the udev names in `tools/udev/99-aav.rules` (`/dev/aav/...`). Pins and
  calibration of the boards stay in the firmware.
- The lidar driver reads only packets from `lidar_ip`. In bench mode, `mock_lidar` (or
  `tools/fake_vlp16.py`) sends to `127.0.0.1:2369` instead.

## Side Effects

- Opens serial ports (IMU, GPS, radar, battery), USB (F9P, cameras) and a UDP port
  (lidar).
- `ublox_gps` sends the receiver RAM-only settings (which messages to send). A power
  cycle clears them.

## Verification

```sh
pixi run build && colcon test --packages-select aav_sensors && colcon test-result --verbose
```

No tests of its own. `aav_bringup`'s `test_car_launch.py` loads `sensors.launch.py`, in
`pixi run test`. On the car:
`pixi run check car`. Untested with the real cameras (Q22) and GPS (Q18).
