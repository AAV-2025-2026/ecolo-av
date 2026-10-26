# tools/udev

Stable names for the car's USB devices: `/dev/aav/<name>` instead of `ttyUSB0`, whose
number changes with plug order. The ROS configs use these names.

## Overview

One rules file, `99-aav.rules`, for udev on each car computer that has devices plugged
in. It is not installed on the car yet: that needs sudo.

## Interface

| Name | Device | Matched by |
|---|---|---|
| `/dev/aav/imu` | Yahboom IMU (CH340) | `1a86:7523` + serial (TODO) |
| `/dev/aav/radar_cmd`, `/dev/aav/radar_data` | TI IWR6843AOP (CP2105) | `10c4:ea70`, interface 00 / 01 |
| `/dev/aav/battery` | Victron VE.Direct cable (FTDI) | `0403:6015` + serial (TODO) |
| `/dev/aav/gps` | any u-blox USB serial port | vendor `1546` |
| (no name) | u-blox F9P over libusb (ublox_dgnss) | `1546:01a9`, group `plugdev` |
| `/dev/aav/camera_left`, `/dev/aav/camera_right` | the cameras (usb_cam) | TODO (Q22) |
| `/dev/aav/gps` | an NMEA GPS (gps_nmea) | TODO (Q18) |

Used by, among others: `ros/sources/aav_sensors/config/imu.yaml`, `ublox_gps.yaml`,
`cameras.launch.py`, `battery_monitor`, `ti_ros2_driver`.

Install:

```sh
sudo cp tools/udev/99-aav.rules /etc/udev/rules.d/ && sudo udevadm control --reload \
  && sudo udevadm trigger
```

Find a device's IDs: `udevadm info -a -n /dev/ttyUSB0 | grep -E 'idVendor|idProduct|serial'`.

## Invariants

- Device names live here; ROS configs say `/dev/aav/...`, never `ttyUSB0`.
- Two devices with the same USB-serial chip differ only by serial number: fill in
  `ATTRS{serial}` for each (team TODO C8).
- The vendor and product IDs are common values, not yet checked on our parts.
- ModemManager must leave GPS ports alone (`ID_MM_DEVICE_IGNORE`).

## Side Effects

Once installed: symlinks in `/dev/aav/`, and mode `0666` on those devices.

## Verification

No automatic test. On the car, after installing: `ls -l /dev/aav/`, then unplug and
replug everything and check the names stay the same. `tools/car_listen.sh` reports the
devices without opening them.
