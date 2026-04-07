# object_detection

Higher-level perception package for the AAV radar stack. This package sits on top of the raw sensor data published by `iwr6843aop_pub` and is responsible for everything that turns a stream of radar points into meaningful information — filtering noise, grouping points into clusters, tracking objects across frames, and optionally building a spatial map.

Based on and adapted from:  
https://github.com/lightinfection/TI_IWR6843AOP

## What this package does

The IWR6843AOP outputs a raw point cloud — a set of 3D coordinates representing surfaces the radar detected. On its own this data is noisy and unstructured. This package processes that data through a pipeline:

1. **Filter** — removes spurious points caused by noise, multipath reflections, or out-of-range returns
2. **Cluster** — groups nearby points together using DBSCAN so that a cluster represents a single physical object
3. **Track** — follows clusters across consecutive radar frames so you can determine an object's velocity and trajectory in 3D space
4. **Map** *(needs further testing)* — builds a persistent spatial map of clustered detections over time using ICP registration to align new frames to previously seen ones

## Status

| Feature | Status | Notes |
|---|---|---|
| Point cloud filtering | Complete | Both static and dynamic modes fully working |
| 3D object tracking | Complete | Tracking objects across frames fully working |
| DBSCAN clustering | Implemented | Needs further testing before full confidence |
| ICP registration | Implemented | Needs further testing before full confidence |
| Cluster map | Implemented | Needs further testing before it can be relied upon in flight |

## Package structure

```
object_detection/
├── example/
│   ├── dbscan.cpp
│   ├── filter_multi_frames.cpp
│   ├── filter_single_frame.cpp
│   └── test_icp.cpp
├── include/object_detection/
│   ├── cluster/
│   ├── common/
│   ├── filter/
│   └── registration/
├── launch/
│   ├── 3d_tracking.launch.py
│   ├── dbscan_cluster.launch.py
│   ├── dbscan_cluster_map.launch.py
│   ├── filter_for_ti_dynamic.launch.py
│   └── filter_for_ti_static.launch.py
├── map/
│   ├── mmwave.bt
│   └── velodyne.pcd
├── rviz/
├── CMakeLists.txt
└── package.xml
```

## example/

These are standalone C++ programs that test and demonstrate each core algorithm in isolation — no ROS 2 required to run them. They are invaluable for debugging algorithm behaviour without the overhead of a full ROS 2 launch, and for understanding exactly what each stage of the pipeline is doing before integrating it.

### `dbscan.cpp`
Demonstrates the DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm on a raw point set. DBSCAN works by finding dense regions of points and labelling them as clusters, while points that don't belong to any dense region are labelled as noise and discarded.

Two key parameters control its behaviour:
- **epsilon (ε)** — the radius within which a point searches for neighbours. Too large and separate objects merge into one cluster; too small and a single object splits into many.
- **minPts** — the minimum number of neighbours a point needs within ε to be considered a core point. Raising this makes the algorithm more resistant to noise but may miss sparse detections.

Use this example to tune ε and minPts for your environment before deploying.

### `filter_single_frame.cpp`
Demonstrates point cloud filtering on a single radar frame. The filter removes points that fall outside a defined region of interest (by range, azimuth, elevation, or intensity threshold) and applies statistical outlier rejection to remove isolated noise points.

This is the starting point for understanding what raw IWR6843AOP data looks like and what a cleaned frame should look like after filtering.

### `filter_multi_frames.cpp`
Extends single-frame filtering to accumulate and filter across multiple consecutive radar frames. Because the IWR6843AOP has relatively sparse returns per frame, accumulating several frames before processing significantly improves detection reliability — particularly for slow-moving or stationary objects.

This example shows how frames are buffered and merged before the filter and clustering stages run.

### `test_icp.cpp`
Demonstrates Iterative Closest Point (ICP) registration — the algorithm used to align two point clouds by finding the rigid transformation (rotation + translation) that minimises the distance between corresponding points. In this package ICP is used to align newly detected clusters against a reference map so that the map can be built incrementally.

Use this example to understand ICP convergence behaviour and to test registration quality with your actual radar data before enabling the cluster map pipeline.

## include/object_detection/

C++ header files organised by algorithm domain. Each subfolder corresponds to one stage of the processing pipeline.

### `cluster/`
Headers for the DBSCAN clustering implementation. Defines the data structures for points, clusters, and the DBSCAN class itself. If you need to change how clusters are formed — for example adding a height dimension constraint so the radar doesn't merge objects at different elevations — this is where those changes go.

### `common/`
Shared utility headers used across all pipeline stages. Includes common data type definitions (point structs, frame containers), mathematical helpers, and any constants shared between filter, cluster, and registration modules. If you add a new data type that multiple pipeline stages need to share, define it here.

