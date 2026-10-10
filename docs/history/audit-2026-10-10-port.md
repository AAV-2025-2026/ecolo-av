# Audit, 10 October 2026: Jazzy port of the inherited code, dependencies, languages

A read-only audit by a Claude Code agent, kept as it reported. Line numbers are from the tree at the time; fixes are tracked in `TODO.md`.

I made no changes under `/home/ben/aav`; `git status` and a `find -newer` check came back clean. Scratch scripts and raw outputs are in `/tmp/aav_portaudit/{scripts,out}` and the downloads are in fresh `dl_*` folders. That folder already had files from an earlier session; I didn't use them. Imports ran as `pixi run --as-is tools/ros.sh python3 -B -P …`, which doesn't touch the lockfile or the environment and writes no `__pycache__`. The main session committed `8ed4ccf` and kept editing `docs/` while I worked, so docs line counts drift.

**1. Per package**

**Jazzy-ready** (they build, pass tests, and their entry points and 25 launch files all import): aav_bringup, aav_description, aav_interfaces, aav_gazebo, aav_legacy, aav_spine, aav_turtlesim, aav_navigation, aav_scripted, aav_teleop, aav_ego, aav_localization, aav_mux.
- NOTE: the CMake warning (section 3).
- NOTE: `.get_logger().warn(` is a deprecated alias in Jazzy's rclpy. It appears at `ego_node.py:60`, `scripted_driver.py:75`, `legacy_uart_bridge.py:44,52`, `spine_bridge.py:112,142` and `encoder_udp.py:54` → use `.warning(`.
- The Gazebo and Nav2 profiles were not run here: UNVERIFIED.

**aav_carla** (pixi only)
- WRONG: `package.xml:14` needs `topic_tools`, which isn't in the pixi env → add `ros-jazzy-topic-tools = ">=1.3.4,<2"` to `pixi.toml` (on robostack-jazzy for all 3 platforms).

**aav_sensors** (pixi only)
- WRONG: `package.xml:14-15` (`ublox_dgnss_node`, `ublox_nav_sat_fix_hp_node`) installs on noble through apt (ublox_dgnss 0.7.4-1). It is not on robostack-jazzy, which only has `ros-jazzy-ublox` and `-ublox-gps`. So `sensors.launch.py` with the default `gps:=true` can't run under pixi on any OS.

**maincar** — needs changes
- BREAKS (pixi): `ui_flask.py:9` and `:11` fail with ModuleNotFoundError for `flask` and `flask_socketio` → add both to `pixi.toml`.
- BREAKS (noble, at boot): `ui_flask.py:129-135` `socketio.run(...)` → add `allow_unsafe_werkzeug=True`.
  - Flask-SocketIO 5.3.6 (noble) raises RuntimeError when stdin isn't a terminal, e.g. under systemd, which is how `flask_bootup.sh` starts it.
  - 5.0.1 (jammy) had no such check; I confirmed this in both versions' sources.
  - The error kills a daemon thread, so the HUD back end silently never listens.
- WRONG: the websocket transport needs `simple-websocket`.
  - noble has no `python3-simple-websocket` package (Launchpad shows plucky and later only), and rosdep has no key for it.
  - The Flutter client allows only websockets (`socket_services.dart:27`).
  - Fix: pixi's `flask-socketio` already pulls `simple-websocket`. On apt machines change `:27` `.setTransports(['websocket'])` → `.setTransports(['polling', 'websocket'])`.
- WRONG: `package.xml` is missing `<depend>sensor_msgs</depend>` (`ui_flask.py:14`, `ui_test.py:21`) and `<exec_depend>` for `launch` and `launch_ros` (`launch/launch.py:1-2`).
- WRONG: `ui_flask.py:91` `mock_gps_altitude` → `mock_gps_z` (it raises NameError). `:106` `list_lastestRoute` → `list_latestRoute`.
- WRONG: `ui_flask.py:382-386` and `ui_test.py:111-113` → use the repo's pattern, `except (KeyboardInterrupt, ExternalShutdownException)` plus `rclpy.try_shutdown()`.
- NOTE: `launch/launch.py:14-19` also starts the mock publisher.
- NOTE: `docs/hud.md:44-45` ("Flask from apt") is incomplete without the two fixes above.

