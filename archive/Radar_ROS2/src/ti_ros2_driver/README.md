# ti_ros2_driver

The TI ROS 2 driver package. This is the bridge between the IWR6843AOP hardware and the ROS 2 ecosystem - it handles sensor configuration, publishes point cloud data, runs heat map visualisation, and provides the foundation on top of which the `object_detection` package operates.

Based on and adapted from the higher-level reference:  
https://github.com/lightinfection/TI_IWR6843AOP

## Status

This package is fully complete. All launch modes, configurations, and publisher nodes are working.

## What this package does

When you launch this driver it does the following:

1. Opens a serial connection to the IWR6843AOP over UART
2. Sends a chirp configuration file (`.cfg`) to the sensor to program its radar parameters - range, velocity resolution, frame rate, antenna mode
3. Reads the sensor's output stream frame by frame
4. Parses each frame into a structured point cloud (x, y, z, intensity, Doppler velocity per point)
5. Publishes the point cloud as a ROS 2 topic that `object_detection` and any other downstream nodes subscribe to
6. Optionally runs heat map or 3D tracking visualisation depending on which launch file is used

---

## Package structure

```
ti_ros2_driver/
├── cfg/
│   ├── bin/
│   ├── 3d_tracking_high_detection.cfg
│   ├── 3d_tracking_indoor.cfg
│   ├── 3d_tracking_low_noise.cfg
│   ├── AOP_6m_default.cfg
│   ├── AOP_6m_staticRetention.cfg
│   ├── AOP_6m_tracking_default.cfg
│   ├── AOP_9m_default.cfg
│   ├── AOP_9m_sensitive.cfg
│   ├── ISK_14m_extended.cfg
│   ├── ISK_6m_default.cfg
│   ├── ISK_6m_staticRetention.cfg
│   ├── ISK_6m_staticRetention_45de...cfg
│   ├── ODS_6m_default.cfg
│   ├── ODS_6m_staticRetention.cfg
│   ├── RADheatmap.cfg
│   ├── base.cfg
│   └── rules.txt
├── debug/
│   └── result.json
├── launch/
│   ├── 6843aop_3d_tracking.launch.py
│   ├── 6843aop_HeatMap.launch.py
│   └── 6843aop_base.launch.py
├── resource/
│   └── ti_ros2_driver
├── test/
│   ├── test_copyright.py
│   ├── test_flake8.py
│   └── test_pep257.py
├── ti_ros2_driver/
│   ├── __pycache__/
│   ├── TI.py
│   ├── __init__.py
│   ├── benchmark.py
│   ├── pc_publisher.py
│   └── plotheatmap.py
├── package.xml
├── setup.cfg
├── setup.py
└── README.md
```

## cfg/

Chirp configuration files. These are the most important files for anyone setting up or tuning the sensor. Each `.cfg` file programs the IWR6843AOP with a complete set of radar parameters - without a valid config the sensor will not produce any data.

A config file defines: the number of chirps per frame, the chirp slope (which sets range resolution), the idle time between chirps, the ADC sample rate, the frame period, and which TX/RX antennas are active. Changing these values changes the fundamental trade-offs between range, velocity resolution, angular resolution, and update rate.

**Do not modify a `.cfg` file unless you understand what each parameter does.** Incorrect values can cause the sensor to reject the config entirely or produce garbage data. Always test a modified config on the bench before using it in flight.

### Config file reference

| File | Antenna mode | Max range | Use case |
|---|---|---|---|
| `AOP_6m_default.cfg` | AOP (on-package) | ~6 m | General purpose default for AOP variant - start here |
| `AOP_6m_staticRetention.cfg` | AOP | ~6 m | Retains static (non-moving) objects that would otherwise be filtered by Doppler - useful for mapping walls and fixed obstacles |
| `AOP_6m_tracking_default.cfg` | AOP | ~6 m | Optimised for object tracking - pairs with `6843aop_3d_tracking.launch.py` |
| `AOP_9m_default.cfg` | AOP | ~9 m | Extended range variant of the default - lower update rate than 6 m configs |
| `AOP_9m_sensitive.cfg` | AOP | ~9 m | Higher sensitivity at 9 m - more susceptible to noise, use in clean RF environments |
| `3d_tracking_high_detection.cfg` | AOP | ~6 m | Maximises detection probability for 3D tracking - higher false positive rate |
| `3d_tracking_indoor.cfg` | AOP | ~6 m | Tuned for indoor environments with many reflective surfaces |
| `3d_tracking_low_noise.cfg` | AOP | ~6 m | Prioritises noise rejection over detection rate - use in electrically noisy environments |
| `ISK_6m_default.cfg` | ISK (external antenna) | ~6 m | Default for ISK antenna variant - not applicable if using AOP package |
| `ISK_6m_staticRetention.cfg` | ISK | ~6 m | Static retention for ISK variant |
| `ISK_6m_staticRetention_45de...cfg` | ISK | ~6 m | Static retention with 45° mounting angle compensation |
| `ISK_14m_extended.cfg` | ISK | ~14 m | Long range config for ISK - very low update rate |
| `ODS_6m_default.cfg` | ODS | ~6 m | For ODS (obstacle detection) antenna variant |
| `ODS_6m_staticRetention.cfg` | ODS | ~6 m | Static retention for ODS variant |
| `RADheatmap.cfg` | AOP | ~6 m | Special config for raw ADC heat map mode - used with `6843aop_HeatMap.launch.py` |
| `base.cfg` | AOP | ~6 m | Minimal base configuration - used as a starting point or for debugging |

