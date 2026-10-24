# AAV GNSS/IMU Nodes

This repository contains the core ROS 2 sensor packages for the aav. It is structured to separate the GNSS and IMU nodes, alongside an archive of deprecated code.

## Repository Structure

```text
.
├── gnss_node/                     # ROS 2 driver for the u-blox ZED-F9R GNSS receiver
├── imu_node/                      # ROS 2 driver for the IMU
└── legacy/                        # Archive of older iterations from previous years
```

## Packages Overview

### 1. GNSS Node (`/gnss_node`)
A robust, thread-safe ROS 2 package designed to handle serial NMEA communication with the u-blox ZED-F9R. 
* Parses NMEA sentences and publishes `sensor_msgs/NavSatFix` messages.
* Manages a background RTK/NTRIP correction stream using `rtklib` for high-precision global positioning.
* Includes `systemd` deployment scripts for automatic startup on vehicle boot.
* **[View the GNSS README for setup and launch instructions](./gnss/README.md)**

### 2. IMU Node (`/imu_node`)
ROS 2 driver responsible for interfacing with the Inertial Measurement Unit.
* Publishes high-frequency `sensor_msgs/Imu` messages (orientation, angular velocity, and linear acceleration).
* Designed to work in tandem with the GNSS node to feed the aav's sensor fusion and localization stack.
* **[View the IMU README for setup and launch instructions](./imu/README.md)**

### 3. Legacy Code (`/legacy`)
This directory serves as an archive for older iterations of the project. It contains deprecated scripts, previous driver implementations, and test files that are no longer actively maintained but are kept for reference and version history.

## Getting Started

Because the GNSS and IMU packages have different system-level dependencies (like specific `udev` rules and hardware configurations), they each have their own dedicated installation scripts and build instructions. 

Please navigate to the respective folder's `README.md` for specific instructions on how to install prerequisites, build the ROS 2 packages via `colcon`, and launch the nodes.
