# aav_radar_clusters

## Overview

A Rust ROS node (rclrs). DBSCAN groups the radar's points into objects, and draws a box
round each for RViz. It is a rewrite of the 2025-26 team's C++ `dbscan` node
(`aav_object_detection`), which it replaced on 15 Oct. It gives the same clusters and
boxes, bit for bit, on 94 recorded clouds. `PROVENANCE.md` has the full story.

A Cargo workspace with two crates:

| Crate | Is | ROS? |
|---|---|---|
| `crates/radar-clustering` | DBSCAN, the boxes, and `PointCloud2`'s bytes | no: `cargo test` on any laptop |
| `crates/clusters-node` | the node, binary `radar_clusters` | yes (rclrs 0.8, `ros-env` 0.3) |

colcon builds it through `CMakeLists.txt`, which only runs `cargo build --release --locked`
and installs the binary. So `ros2 run` and launch files treat it like any other node.

## Interface

### Node `radar_clusters`

| In / out | Topic | Type |
|---|---|---|
| in | `/sensors/radar/points` | `sensor_msgs/PointCloud2`, best effort |
| out | `/perception/radar/clusters` | `sensor_msgs/PointCloud2`, reliable: clustered points, coloured, with a `cluster` field; noise left out |
| out | `/perception/radar/cluster_boxes` | `visualization_msgs/MarkerArray`: a DELETEALL, then one CUBE per cluster |

| Parameter | Default | Means |
|---|---|---|
| `eps` | 0.8 m | points this close are neighbours (read-only) |
| `minimum_points` | 15 | neighbours a point needs, itself included, to start or grow a cluster (read-only) |

### Launch

`launch/radar_clusters.launch.py`: the node, plus `mock:=true` (aav_radar_ti's pretend
radar: use `minimum_points:=5` with it) and `radar_rviz:=true` (RViz with
`rviz/radar_clusters.rviz`). Arguments `eps`, `minimum_points`.

### `radar-clustering` crate

| Item | Does |
|---|---|
| `Metres` | a distance in metres |
| `Point` | position (m), intensity, velocity (m/s) |
| `Settings::new(radius, min_points)` | checked settings, or `SettingsError` (`Radius`, `NoPoints`) |
| `cluster(&points, &settings)` | the clusters, in the order found: `Vec<Cluster>` (`members`, `bounds`) |
| `Bounds::of`, `Bounds::padded(BOX_MARGIN)` | a box round the points, 0.1 m larger: `Cuboid` |
| `colour(index)`, `Rgb` | ten fixed colours, easy to tell apart |
| `cloud::read_points(&CloudView)` | the points from a cloud's bytes, or `CloudError` |
| `cloud::write_clusters`, `CLUSTER_FIELDS`, `CLUSTER_POINT_STEP` | the output cloud: x, y, z, intensity, velocity, rgb, cluster (28 bytes a point) |

## Invariants

- `radar-clustering` has no ROS. Logic changes go there, with tests.
- `eps` is a distance in metres. The C++ compared it with the squared distance, so its
  0.8 meant 0.89 m; the test vectors give the Rust sqrt(eps).
- Both outputs keep the input cloud's header: the radar's frame (`radar_link`) and time.
- An empty cloud clears the clusters and the boxes.
- The input is best effort, or nothing matches the radar.
- Rust style: enums and `Result`, no `unwrap` in library code; `cargo fmt` and `cargo clippy` clean.
- `Cargo.lock` is committed; builds use `--locked`.

## Side Effects

- Publishes the two topics above. Stops cleanly on SIGINT, SIGTERM or SIGHUP (`ctrlc`).
- colcon builds into its own `target/` folder in the build directory.

## Verification

```sh
cd ros/perception/aav_radar_clusters && cargo test -p radar-clustering   # no ROS
pixi run build && colcon test --packages-select aav_radar_clusters && colcon test-result --verbose
```

`tools/test.sh` runs the first (with `--locked`); `pixi run test` runs everything.
`tests/cpp_vectors.rs` checks the C++ node's recorded answers. Through ROS:

```sh
pixi run --frozen tools/ros.sh --local python3 \
    ros/perception/aav_radar_clusters/test/capture_cpp_vectors.py --node rust
```