### `rules.txt`
Defines validation rules that the driver checks the loaded `.cfg` against before sending it to the sensor. If you write a custom config and the driver refuses to load it, check whether it violates any rule defined here.

### `bin/`
Contains compiled binary versions of certain config files or supporting tools used during the sensor initialisation sequence.

## debug/

### `result.json`
A JSON file capturing output from a debug or benchmark run - contains parsed point cloud data, frame timestamps, or performance metrics depending on what was running when it was generated. Useful for offline analysis without needing the sensor connected. If you run `benchmark.py` the results are written here.

---

## launch/

All launch files connect to the sensor, load a config, and start the appropriate ROS 2 nodes. Run from the workspace root after sourcing:

```bash
source install/setup.bash
ros2 launch ti_ros2_driver <launch_file>.launch.py
```

You will need to pass the correct serial port and config file path as arguments - check inside each launch file for the available parameters.

### `6843aop_base.launch.py`
The minimal launch file. Starts only the point cloud publisher (`pc_publisher.py`) with a specified config file. No tracking, no visualisation. Use this to verify the sensor is connected and producing data, or as the base when writing a new launch configuration.

```bash
ros2 launch ti_ros2_driver 6843aop_base.launch.py
```

### `6843aop_3d_tracking.launch.py`
Starts the full 3D tracking pipeline. Loads a tracking-optimised config (typically `AOP_6m_tracking_default.cfg`), starts the point cloud publisher, and launches the 3D tracking node. This is the primary launch file for obstacle detection during flight. The `object_detection` package's tracking pipeline subscribes to the topics published by this launch.

```bash
ros2 launch ti_ros2_driver 6843aop_3d_tracking.launch.py
```

### `6843aop_HeatMap.launch.py`
Starts the heat map visualisation mode. Loads `RADheatmap.cfg`, starts the point cloud publisher, and launches `plotheatmap.py` to render a 2D range-azimuth heat map of raw radar returns. This mode does not run object detection or tracking - it is purely a diagnostic and visualisation tool. Use it to verify antenna alignment, check for environmental interference, or visually confirm detection coverage before a flight.

```bash
ros2 launch ti_ros2_driver 6843aop_HeatMap.launch.py
```

## resource/

### `ti_ros2_driver`
A marker file used by the ROS 2 ament resource index. It tells the ROS 2 tooling that this package is installed and available. You do not need to touch this file - it is managed automatically by the build system.

## test/

Automated code quality checks run by colcon during CI. These do not test radar functionality - they check that the Python source code meets style and documentation standards.

### `test_copyright.py`
Checks that all Python source files in the package contain a valid copyright header. If you add a new `.py` file, make sure it has the correct copyright notice at the top or this test will fail.

### `test_flake8.py`
Runs the Flake8 Python linter across all source files. Catches syntax errors, undefined variables, unused imports, and style violations (line length, whitespace, etc.). Fix any reported issues before committing.

### `test_pep257.py`
Checks that all Python docstrings conform to PEP 257 conventions. If you add functions or classes without docstrings, or with incorrectly formatted ones, this test will flag them.

Run all tests manually with:

```bash
colcon test --packages-select ti_ros2_driver
colcon test-result --verbose
```

## ti_ros2_driver/ (inner Python module)

This is the actual Python source module - the code that runs when you launch the driver.

### `__init__.py`
Marks this directory as a Python package so its modules can be imported. Empty or near-empty - do not add logic here.

### `TI.py`
The core serial communication and frame parsing module. This is the most important file in the package. It is responsible for:

