# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/Nav_Radar @ main (6242631882), src/ti_ros2_driver.

Files, unchanged unless listed under Changes:

- `cfg/3d_tracking_high_detection.cfg`
- `cfg/3d_tracking_indoor.cfg`
- `cfg/3d_tracking_low_noise.cfg`
- `cfg/AOP_6m_default.cfg`
- `cfg/AOP_6m_staticRetention.cfg`
- `cfg/AOP_6m_tracking_default.cfg`
- `cfg/AOP_9m_default.cfg`
- `cfg/AOP_9m_sensitive.cfg`
- `cfg/ISK_14m_extended.cfg`
- `cfg/ISK_6m_default.cfg`
- `cfg/ISK_6m_staticRetention.cfg`
- `cfg/ISK_6m_staticRetention_45deg.cfg`
- `cfg/ODS_6m_default.cfg`
- `cfg/ODS_6m_staticRetention.cfg`
- `cfg/RADheatmap.cfg`
- `cfg/base.cfg`
- `cfg/rules.txt`
- `launch/6843aop_3d_tracking.launch.py`
- `launch/6843aop_HeatMap.launch.py`
- `launch/6843aop_base.launch.py`
- `launch/6843aop_with_obstacles.launch.py`
- `launch/mock_obstacle_demo.launch.py`
- `package.xml`
- `resource/ti_ros2_driver`
- `setup.cfg`
- `setup.py`
- `test/test_copyright.py`
- `test/test_flake8.py`
- `test/test_pep257.py`
- `ti_ros2_driver/TI.py`
- `ti_ros2_driver/__init__.py`
- `ti_ros2_driver/benchmark.py`
- `ti_ros2_driver/mock_radar_publisher.py`
- `ti_ros2_driver/obstacle_extractor.py`
- `ti_ros2_driver/pc_publisher.py`
- `ti_ros2_driver/plotheatmap.py`

## Changes (2026-10-09)

- `package.xml`: declared python3-serial, python3-numpy, python3-scipy and python3-matplotlib,
  which the code imports, so `rosdep install` brings them in on Jazzy.

## Changes (2026-10-10)

- All Python restyled to ROS's Python rules (ament_flake8, ament_pep257) with `ruff format` and isort-style import sorting, then the last errors by hand. Formatting only, except where listed:
  - `TI.py`: no more `sudo chmod +777` on the ports: it raises an error that points at
    the udev rules (`tools/udev/99-aav.rules`). Bare `except:` became `except Exception:`
    (or `ValueError` where only that can happen).
  - `pc_publisher.py`: defaults are the installed `cfg/base.cfg` (it was relative to the
    working directory), `/dev/aav/radar_cmd`, `/dev/aav/radar_data` and frame `radar_link`
    (was the typo `ti_mmwaver_0`).
  - `pc_publisher.py`, `obstacle_extractor.py`, `mock_radar_publisher.py`: a clean exit
    on `ExternalShutdownException` too (Jazzy).
  - `launch/6843aop_*.launch.py`: the same ports and frame; comments on their own lines.
- `setup.py`: `tests_require` -> `extras_require={'test': ['pytest']}` (setuptools 79
  ignores `tests_require`, so colcon ran no tests and failed).
- `package.xml`: `ros2launch` -> exec_depend `launch`, `launch_ros`, `ament_index_python`.
- Still needed before the radar feeds a costmap:
  - Out-of-box mode remaps axes to x forward / y left; 3D-tracking mode leaves x right /
    y forward (see `TI.py`'s two parsers).
  - The cfg files are indoor demos (9 m range, 10 Hz).
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.
