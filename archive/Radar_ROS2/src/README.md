# src/

This is the source directory for the workspace. It contains the three ROS 2 packages that make up the AAV radar stack.

## Packages

### `iwr6843aop_pub` *(git submodule @ 4dc00f8)*
Low-level ROS 2 publisher for the TI IWR6843AOP sensor. Handles serial communication over UART, parses raw mmWave radar frames, and publishes point cloud data as standard ROS messages.

This package is the **low-level reference** described in the top-level README - based on and adapted from:  
https://github.com/nhma20/iwr6843aop_pub

- Status: Complete

### `object_detection`
Higher-level perception package. Consumes the point cloud from `iwr6843aop_pub` and runs detection and tracking algorithms to identify and localise objects in the radar's field of view.

This package belongs to the **higher-level reference** described in the top-level README - based on and adapted from:  
https://github.com/lightinfection/TI_IWR6843AOP

- Status: Complete - cluster map requires further testing for full confidence

### `ti_ros2_driver`
TI's ROS 2 driver layer. Manages sensor configuration, chirp profile loading, and the data pipeline between the hardware and the ROS 2 ecosystem.

This package belongs to the **higher-level reference** described in the top-level README - based on and adapted from:  
https://github.com/lightinfection/TI_IWR6843AOP

- Status: Complete

## Building

From the workspace root:

```bash
colcon build --symlink-install
source install/setup.bash
```

To build a single package:

```bash
colcon build --symlink-install --packages-select <package_name>
# e.g.
colcon build --symlink-select object_detection
```

## Updating the submodule

`iwr6843aop_pub` is a git submodule. To pull the latest version:

```bash
git submodule update --remote src/iwr6843aop_pub
```
