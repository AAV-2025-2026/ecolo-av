# u-blox ZED-F9R GNSS Publisher

This repository contains a ROS 2 integration stack for the **u-blox ZED-F9R** GNSS module. It is designed to provide highly accurate, RTK-corrected `sensor_msgs/NavSatFix` data for the naviagation of the AAV.

To accommodate both rapid hardware testing and final vehicle deployment, this repository is split into two versions: a lightweight **Standalone** version and a formal **ROS 2 Colcon Workspace** version.

## Repository Structure

```text
gnss_node/
├── README.md               <-- You are here
├── standalone/             <-- Prototype & Hardware testing
│   ├── install_setup.sh
│   ├── launch_gps.sh
│   ├── README.md
│   ├── other/
│   └── src/
└── ros2_ws/                <-- Final deployment build
│   ├── README.md
    └── src/
```

---

## 1. Standalone Version (`/standalone`)

**Best for:** Initial hardware validation, debugging, and running the GNSS node on a laptop without needing to compile a full ROS 2 workspace.

This version uses a "Sidecar Architecture". It runs the ROS 2 node directly via a standard Python script while a background bash process manages the RTK connection (`str2str`) and handles auto-recovery if the network drops. 

* **No `colcon build` required.**
* Includes `udev` rules for persistent, permission-free serial access (`/dev/zed_f9r`).
* **See the [Standalone README](./standalone/README.md) for full setup and usage instructions.**

---

## 2. ROS 2 Workspace Version (`/ros2_ws`)

**Best for:** Integration into the final autonomous vehicle stack running on the onboard computer.

This is a formally structured ROS 2 Python package. It is designed to be built using `colcon build` and launched using standard ROS 2 launch files. It integrates the core NMEA-parsing and RTK-management logic into a structure that downstream nodes (like `robot_localization`) can easily interface with.

* Built for production deployment.
* Managed via `package.xml` and `setup.py`.
* **See the [ROS 2 Workspace README](./ros2_ws/README.md) for build instructions and parameter configurations.**

---

## Hardware Dependencies

Both versions are built for the **u-blox ZED-F9R-01B** and require the following system packages:
* `rtklib` (for NTRIP RTK stream management)
* `python3-serial`
* `python3-nmea2`

## Core Outputs

Both versions publish to the exact same ROS 2 topics:

| Topic | Type | Description |
| :--- | :--- | :--- |
| `/aav/gps/fix` | `sensor_msgs/NavSatFix` | Real-time coordinate data. |

**Status Indicator Mapping:**
* `-1`: No Fix (Invalid / Searching)
* `0`: Standard GPS / Dead Reckoning
* `1`: SBAS (WAAS corrections, active while waiting for RTK)
* `2`: GBAS / RTK (Centimeter-level accuracy)

## Author
Tommy Csete - Localization Group
