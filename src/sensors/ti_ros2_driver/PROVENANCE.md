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
- Not changed yet, but needed before the radar feeds a costmap (from the 2026-10-09 survey):
  - frame_id is `ti_mmwaver_0` (typo) and no TF connects it to the car; use `radar_link`
    from aav_description.
  - Out-of-box mode remaps axes to x forward / y left; 3D-tracking mode leaves x right /
    y forward (TI.py:127-130 vs 228-244).
  - On a permission error it runs `sudo chmod +777` on the port (TI.py:34-38); use a udev rule.
  - The cfg files are indoor demos (9 m range, 10 Hz).