**battery_monitor** — needs changes
- WRONG: the test failure (section 3).
- WRONG: `battery_monitor.py:3-5` uses bare sibling imports, which only work as the installed console script because `setup.py:13-15` copies the modules into `lib/`. → `from battery_monitor.VEDirect import VEDirect` (same for the other two), then delete `setup.py:13-15`.
- WRONG: `battery_monitor.py:8-9` hard-codes `/dev/ttyUSB0` and 19200 → make them parameters, defaulting to `/dev/aav/battery` (`99-aav.rules:20`).
- WRONG: the `while True` loop at `battery_monitor.py:74-81` makes the cleanup unreachable → add try/except/finally.

**ti_ros2_driver** — needs changes
- BREAKS (pixi): `pcl_pub` fails with ModuleNotFoundError for `scipy` (`plotheatmap.py:5`, imported from `pc_publisher.py:16`) → add `scipy`.
- WRONG: the test failure (section 3).
- WRONG: `pc_publisher.py:25` and `:35` default to `os.getcwd()+'/src/ti_ros2_driver/...'`, which is wrong for our layout → `os.path.join(get_package_share_directory('ti_ros2_driver'), 'cfg', 'base.cfg')`.
- WRONG: `TI.py:34,38` runs `os.system("sudo chmod +777 "+port)` → delete it; use the udev rules (`99-aav.rules:16-17`).
- WRONG: `pc_publisher.py:298`, `obstacle_extractor.py:203` and `mock_radar_publisher.py:94` → also catch `ExternalShutdownException`.
- NOTE: `package.xml:10` `<depend>ros2launch</depend>` → exec_depend `launch`, `launch_ros` and `ament_index_python`.
- NOTE: `launch/*:13-14` → use `/dev/aav/radar_cmd` and `/dev/aav/radar_data`.

