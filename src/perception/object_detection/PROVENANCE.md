# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/Nav_Radar @ main (6242631882), src/object_detection.

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
