# AAV Radar

A ROS 2 driver for real-time **object detection and environment mapping** using the Texas Instruments IWR6843AOP 60–64 GHz mmWave radar sensor. Built for autonomous aerial vehicles and other robotics platforms.


## Hardware requirements

| Item | Details |
|---|---|
| Sensor | TI IWR6843AOP (60–64 GHz mmWave, antenna-on-package) |
| Interface | USB-UART via MMWAVE-DEVPACK or DCA1000EVM |
| Host OS | Ubuntu 22.04 (recommended) |
| ROS version | ROS 2 Humble or later |


## Before you start - flashing the sensor

The IWR6843AOP must be flashed with the correct mmWave firmware before use. Special configuration files required for flashing are in the database sheet provided below.

**Datasheet (DBS)** - full specs, pin diagrams, SOP boot modes:  
https://www.ti.com/lit/ds/symlink/iwr6843aop.pdf?ts=1775563735084&ref_url=https%3A%2F%2Fwww.ti.com%2Fproduct%2FIWR6843AOP

**Flashing guide** - official TI hardware setup walkthrough (EVM config, USB, SOP mode, power cycling):  
https://www.ti.com/video/6205846491001

### SOP (Sense-on-Power) mode reference

The three SOP pins are sampled at power-up to select the boot mode. Set them using the jumpers on your EVM **before** applying power.

| SOP[2] | SOP[1] | SOP[0] | Mode |
|:------:|:------:|:------:|------|
| 0 | 0 | 0 | Autonomous mode - runs application from QSPI flash |
| 0 | 1 | 0 | Flash programming mode - use this to flash firmware |
| 1 | 0 | 1 | JTAG debug mode |

> After flashing, set SOP back to `000` and power cycle the board to boot into autonomous mode.


## Getting started

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/<your-org>/aav-radar.git
cd aav-radar

# 2. Install dependencies
cd install && ./install.sh

# 3. Build
cd ../build
colcon build --symlink-install
source install/setup.bash

# 4. Run (see src/ for launch files and config)
ros2 launch src/ros2 (which method you want).py
```


## Repository structure

```
aav-radar/
├── build/              # Build artifacts
├── install/            # Install scripts
├── iwr6843aop_pub/     # ROS 2 sensor publisher node (submodule)
├── log/                # Runtime logs
├── src/                # Radar driver, launch files, and config
├── tools/              # Config files required for flashing
├── frames_*.gv / .pdf  # Radar frame visualizations from test runs
└── .gitmodules
```


## Project status

| Layer | Status |
|---|---|
| Low-level driver - sensor communication, UART, raw point cloud publishing | Complete |
| Higher-level - ROS 2 integration, object detection, tracking |  Complete |
| Cluster map | In progress - implemented but requires further testing for full confidence |

## Reference repositories

Two open-source repos were used as references during development. Both are useful starting points if you want to understand the stack at different levels.

**Low-level reference** - bare sensor publisher, good for understanding the hardware interface and raw data format:  
N. H. M. A., "IWR6843AOP ROS Publisher," GitHub, 2025.  
https://github.com/nhma20/iwr6843aop_pub

** Advanced reference** - full ROS 2 integration with object detection, closer to what this repo builds on top of:  
lightinfection, "TI IWR6843AOP Driver," GitHub, 2024.  
https://github.com/lightinfection/TI_IWR6843AOP


## Contributing

Pull requests and issues are welcome. Please open an issue first to discuss any significant changes to the detection or mapping pipeline.

## License

MIT - see [LICENSE](./LICENSE) for details.
