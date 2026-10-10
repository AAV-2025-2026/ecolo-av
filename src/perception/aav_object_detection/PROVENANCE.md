# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/Nav_Radar @ main (6242631882), src/object_detection.
Original author: Gyro (2025-26 team).

Files, unchanged unless listed under Changes:

- `CMakeLists.txt`
- `example/dbscan.cpp`
- `example/filter_multi_frames.cpp`
- `example/filter_single_frame.cpp`
- `example/test_icp.cpp`
- `include/object_detection/cluster/dbscan.hpp`
- `include/object_detection/cluster/eu_cluster_extractor.hpp`
- `include/object_detection/common/PointTI.h`
- `include/object_detection/common/boundingbox.hpp`
- `include/object_detection/common/param.h`
- `include/object_detection/filter/box_filter.hpp`
- `include/object_detection/filter/difference_of_normals_filter.hpp`
- `include/object_detection/filter/passthrough_filter.hpp`
- `include/object_detection/filter/radius_outlier_removal.hpp`
- `include/object_detection/filter/statistical_outlier_removal.hpp`
- `include/object_detection/filter/voxelgrid.hpp`
- `include/object_detection/registration/icp.hpp`
- `launch/3d_tracking.launch.py`
- `launch/dbscan_cluster.launch.py`
- `launch/dbscan_cluster_map.launch.py`
- `launch/filter_for_ti_dynamic.launch.py`
- `launch/filter_for_ti_static.launch.py`
- `map/mmwave.bt`
- `package.xml`
- `rviz/3d_tracking.rviz`
- `rviz/mmwave_multi_frames.rviz`
- `rviz/mmwave_multi_frames_dbscan.rviz`
- `rviz/mmwave_single_frame.rviz`
- `rviz/mmwave_single_frame_dbscan.rviz`

## Changes

- 2026-10-10: `CMakeLists.txt` `cmake_minimum_required` 3.8 -> 3.10.
- 2026-10-10: brought in from parked as `aav_object_detection` (the name in
  docs/conventions.md).
  - The package and the CMake project are renamed; the launch files' package names follow.
    The header folder keeps its name, `include/object_detection`, so the code is unchanged.
  - `CMakeLists.txt`: C++14 -> C++17 (PCL 1.15 and rclcpp need it); the style tests are
    dropped (ament_lint_auto would fail on the inherited code).
  - `include/object_detection/common/PointTI.h`: `struct EIGEN_ALIGN16 PointTI { ... };`
    instead of `struct PointTI { ... } EIGEN_ALIGN16;`, and `PCL_MAKE_ALIGNED_OPERATOR_NEW`.
    Today's Eigen makes EIGEN_ALIGN16 an `alignas`, which can't follow the struct.
  - `package.xml` is rewritten with the real dependencies (visualization_msgs, octomap,
    eigen, ti_ros2_driver) and the team as maintainer.
  - New: `launch/radar_clusters.launch.py`, the DBSCAN node on our topics (/radar/points in;
    /radar/clusters and /radar/cluster_boxes out), with mock radar points for testing.
