# Upgrade each computer: the quick note

One page per kind of computer. The full steps: [Car setup](car-setup.md) and, for the
ESP32, [The ESP32 on the bench](esp32-bench.md). **Back up first, every time.**

## Which computer is which

| Computer | Role | Plugged in | Runs | Its machine file |
|---|---|---|---|---|
| Jetson Orin | `orin` | the lidar (over the network), CAN | the brain: ego, Nav2, localization, perception | `machines/orin.yaml` |
| Pi wired to the ESP32 | `motor_pi` | the ESP32 (UART) | the bridge to the ESP32 | `machines/motor_pi.yaml` |
| IMU and GPS Pi | `localization` | the IMU and the GPS (USB) | only their drivers; the Orin does the maths | `machines/localization.yaml` |
| Camera Pi(s) | `camera_pi` | the two front cameras | video streams, no ROS (Pi OS) | none |
| Dashboard Pi | `dash` | the two screens | the HUD and the map | none |

- **The lidar** is not a computer: it sends its packets straight to the Orin.
- **The ESP32 has no YAML.** Its settings (steering limits, brake positions, speed limits,
  timeouts) are built into its firmware. Its `CONFIG` line shows them all at boot.

## For the ESP32 (a USB cable, from a laptop with the repo)

```sh
pixi run esp tools                       # once per laptop
vendor/cargo-tools/bin/espflash read-flash 0 0x400000 backup-esp32.bin
                                         # the backup of the C++ (4 MB): keep it, never in git
pixi run esp walk                        # talks you through: build, flash, the first check
```

To go back to the C++: `vendor/cargo-tools/bin/espflash write-bin 0 backup-esp32.bin`.
No special build: `pixi run esp flash` builds the car's one.

## For a Pi with Ubuntu (`motor_pi`, `localization`, `dash`)

```sh
# make an image of the SD card first
bash car_setup.sh <role>                 # a dry run: read what it will do
bash car_setup.sh <role> --apply         # do it
```

`motor_pi` won't upgrade until the Rust ESP32 has passed car day's session 6
(`--after-esp32`).

## For a Pi with Pi OS (the camera Pis: they stay on Pi OS)

```sh
# make an image of the SD card first
bash car_setup.sh camera_pi upgrade --apply
bash car_setup.sh camera_pi services --apply
```

## For the Orin

```sh
# a full image first (NVIDIA's backup, from a host PC): car-day.md B3
bash car_setup.sh orin                   # a dry run
bash car_setup.sh orin --apply
```

Later (Day B): the reflash to JetPack 7.2, then `car_setup.sh orin` again. Not yet run
on the real Orin.
