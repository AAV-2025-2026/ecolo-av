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
- `package.xml`
- `resource/aav_radar_ti`
- `setup.cfg`
- `setup.py`
- `test/test_copyright.py`
- `test/test_flake8.py`
- `test/test_pep257.py`
- `aav_radar_ti/TI.py`
- `aav_radar_ti/__init__.py`
- `aav_radar_ti/benchmark.py`
- `aav_radar_ti/mock_radar_publisher.py`
- `aav_radar_ti/pc_publisher.py`
- `aav_radar_ti/plotheatmap.py`

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
  - `pc_publisher.py`, `obstacle_extractor.py` (since removed), `mock_radar_publisher.py`: a clean exit
    on `ExternalShutdownException` too (Jazzy).
  - `launch/6843aop_*.launch.py` (since removed): the same ports and frame; comments on
    their own lines.
- `setup.py`: `tests_require` -> `extras_require={'test': ['pytest']}` (setuptools 79
  ignores `tests_require`, so colcon ran no tests and failed).
- `package.xml`: `ros2launch` -> exec_depend `launch`, `launch_ros`, `ament_index_python`.
- Still needed before the radar feeds a costmap:
  - Out-of-box mode remaps axes to x forward / y left; 3D-tracking mode leaves x right /
    y forward (see `TI.py`'s two parsers).
  - The cfg files are indoor demos (9 m range, 10 Hz).
- 25 Oct 2026: added `README.md` (EGM sections: Overview, Interface, Invariants, Side
  Effects, Verification) and `CLAUDE.md`. Docs only: no inherited file changed.

## Changes (2026-10-26)

Removed what nothing outside `archive/` used (the naming and cleanup audit,
`docs/designs/2026-10-26_naming-and-cleanup.md`):

- `ti_ros2_driver/obstacle_extractor.py` and its `setup.py` entry point: `aav_radar_clusters`
  (Rust) clusters the radar's points now.
- The five launch files, `launch/6843aop_3d_tracking.launch.py`, `6843aop_HeatMap`,
  `6843aop_base`, `6843aop_with_obstacles` and `mock_obstacle_demo`: the 2025-26 team's
  demos, on the old topic names. `aav_sensors`' `sensors.launch.py` starts the driver.
  `setup.py` no longer installs `launch/`.
- `package.xml`: `geometry_msgs` (only the extractor used it), `launch` and `launch_ros`
  (only the launch files did).

Kept, because something uses them: `pcl_pub` (`pc_publisher.py`), `TI.py`, `cfg/`;
`benchmark.py` and `plotheatmap.py` (`pc_publisher.py` imports both); and
`mock_radar_publisher` (`aav_radar_clusters`' `radar_clusters.launch.py mock:=true`).

## Renamed (2026-10-26)

- The package `ti_ros2_driver` is `aav_radar_ti` (`aav_<kind>_<maker>`,
  `docs/conventions.md`): its folder, its module (`ti_ros2_driver/` -> `aav_radar_ti/`),
  `resource/` marker, `package.xml`, `setup.py`, `setup.cfg`, and
  `pc_publisher.py`'s `get_package_share_directory('aav_radar_ti')`. The paths in the
  list above are the new ones. `pc_publisher.py`'s and `benchmark.py`'s default debug
  path say `src/aav_radar_ti/debug/result.json`.
- Only names change: the executables (`pcl_pub`, `mock_radar_publisher`), the nodes and
  the topics stay.
