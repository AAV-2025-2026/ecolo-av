# Platforms: Ubuntu, the car's computers, networking

Every computer runs ROS 2 Jazzy. On the car's computers that means Ubuntu 24.04 with the
official packages. On a Mac or any other Linux, use Pixi: see [Run it](run.md).

## Which computer gets Jazzy how

| Computer | OS | Jazzy from |
|---|---|---|
| Jetson AGX Orin | JetPack 7.2 (Ubuntu 24.04) | apt. JetPack 6 is Ubuntu 22.04, so reflash first, after a backup. |
| Raspberry Pi 4 or 5 | Ubuntu 24.04 Server (arm64) | apt |
| Linux laptop | Ubuntu 24.04 | apt, or Pixi |
| Mac | macOS 14 or newer | Pixi: [Your Mac](mac.md) |
| oirp-spss | AlmaLinux 9 | Pixi, with no admin rights |
| Windows | Windows 10 or 11 | WSL2 with Ubuntu 24.04 |

Every computer on one ROS network must run the same release: Humble and Jazzy don't mix.

## Ubuntu 24.04: install Jazzy

The official steps, from docs.ros.org ("Ubuntu (deb packages)"):

```bash
sudo apt install software-properties-common curl
sudo add-apt-repository universe
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update && sudo apt full-upgrade -y
sudo apt install ros-jazzy-desktop ros-dev-tools     # ros-jazzy-ros-base on the Pis and the Orin
sudo rosdep init && rosdep update
```

Add `source /opt/ros/jazzy/setup.bash` to `~/.bashrc`. To check it, run
`ros2 run demo_nodes_cpp talker` in one terminal and `ros2 run demo_nodes_py listener` in
another.

## Ubuntu: build this workspace

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -y    # every stock package we use
colcon build --symlink-install
source install/setup.bash                          # in every new terminal
```

- `--symlink-install` links the Python files and configs instead of copying them, so an
  edit only needs a relaunch. C++ and message changes still need a rebuild.
- `colcon build --packages-select aav_ego` builds just one package.
- After switching branches, delete `build/`, `install/` and `log/`, and rebuild.

## Networking: many computers, one ROS graph

ROS 2 has no master. Nodes find each other by multicast on the local network.

| # | Rule | Why |
|---|---|---|
| 1 | The same `ROS_DOMAIN_ID` (1–101) in every machine's `~/.bashrc` | the 2025-26 dashboard used 10 and its UI used 0, so they never met |
| 2 | One network that allows multicast, such as the car's own router | campus WiFi often blocks it; then list the computers in `ROS_STATIC_PEERS` |
| 3 | Keep `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` | set it to `LOCALHOST` to keep a laptop's experiments off the car |
| 4 | One middleware everywhere: Fast DDS, the default | different middlewares may not talk to each other |
| 5 | Clocks in sync: chrony, with the Orin as the time server | TF and the EKFs reject messages from a wrong clock |
| 6 | Virtual machines on bridged networking, not NAT | so the VM gets its own address on the car's network |

`ros2 doctor --report` and `ros2 multicast send` / `receive` diagnose most problems.

## On the car: what runs where

The design puts everything on the Orin. Until the spine exists, the Motor Pi still talks
to today's ESP32. The files in `src/aav_bringup/config/machines/` say what runs where:

| Machine file | Runs |
|---|---|
| `orin.yaml` | description, mux, ego, scripted, the IMU and GPS drivers, localization, Nav2, the legacy encoder listener, Foxglove |
| `motor_pi.yaml` | `legacy_uart_bridge` only: it's the computer wired to the ESP32 |
| `laptop.yaml` | the joystick, on the safety driver's laptop |
| `all.yaml` | everything on one computer, for the bench |

On each computer, run `ros2 launch aav_bringup car.launch.py machine:=<its file>`.

!!! warning "The first hardware test"
  Wheels off the ground, the e-stop in reach, and a low speed limit in `ego.yaml`. Check
  that positive steering turns left, that the throttle goes the right way, and that the
  car stops when you release the deadman and when you kill the bridge. Today's firmware
  fails the last one: see [Firmware](firmware.md).

## Moving the Orin to JetPack 7.2

It's a reflash, not an upgrade:
1. **Back up** `/home/aavjetson` and every workspace first. It holds the only copy of the
   2025-26 YOLO detector and camera/LiDAR setup. Better still, take a full image with
   `l4t_backup_restore.sh`.
2. **Check** `cat /etc/nv_tegra_release` and the module's part number. Module
   699-13701-0005-502 has a reported flashing problem; -501 works.
3. **Flash** with SDK Manager from an Ubuntu 22.04 or 24.04 x86 PC, or use the dev kit's
   USB installer.
4. **Install Jazzy** as above. Move the Pis to Ubuntu 24.04 at the same time.

The reasons and the risks: [history/conversation.md](history/conversation.md#so-we-can-upgrade-the-orin-to-jazzy-jetpack-72-test-it-before-committing).
