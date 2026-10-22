# Maps and position: from the wheels to OpenStreetMap

Written 15 October 2026, for Ben. It answers:

1. What does the local EKF give you?
2. How does it become a position on a real map, with GPS?
3. Where does OpenStreetMap come in?
4. How do costmaps relate to all of it?

> **The short version**
> - **Local EKF:** "how I've moved since I started". Smooth, but it slowly drifts.
> - **Global EKF:** the same, plus GPS. "Where I am on the earth". True, but it can jump a little.
> - The **map frame** is a flat grid in metres, pinned to one GPS point (the **datum**). That's how x/y and latitude/longitude meet.
> - **OpenStreetMap is only in the HUD:** searching places, drawing streets, planning a road route. Nav2 never reads it.
> - **Costmaps** are grids of "how bad is it to drive here". The **global** one is big and coarse (for the whole route). The **local** one is small, fine and live (for what's in front of the car right now).

## 1. Your picture, corrected a little

You said: *"local EKF gives odometry, then you put it on a map and mix it with GPS."*

Close. The mixing with GPS is done by **a second EKF**, not on top of the first one:

```text
 wheels + IMU ──────────────► ekf_local  ──► "odom" position  (smooth, drifts)
 wheels + IMU + GPS(x,y) ───► ekf_global ──► "map" position   (true, may hop)
                    ▲
 GPS lat/lon ─► navsat_transform ─► GPS as x,y in metres
```

- Both EKFs read the raw sensors. Neither reads the other's topic.
- They meet in **TF**, the tree of coordinate frames: `map → odom → base_link`.

## 2. The three frames

| Frame | Think of it as | Who sets it | Good for | Bad at |
|---|---|---|---|---|
| `base_link` | the car itself: on the ground, under the rear axle | the car model | "1 m in front of me" | - |
| `odom` | where the car **started**, today | `ekf_local` | smooth motion, steering | drifts: after 1 km it may be metres out |
| `map` | a fixed grid on the earth | `ekf_global` + GPS | "where am I", plans, goals | can hop when a GPS fix arrives |

A picture of the chain:

```text
   map ──(ekf_global: the GPS correction)──► odom ──(ekf_local: the smooth motion)──► base_link
```

- `ekf_local` says how far the car is from where it started: `odom → base_link`.
- `ekf_global` says how far "where it started" is from the true spot: `map → odom`. That small correction soaks up the drift.
- Chain them and you get the car on the map, still smooth.

## 3. How x/y meets latitude/longitude: the datum

The `map` frame is flat and in metres, but GPS gives latitude and longitude. They're joined at **one point**, the datum.

| Setting | Value | File |
|---|---|---|
| Datum | 45.3860 N, -75.6960 (near Carleton: a **placeholder**) | `src/localization/aav_localization/config/navsat.yaml` |
| Map (0, 0) | = the datum | |
| x axis | east | |
| y axis | north | |

- `navsat_transform` turns each GPS fix into x/y metres from the datum.
- It also answers on request: `/fromLL` (lat/lon → x/y) and `/toLL` (x/y → lat/lon).
- That's how a GPS goal becomes a Nav2 goal.

## 4. Where OpenStreetMap comes in

OpenStreetMap (OSM) is a free map of the world's roads and places. **We use it only in the HUD**, for the person in the seat:

| HUD feature | Uses | Where | In git? |
|---|---|---|---|
| Search "Tim Hortons" | `ottawa.db`: 606,628 named places from OSM | the HUD app | no (51 MB): `pixi run get-hud-map` |
| Draw the street map | a tile server on port 8080 | the dash Pi | no |
| Plan a road route | OSRM (a road router), Ontario's OSM data, port 5001 | Docker on the dash Pi | no |

Then the route reaches the car like this:

```text
 HUD: pick a place ─► OSRM: road route (a line of lat/lon points)
     ─► "lock" the route ─► Nav2: FollowGPSWaypoints
     ─► /fromLL: each point to map x/y ─► Nav2 drives point to point
```

> ⚠️ **Nav2 doesn't know where the road is.** OSRM's points follow the road, but Nav2
> only sees the points, not the road. Between two points it plans across its costmap,
> which today is empty (all free). Staying in the lane is the lane keeper's job
> (`aav_lane_finder`, `aav_lane_geometry`). A lane layer in the costmap would be the next step.

This route path is written (the HUD back end and Nav2's GPS waypoints). It has never run with the real OSRM and tile server, which were on the 2025-26 team's Pi.

## 5. Costmaps: the fine-grained part

A **costmap** is a grid laid on the ground. Each cell holds a cost:

| Cost | Means |
|---|---|
| 0 | free: drive here |
| low to high | near something: OK, but further away is better |
| lethal | a wall or an obstacle: never |
| unknown | not seen yet |

**Inflation** adds a soft band of cost around every obstacle, as wide as the car (2.0 m for us), so a plan for the car's **centre** also keeps its **corners** clear.

### Our two costmaps

| | Global costmap | Local costmap |
|---|---|---|
| Question it answers | "Which way to the goal?" | "What's right in front of me?" |
| Frame | `map` (fixed on the earth) | `odom` (smooth: never jumps) |
| Size | 200 m × 200 m (from the map file) | 20 m × 20 m, moves with the car |
| Cell size | 25 cm | 10 cm |
| Filled from | a map file: `empty` (all free) or `example_lot` | the map, plus live sensors: radar, camera detections (lidar later) |
| Used by | the **planner**: Smac Hybrid-A*, which only plans turns the car can make | the **controller**: MPPI, which steers along the plan |
| File | `src/drivers/aav_navigation/config/nav2.yaml` | the same |

Why the local one is in `odom`: if it were in `map`, every GPS hop would shift the obstacles under the car.

## 6. All the scales, big to small

| Scale | Thing | Cell or step | Job |
|---|---|---|---|
| kilometres | OpenStreetMap + OSRM, in the HUD | road segments | "which streets to take" |
| tens of metres | GPS waypoints | one point every few tens of metres | breadcrumbs for Nav2 |
| 200 m | global costmap | 25 cm | a path the car can drive |
| 20 m | local costmap | 10 cm | dodge what the sensors see |
| a few metres | collision_monitor | its stop zone | last-moment stop, whatever Nav2 thinks |
| centimetres | lane keeping | camera pixels | stay in the lane |

## 7. What works, and what's missing

| Part | Status |
|---|---|
| `ekf_local`, `ekf_global`, `navsat_transform` | ✅ in Gazebo and on the bench. ❌ never on the car |
| Nav2 with both costmaps | ✅ in Gazebo and on the bench |
| Radar and cameras in the local costmap | ✅ on the bench |
| Lidar in the local costmap | ❌ no lidar driver yet |
| The real datum | ❌ a placeholder: set it at the test site |
| The HUD's route → Nav2 | 🔧 written; never run with real OSRM |
| A map of the real test site | ❌ only `empty` and an example lot |
| Nav2 knowing about roads and lanes | ❌ the next big step |

## 8. Try it

| You want to see | Run |
|---|---|
| The two EKFs and the frames | `pixi run sim`, then `pixi run tools/ros.sh ros2 run rqt_tf_tree rqt_tf_tree` |
| The car on the map, live | `pixi run tools/ros.sh ros2 run tf2_ros tf2_echo map base_link` |
| A GPS point as map x/y | `pixi run tools/ros.sh ros2 service call /fromLL robot_localization/srv/FromLL "{ll_point: {latitude: 45.3861, longitude: -75.6959}}"` |
| The costmaps | in RViz (it opens with `pixi run sim`): add `/local_costmap/costmap` and `/global_costmap/costmap` |

More: [Costmaps](docs/costmaps.md), [How it fits](docs/how-it-fits.md), [HUD](docs/hud.md).