**yahboom_imu_cpp** — needs changes. It compiles cleanly against the Jazzy headers with `-Wall -Wextra -Wpedantic`.
- WRONG: the lint failures (section 3).
- NOTE (README): `:14` "ROS2 Humble" → "ROS 2 Jazzy". Delete `:20` (`ros-humble-serial`): no `serial` package exists in Humble or Jazzy, and the code uses termios. `:45` `/opt/ros/humble` → `/opt/ros/jazzy`.
- NOTE (Mac, UNVERIFIED because there's no macOS SDK here): `serial_port.cpp:50` `B921600` isn't defined on macOS → wrap it in `#ifdef B921600`.
- NOTE: add exec_depend `launch` and `launch_ros` to `package.xml`. Change `imu.launch.py:12` to `/dev/aav/imu`.

**Parked — what porting would need**
- **lane_geometry:**
  - exec_depend `launch`, `launch_ros`, `python3-numpy`.
  - `control_interface.py:94` publishes Twist on `/control_cmd` → TwistStamped on `/cmd_vel/<driver>`.
  - Use the Jazzy shutdown pattern.
- **object_detection:**
  - Add `visualization_msgs`, `octomap`, `eigen`, `libpcl-all-dev`, plus exec `rviz2` and `ament_index_python`.
  - `CMakeLists.txt:5` C++14 → 17.
  - Drop the never-set `${Boost_SYSTEM_LIBRARY}` (`:49-61`).
  - `test_icp.cpp:24-25` has `/home/lscm` paths.
  - Pixi needs `ros-jazzy-pcl-ros`.
  - `find_package(PCL 1.12)` is fine: it accepts newer versions.
- **yolo_ros2:**
  - BREAKS the build: `resource/yolo_ros2` is missing (`setup.py:17-18`).
  - `setup.py:15` → `extras_require`.
  - Add `rclpy`, `sensor_msgs`, `cv_bridge`, `python3-opencv`, `python3-ultralytics-pip`. That last key installs with pip, which noble's system Python blocks (PEP 668): needs `PIP_BREAK_SYSTEM_PACKAGES=1` or a venv.
  - Pixi: `ultralytics` and `pytorch`.
  - `yolo_inference.py:26` hard-codes `~/Yolo` weights; `:69` `imshow` needs a display.

**Firmware and HUD**
- `aav_umod_esp32` does not use micro-ROS, so there is no Humble/Jazzy agent problem.
  - `platformio.ini:34-46` has no micro-ROS library.
  - `ros2_handler.cpp:8-80` reads a custom 13-byte UART frame on Serial1: three float32 values plus a checksum.
  - Its ROS side is aav_legacy.
  - The sentinel Pico 2 and the UDP wheel encoder don't use ROS either.
- `hud/flutter_pi` has no ROS client.
  - It talks Socket.IO to `127.0.0.1:5000` (`home_page.dart:31`, `map_page.dart:86`) and posts to `/receive` (`map_page.dart:348`), both served by the maincar ROS node.
  - It only listens for `mock_*` and `nav_state` events (`socket_services.dart:47-76`).
- `hud/scripts`:
  - `flask_bootup.sh:19` sources the old Humble workspace → source this repo's `install/setup.bash`.
  - All three scripts hard-code `/home/aavui`.
  - `flutter_bootup.sh:26` uses `flutter run`, which is a debug build.

**2. Dependencies**
- Every key in all 22 `package.xml` files, parked ones included, resolves for Jazzy on noble. Each is either in jazzy `distribution.yaml` or a rosdep key with an ubuntu entry in `base.yaml`/`python.yaml`.
- **Missing:**
  - maincar: `sensor_msgs`, `launch`, `launch_ros`.
  - ti_ros2_driver: `launch`, `launch_ros`, `ament_index_python`.
  - yahboom: `launch`, `launch_ros`.
  - Parked packages: as listed above.
- **Extra:**
  - ti_ros2_driver's `ros2launch`.
  - maincar's 4 test_depends, though its tests weren't copied.
  - `ament_flake8` in our ament_python packages, which have no flake8 test.
- **pixi.toml additions:**
  - `flask = ">=3.1.3,<4"`
  - `flask-socketio = ">=5.7.0,<6"` (pulls `python-engineio` and `simple-websocket`)
  - `scipy = ">=1.18.1,<2"` (py312 builds exist for linux-64, osx-arm64 and osx-64)
  - `ros-jazzy-topic-tools`
  - `ublox_dgnss` has no conda package.
- **Rosdep keys, already declared, all noble-valid:**
  - `python3-flask` (`python.yaml:4397`)
  - `python3-flask-socketio` (`:4448`)
  - `python3-scipy` (`:8218`)
  - Source: https://raw.githubusercontent.com/ros/rosdistro/master/rosdep/python.yaml
  - `simple-websocket` has no key.

**3. Test failures and build warnings**

**yahboom_imu_cpp: 13 failures** = 9 flake8 + 1 lint_cmake + 3 uncrustify. I applied these fixes to a copy in `/tmp` and every linter then reported no problems:
- `CMakeLists.txt:28` `install (DIRECTORY launch` → `install(DIRECTORY launch`.
- `launch/imu.launch.py`: add a second blank line before line 4, and a newline at the end of the file.
- `raw_check.py`: delete line 2 (`import time`); use single quotes on lines 5, 14 and 15.
- Run `ament_uncrustify --reformat include src`.

ament skips cppcheck 2.22 entirely, and `CMakeLists.txt:34-35` turns off the copyright and cpplint checks.

**battery_monitor and ti_ros2_driver**
- Cause: setuptools 79 drops `tests_require=['pytest']` (`setup.py:23` and `setup.py:25`). colcon then falls back to `python3 -m unittest`, which finds no tests and exits with code 5.
- Fix: replace it with `extras_require={'test': ['pytest']},`. I checked with colcon's own `has_test_dependency`, which goes from False to True.
- After that the lint tests actually run:
  - pep257 passes and the copyright test stays skipped.
  - flake8 fails: 135 errors in battery_monitor (mostly 2-space indent, double quotes) and 496 in ti_ros2_driver (double quotes, long lines, multiple statements per line).
  - So either reformat both packages or delete `test_flake8.py`, as was done for maincar.

**Build warnings**
- **CMake** — "Compatibility with CMake < 3.10 will be removed":
  - Packages: aav_bringup, aav_description, aav_interfaces, aav_localization, aav_mux, aav_navigation, aav_sensors, aav_teleop, yahboom_imu_cpp (and the parked CMake packages).
  - Where: in `log/build_2026-10-09_22-43-29/<pkg>/stderr.log`, not in `log/latest_build`, because CMake didn't re-configure in that build.
  - Fix: `CMakeLists.txt:1` `cmake_minimum_required(VERSION 3.8)` → `cmake_minimum_required(VERSION 3.10)`.
- **setuptools** — "Unknown distribution option: 'tests_require'" in battery_monitor and ti_ros2_driver: same fix as above.
- There were no compiler warnings.
- Also clean:
  - no `distutils`, `imp` or `pkg_resources`;
  - no APIs removed in NumPy 2;
  - no Python 3.12 SyntaxWarnings (104 files compiled);
  - no dash keys in any `setup.cfg`.

**4. Languages** (files / lines; build output, `.pixi`, `.git` and caches excluded)

| Language | Files | Lines | Where |
|---|---|---|---|
| Python | 105 | 6,775 | our ROS packages 2,927; inherited 2,288; parked 715; `tools` 686; `firmware/can` 130; legacy firmware helpers 29 |
| C++ (.cpp/.cc/.hpp) | 29 | 3,605 | object_detection 1,654; Pico 2 sentinel 1,044; ESP32 536; IMU driver 235; Flutter Linux runner 136 |
| C/C++ headers (.h) | 12 | 230 | ESP32 159; object_detection 53; Flutter 18 |
| Arduino (.ino) | 2 | 271 | wheel_encoder_pico2 |
| Rust | 8 | 1,372 | `firmware/spine` |
| Dart | 10 | 2,088 | `hud/flutter_pi` |
| CMake | 16 | 664 | our 8 packages 87; IMU 39; parked 114; Flutter 242; Pico SDK 182 |
| XML | 24 | 649 | 22 `package.xml`, 2 Nav2 behaviour trees |
| xacro / SDF | 2 / 2 | 225 / 189 | aav_description / aav_gazebo worlds |
| YAML | 28 | 1,219 | ROS parameters 824; `docs/interfaces.yaml` 256; Flutter 132; yolo 7 |
| RViz config (YAML) | 7 | 1,329 | object_detection 1,165; ours 164 |
| TI radar .cfg | 16 | 712 | ti_ros2_driver |
| INI | 16 | 296 | `setup.cfg`, camera .ini, `platformio.ini` |
| ROS .msg / .action | 3 | 79 | aav_interfaces, lane_geometry |
| DBC | 1 | 90 | `firmware/can/aav.dbc` |
| Shell | 8 | 149 | `tools` 74; `hud/scripts` 75 |
| TOML | 3 | 90 | `pixi.toml`, 2 `Cargo.toml` |
| Markdown | 39 | about 3,300 | mostly `docs/` (being edited) |

- **Small:** SVG 4/398, CSS 1/151 and MATLAB 1/85 in `docs/`; HTML 1/38 and JSON 1/35 in the Flutter web folder; udev rules 1/23.
- **Binary:** 2 PGM maps and 1 OctoMap `.bt` file.
- **Generated, not counted:** `pixi.lock` 52,328 lines, `pubspec.lock` 682, `test_vectors.json` 184, `Cargo.lock` 7.
