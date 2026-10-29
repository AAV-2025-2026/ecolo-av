# debug-core

## Overview

The debug HUD's logic, with no ROS and no raylib, so it is tested on any laptop. The
`debug_hud` program (`debug-app`) feeds it the lidar's clouds, the localizers' poses,
`/tf` and every sensor's topic, and draws what it says: the cubes around the car, where
each localizer puts the car, and the panel. Design: `docs/designs/2026-10-29_debug-hud.md`.

```
cloud (lidar_link) --static tf--> base_link --local EKF at the cloud's stamp--> odom
                                                                  |
                                                       cubes (20 cm), a height band each
map-frame layers (EKF global, AMCL, truth, plan) --latest map -> odom from /tf--> odom
```

## Interface

| Module | Holds |
|---|---|
| `config` | `DebugConfig` from `config/debug_hud.yaml` (built in); `Topic`, `Frame`, `Number`, `NODE_NAME` = `debug_hud` |
| `frames` | `Stamp` (ns), `Transform3`, `StaticFrames::lookup` (follows a chain up to base_link), `MapToOdom` |
| `poses` | `PoseBuffer`: 1 s of local EKF poses; `at(stamp)` interpolates, or says `TooOld` / `TooNew` |
| `cloud` | `positions(&CloudView)`: x, y, z from a PointCloud2's bytes |
| `cubes` | `build(points, cloud_to_base, car, stamp, settings)` -> `CubeScan`; `Band` (ground ... higher) |
| `scan` | `place(...)`: a cloud start to finish, or a `ScanError` |
| `orbit` | `Orbit`: the 3D camera; `Mode` chase / follow / free |
| `track` | `TrackStatus::from_values`: aav_track's `/drivers/nav/track/status` |
| `state` | `DebugState`, `Update`, `Localizer`, `Source` (the panel's rows) |

It builds on (path dependencies): [`hud-core`](../hud-core/README.md) (`health`,
`origin`, `vehicle`), [`map-core`](../map-core/README.md) (`geom`, `car`) and
`aav_radar_clusters`' `radar-clustering` (its PointCloud2 reader, with its tests).

## Invariants

- No ROS and no raylib.
- odom frame, z up, metres, radians (REP-103/105). Heights are above base_link: the EKF
  is 2D, so a pitched car tilts the cubes.
- A cloud is placed with the local EKF's pose **at its stamp**, interpolated; outside
  the poses kept, it is dropped (`TooOld`) or retried (`TooNew`).
- Stamps are compared only with stamps, never with a clock (Gazebo's are sim time).
- Map-frame layers need `map -> odom`; without it they are not drawn.
- Over `max_cubes`, the nearest cubes stay and the scan counts the rest (`cut`).
- Rays that hit nothing (inf, NaN) are skipped and counted.

## Side Effects

- None: pure logic on what the caller passes in.

## Verification

```sh
cd ros/hud/aav_hud && cargo test --locked -p debug-core
```

`tools/test.sh` runs it (with `hud-core` and `map-core`).