### `filter/`
Headers for the point cloud filtering stage. Defines the filter parameters struct (range limits, angle limits, intensity thresholds) and the filter class interface. Changing filter behaviour — for example adding a Doppler velocity filter to reject stationary clutter — starts here.

### `registration/`
Headers for the ICP registration module used in cluster map building. Defines the registration interface, the map data structure, and the convergence criteria. If the cluster map is producing drifting or misaligned results during testing, the ICP parameters exposed through these headers are the first place to look.

## launch/

ROS 2 launch files. Each one starts a specific configuration of the pipeline. All launch files should be run from the **workspace root** after sourcing:

```bash
source install/setup.bash
ros2 launch object_detection <launch_file>.launch.py
```

### `filter_for_ti_static.launch.py`
Starts the point cloud filter tuned for **static scenes** — environments where the sensor and all objects of interest are stationary. Uses tighter filter parameters to reject any points that show Doppler velocity (i.e. treats moving detections as noise). Use this for mapping an empty room or a fixed reference environment.

### `filter_for_ti_dynamic.launch.py`
Starts the point cloud filter tuned for **dynamic scenes** — environments where objects are moving. Relaxes the Doppler filter so that moving objects are retained in the point cloud. This is the correct mode for in-flight obstacle detection.

### `dbscan_cluster.launch.py`
Starts the full filter → DBSCAN cluster pipeline. Publishes clustered detections as ROS messages. Does **not** run tracking or map building — useful for verifying that clustering is working correctly and for tuning ε and minPts on real sensor data before adding tracking on top.

### `3d_tracking.launch.py`
Starts the full filter → cluster → 3D tracking pipeline. This is the primary operating mode for obstacle detection. Tracks objects across frames and publishes object IDs, positions, and velocity estimates. Use this for actual flight testing.

### `dbscan_cluster_map.launch.py`
Starts the full filter → cluster → ICP registration → cluster map pipeline. Builds a persistent spatial map of the environment from radar detections. **Currently in progress** — the pipeline runs but the map output requires further testing and validation before it can be relied upon. Do not use this for flight-critical applications yet.

## map/

Reference data files used by the cluster map pipeline.

### `mmwave.bt`
A behaviour tree configuration file that controls the logic flow of the mmWave cluster map building process — when to add new points to the map, when to trigger ICP alignment, and when to reject a frame as too noisy to integrate. If the map is growing incorrectly or failing to update, the behaviour tree logic here is where to look.

### `velodyne.pcd`
A reference point cloud map in PCD (Point Cloud Data) format, captured using a Velodyne LiDAR. This serves as a ground-truth reference for validating the mmWave-built cluster map — by comparing the radar map against this LiDAR map you can quantify how accurately the IWR6843AOP is reconstructing the environment. This file is not required for normal operation; it is a testing and validation tool only.


## rviz/

RViz2 configuration files for visualising the pipeline output. Load a config to see the raw point cloud, filtered cloud, cluster markers, tracked object bounding boxes, and map data all overlaid in 3D.

```bash
rviz2 -d src/object_detection/rviz/<config>.rviz
```

If you add new ROS topics to the pipeline, add the corresponding RViz displays to the config file here so future developers can see them without manual setup.

## CMakeLists.txt

Defines how the package is compiled. Specifies the C++ standard, finds ROS 2 and third-party dependencies, lists all source files to compile, and defines the install targets so colcon knows what to put in `install/`. If you add a new `.cpp` source file to the package you must register it here or it will not be compiled.

## package.xml

The ROS 2 package manifest. Declares the package name, version, maintainer, license, and all build and runtime dependencies. If the package fails to build due to a missing dependency, add it here and re-run `colcon build`. This file is also what ROS 2 uses to resolve the package by name — the name declared here must match the folder name.


## Dependencies

- **`iwr6843aop_pub`** — must be running and publishing point cloud data before any launch file in this package will produce output
- **ROS 2 Humble** or later
- All specific ROS 2 and system dependencies are declared in `package.xml`

## For future developers

- **Point cloud filtering and 3D tracking are the only fully complete and validated features.** Everything else — DBSCAN clustering, ICP registration, and the cluster map — is implemented and functional in controlled conditions but has not yet been tested enough to be fully trusted
- If clustering is producing too many false positives in a new environment, start with `dbscan.cpp` in `example/` to retune ε and minPts offline before changing the live pipeline
- If the filter is dropping real detections, run `filter_single_frame.cpp` on a recorded bag file and inspect the output before adjusting filter parameters in `include/object_detection/filter/`
- The cluster map (`dbscan_cluster_map.launch.py`) is the furthest from complete. The ICP alignment works in controlled tests but has not been confirmed reliable across all flight environments. Do not use this for flight-critical applications until it has been tested across multiple sessions with varying object densities and sensor orientations
- The `velodyne.pcd` in `map/` is your ground truth — use it to score the radar map accuracy quantitatively before signing off on the cluster map feature