- Opening and configuring the UART serial port to the IWR6843AOP
- Sending the chirp configuration file to the sensor line by line at startup
- Reading the binary data stream output by the sensor
- Parsing the TI mmWave data protocol - extracting the magic word, frame header, and TLV (Type-Length-Value) blocks that contain point cloud data, object lists, and side info
- Returning structured Python objects representing each radar frame

If the sensor is connected but producing no data, or if parsing errors appear in the terminal, this is the first file to investigate.

### `pc_publisher.py`
The ROS 2 node that ties everything together. It instantiates `TI.py` to read frames from the sensor and publishes the parsed point cloud as a `sensor_msgs/PointCloud2` message on a ROS 2 topic. This is what `object_detection` subscribes to.

Key responsibilities:
- Initialises the ROS 2 node
- Calls `TI.py` in a loop to fetch new frames
- Converts parsed frame data into `PointCloud2` messages
- Publishes at the frame rate defined in the loaded `.cfg` file

Two topics are published:

| Topic | Type | Description |
|---|---|---|
| `/ti_radar_0/ti_mmwave_0` | `sensor_msgs/msg/PointCloud2` | Raw radar detections - many points per frame |
| `/ti_radar_0/ti_mmwave_0_objects` | `sensor_msgs/msg/PointCloud2` | Processed output - one point per detected object |

If downstream nodes are not receiving point cloud data, check that this node is running and publishing with:

```bash
ros2 topic list
ros2 topic echo /ti_radar_0/ti_mmwave_0
```

### `plotheatmap.py`
A visualisation node that generates a 2D range-azimuth heat map from raw radar returns. Only used when launching with `6843aop_HeatMap.launch.py`. Renders the heat map using matplotlib or a similar library and either displays it in a window or publishes it as a ROS image topic.

Use this to visually verify the sensor's field of view, check for dead zones in antenna coverage, or diagnose interference before a flight.

### `benchmark.py`
A performance benchmarking script. Measures frame parsing speed, point cloud publication latency, and serial read throughput. Results are written to `debug/result.json`. Run this when profiling system performance or after making changes to `TI.py` to confirm you have not introduced regressions in parsing speed.

### `__pycache__/`
Auto-generated Python bytecode cache. Ignored by git and regenerated automatically - do not commit or manually edit.

## package.xml

The ROS 2 package manifest. Declares the package name (`ti_ros2_driver`), version, maintainer, license, and all build and runtime dependencies including `rclpy`, `sensor_msgs`, and any serial communication libraries. If the package fails to build or import at runtime due to a missing dependency, add it here and rebuild.

## setup.cfg

Tells the Python build tools where the entry points are - specifically which Python functions map to which ROS 2 executable names. If you add a new node script and want to launch it by name (e.g. `ros2 run ti_ros2_driver my_new_node`), register its entry point here.

## setup.py

The Python package setup script. Works together with `setup.cfg` to define how the package is installed by colcon. Also specifies which non-Python files (like the contents of `cfg/`, `launch/`, and `resource/`) should be included in the install. If you add new config files or launch files and they are not being installed to `install/`, check that they are listed here.


## Choosing the right config file

This is the most common decision a new developer will face. Use this as a starting point:

| Situation | Recommended config |
|---|---|
| First time setup, just want to see data | `AOP_6m_default.cfg` |
| Indoor flight, many walls and reflections | `3d_tracking_indoor.cfg` |
| Need to detect stationary obstacles | `AOP_6m_staticRetention.cfg` |
| Running 3D object tracking | `AOP_6m_tracking_default.cfg` |
| Electrically noisy environment | `3d_tracking_low_noise.cfg` |
| Want maximum detection range | `AOP_9m_default.cfg` |
| Diagnosing antenna coverage | `RADheatmap.cfg` with HeatMap launch |
| Debugging from scratch | `base.cfg` |

## For future developers

- **The config file you choose has the single biggest effect on system performance.** Before changing any code, try a different `.cfg` first - it is faster and safer
- If the driver connects but the sensor produces no output, the most common cause is a wrong serial port or a config file that the sensor rejected. Watch the terminal output during launch - `TI.py` will print the config lines as they are sent and will report any rejection from the sensor
- `result.json` in `debug/` is useful for reproducing issues without needing the sensor - it contains real parsed output from a previous run that you can feed back into the algorithm code offline
- If you add a new config file, document it in the table above so the next developer knows when to use it
- The three test files in `test/` must pass before merging any changes. Run them with `colcon test` before opening a pull request
