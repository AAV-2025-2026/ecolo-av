# Platforms: installing Jazzy, building, networking

Everything targets **ROS 2 Jazzy** (supported until May 2029). Jazzy's Tier 1 platform is
**Ubuntu 24.04**, on both x86-64 and 64-bit ARM. Every computer that joins the car's ROS
network must run the same release; mixing Humble and Jazzy is unsupported.

| Computer | OS | How it gets Jazzy |
|---|---|---|
| Jetson AGX Orin | JetPack 7.2 (Ubuntu 24.04) | apt, as on Ubuntu. JetPack 6 is Ubuntu 22.04: reflash first, after a backup (see below). |
| Raspberry Pi 4/5 | Ubuntu 24.04 Server (arm64) | apt, as on Ubuntu |
| Linux laptop or desktop | Ubuntu 24.04 | apt |
| Mac | macOS | see [On a Mac](#on-a-mac) |
| Windows | Windows 10/11 | official Windows binaries, or WSL2 with Ubuntu 24.04 |
| Ben's AlmaLinux 9 workstation | RHEL 9 family | Pixi/RoboStack in `$HOME` (no admin), or the official RHEL 9 RPMs (needs admin) |

## Ubuntu 24.04 (laptop, VM, Pi, Orin)

The official steps, from <https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html>:

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

Add `source /opt/ros/jazzy/setup.bash` to `~/.bashrc`. To check the install, run
`ros2 run demo_nodes_cpp talker` in one terminal and
`ros2 run demo_nodes_py listener` in another.

## Building this workspace

From the repository root:

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -y    # installs every stock package we use
colcon build --symlink-install
source install/setup.bash                          # in every new terminal
```

What the commands do:
- **`rosdep`** reads every `package.xml` and installs the dependencies with apt: Nav2,
  robot_localization, twist_mux, the Gazebo bridge, and so on. Packages with a
  `COLCON_IGNORE` file (the parked perception code) are skipped.
- **`--symlink-install`** links the Python files and configs instead of copying them.
  Edits then only need a relaunch, not a rebuild. The C++ IMU driver and the message
  package still need `colcon build` after a change.
- **Build part of the workspace:** `colcon build --packages-up-to aav_bringup` builds
  only what the launch profiles need. `--packages-select aav_ego` builds one package.
- **After switching branches**, or if something odd happens: delete `build/` `install/`
  `log/` and rebuild. They are machine-specific and never committed.

## Languages and compiling for each machine

| Code | Language | Built where |
|---|---|---|
| Our ROS nodes (`ego`, `spine_bridge`, `scripted_driver`, the adapters) | Python | Nowhere: the same source runs on x86 laptops and ARM boards. `colcon build` only installs it. |
| `aav_interfaces` (our messages) | `.msg`/`.action`, generated into C++ and Python | by colcon, on each machine |
| `yahboom_imu_cpp` (the reused IMU driver) | C++ | by colcon, on the machine it runs on (the Orin builds it in seconds) |
| `firmware/spine` | Rust (`no_std`) | cross-compiled on any laptop for the ESP32, then flashed over USB |
| `firmware/legacy` | C++ (Arduino/PlatformIO, Pico SDK) | PlatformIO / the Pico SDK on a laptop |
| launch files, configs, URDF | Python, YAML, xacro | not compiled |

Python wasn't chosen just to avoid compiling. The nodes we write are glue that runs at
50 Hz or less, and the hard timing lives in the firmware. Python is quickest to write,
easiest for next year's team, and officially supported (`rclpy`). Not having to
cross-compile is a bonus.

Rust's targets, for reference:
- the Orin and the Pis: `aarch64-unknown-linux-gnu`;
- ESP32 (Xtensa): via `espup`;
- ESP32-C3/C6: standard RISC-V targets;
- Pico 2: `thumbv8m.main-none-eabihf`.

A Rust ROS node (`rclrs`) links against the ROS libraries, so build it on the board. A
bare microcontroller can't run a ROS node at all: it reaches ROS through a bridge, which
for us is the CAN spine and `spine_bridge`. See [firmware.md](firmware.md).

## On a Mac

*Being written: see the Mac section of docs/status.md for now.*

## Networking: several computers, one ROS graph

ROS 2 has no master. Nodes find each other with multicast discovery on the local
network.

1. **Same domain everywhere.** Put `export ROS_DOMAIN_ID=<n>` in every machine's
   `~/.bashrc`, using one team-wide number between 1 and 101. The 2025-26 dashboard used
   10 and its UI used 0, which is why they never saw each other. Default 0 is shared
   with every other ROS user on the network.
2. **Same network, multicast allowed.** The car's own router or switch works. Campus WiFi
   often blocks multicast. If machines can't see each other, list them explicitly with
   `ROS_STATIC_PEERS` (Jazzy) and test with `ros2 multicast receive` / `ros2 multicast send`.
3. **Keep the default `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`.** Jazzy replaced the old
   `ROS_LOCALHOST_ONLY` with this; set it to `LOCALHOST` to keep a laptop's experiments
   off the car.
4. **One middleware everywhere.** Jazzy's default is Fast DDS. If you switch to Cyclone
   DDS (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`), switch every machine.
5. **Synchronised clocks.** Run chrony on every machine, with the Orin as the car's time
   server. ego tolerates a wrong clock but logs a warning; TF and the EKFs do not
   tolerate one.
6. **VMs need bridged networking**, not NAT, so that the VM gets an address on the
   car's network.

`ros2 doctor --report` and `ros2 multicast send/receive` diagnose most problems.

## Moving the Orin to JetPack 7.2 (Ubuntu 24.04)

It's a reflash, not an upgrade:
1. **Back up `/home/aavjetson` and every workspace first.** It holds the only copy of the
   2025-26 YOLO detector and camera/LiDAR setup. Better still, take a full image with
   `l4t_backup_restore.sh`.
2. **Check `cat /etc/nv_tegra_release`** and the module part number. Module
   699-13701-0005-502 has a reported flashing problem, while -501 works.
3. **Flash with SDK Manager** from an Ubuntu 22.04 or 24.04 x86 PC, or use the dev kit's
   USB installer.
4. **Install Jazzy** as above.

Move the Pis to Ubuntu 24.04 at the same time. The rationale and the risks are in
[history/conversation.md](history/conversation.md#so-we-can-upgrade-the-orin-to-jazzy-jetpack-72-test-it-before-committing).
