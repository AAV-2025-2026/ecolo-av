# Driving from A to B: speed up, drive, slow down, stop

Written 15 October 2026, for Ben. The goal: the car drives in a straight line from point
A to point B, speeding up, holding a speed, slowing down and stopping. This is the KEFC
request's "accelerate / hold / stop" demo, and the first step to GPS point-to-point.

> **The short version**
> - There are **three ways**, from simplest to best. The first two exist today; the third is a small new driver.
> - A straight drive in an empty lot needs **no costmap and no map**: only "where am I" and "where is B".
> - The hard part isn't the driving. It's **knowing where the car is and which way it faces** at the start.
> - Test it on the turtle, then the bench, then Gazebo, then the car on stands, then the car.

## 1. The three ways

| | 1. Scripted drive | 2. Nav2 to a GPS point | 3. A "line driver" (new) |
|---|---|---|---|
| Idea | drive a speed profile: speed up, hold for a distance, stop | give Nav2 point B as latitude/longitude; it plans and steers | drive the straight line from A to B, holding the line, and stop at B |
| Needs GPS? | no | yes | yes |
| Steers to stay on the line? | **no**: wheels straight, it drifts | yes | yes |
| Stops exactly at B? | no: after a distance from the start | yes, within Nav2's goal tolerance | yes |
| Speed profile you choose? | **yes**: acceleration, speed, deceleration | roughly: Nav2's limits (1 m/s, 1 m/s²) | **yes** |
| Exists today? | ✅ `aav_scripted` | ✅ Nav2 + `navsat_transform` | ❌ about a day's work |
| Tested | turtle, bench | Gazebo (goals of 8 m and 9.5 m), bench (40 m) | - |
| Best for | the first drive on the car | point-to-point with obstacles | the demo: predictable and easy to explain |

**Recommendation:** start with **1** on the car on stands, then on the ground. Use **2** for
GPS point-to-point. Build **3** if the demo must stop exactly at B with a chosen speed profile.

## 2. Way 1: the scripted drive (today)

The `scripted_driver` drives a speed profile. It knows how far it has gone from
`/localization/odom/local` (wheels + IMU), not from GPS.

```text
 speed
   ▲      hold
   │    ┌───────┐
   │   /         \
   │  / speed up  \ slow down
   └─/─────────────\────► distance
     A               stop (about B)
```

```bash
ros2 action send_goal /scripted_drive aav_interfaces/action/ScriptedDrive \
  "{target_speed: 1.0, acceleration: 0.5, deceleration: 0.5, hold_distance: 10.0, curvature: 0.0}" \
  --feedback
```

| Field | Means |
|---|---|
| `target_speed` | m/s to hold (negative = reverse) |
| `acceleration`, `deceleration` | m/s², how fast to speed up and slow down |
| `hold_distance` | metres at full speed; 0 = use `hold_time` (seconds) instead |
| `curvature` | 0 = straight. It sets a fixed steering angle; it doesn't correct |

- Any person driving (keyboard, joystick) overrides it at once. Cancel the goal and it slows down and stops.
- **Limits:** with wheels straight but no correction, a slightly-off steering centre makes it curve. Until the KTC-100 gives real steering feedback, expect drift.

## 3. Way 2: Nav2 to a GPS point (today)

Nav2 plans a path from where the car is to B and steers along it.

```text
 B (lat, lon) ─► /fromLL ─► B (x, y on the map) ─► Nav2 plans ─► Nav2 steers ─► stops at B
```

```bash
ros2 action send_goal /follow_gps_waypoints nav2_msgs/action/FollowGPSWaypoints \
  "{gps_poses: [{position: {latitude: 45.38612, longitude: -75.69588, altitude: 0.0},
                 orientation: {w: 1.0}}]}" --feedback
```

- The HUD's route uses this same action.
- On an **empty map** (the default, 200 m × 200 m, all free), Nav2's plan is close to a straight line; the planner only respects the car's turning circle.
- Nav2's speed: up to 1.0 m/s, speeding up at up to 1.0 m/s², slowing near the goal (`nav2.yaml`).
- The radar (and the lidar, later) still fill the local costmap, and collision_monitor still stops for something ahead.

## 4. Way 3: a line driver (proposed)

A small new driver, `/drivers/line/cmd_vel`, next to the scripted one:

| Step | Does |
|---|---|
| 1 | Takes A and B (lat/lon, or map x/y) and a speed profile |
| 2 | Turns them into map x/y with `/fromLL` |
| 3 | Each cycle: where am I on the line from A to B, and how far to B? |
| 4 | Speed from the profile, by **distance left to B**, so it slows down and stops at B |
| 5 | Steering: pure pursuit on the line, a point a few metres ahead on it |

It reuses `speed_profile.py` (the scripted driver's maths). It would be tested on the turtle,
the bench and Gazebo like the others, and slot into twist_mux at the scripted priority.

## 5. "Where am I?" is the hard part

| Question | Answered by | The catch |
|---|---|---|
| Where is A, where is B? | GPS: drive there, record `/sensors/gps/fix` for 30 s, average it | needs a good fix; RTK makes it centimetres |
| Where is the car now? | `ekf_global`: wheels + IMU + GPS | GPS-only is ±1-3 m without RTK |
| **Which way does it face?** | the gyro tracks **turns**, but nothing knows the starting heading | ⚠️ the gap: see below |
| How far has it gone? | `ekf_local`: wheels + IMU | drifts slowly; fine over 10-50 m |

### The heading gap

The IMU's gyro measures **turning**, not **north**. We don't use the magnetometer (it
needs calibrating, and the car's motors upset it). Today the start heading comes from
`start_yaw`, typed in by hand. The options:

| Option | How | Cost |
|---|---|---|
| Park on a marked spot, facing a known way | `start_yaw` from the marks | free; good enough for a demo |
| Drive straight a few metres first | the GPS track gives the heading | a few metres of driving |
| The ZED-F9R's own dead reckoning | it fuses its IMU, wheel ticks and GPS, and outputs a heading | set it up on the receiver |
| Two GPS antennas | the line between them is the heading | a second receiver |

**Recommendation:** a marked start spot for the first demos; then the ZED-F9R's heading.

## 6. Do we need a costmap or a map?

| For | Needs |
|---|---|
| Way 1 (scripted) | nothing: no GPS, no map |
| Way 2 (Nav2) | the empty map (exists) + the datum at the test site + the sensors for obstacles |
| Way 3 (line driver) | the datum, A and B; no costmap. collision_monitor still for safety |
| Later: a route with curbs and lanes | a map of the test site (`tools/make_map.py`), or a lane layer |

To make a map of the test lot: drive the edges, record GPS points, and draw them into a
map with `tools/make_map.py` (it already makes `empty` and `example_lot`).

## 7. Test it, step by step

| # | Where | Run | Proves |
|---|---|---|---|
| 1 | Turtle | `pixi run turtle`, then the scripted goal above | the speed profile and the action |
| 2 | Bench | `pixi run bench`, then the scripted goal; `pixi run bench-check` | the same through the real CAN frames and the spine logic |
| 3 | Gazebo | `pixi run sim`, then the GPS goal above | GPS, both EKFs, Nav2, stopping at B |
| 4 | Car on stands | `pixi run car orin` + `motor_pi`; the scripted goal at 0.3 m/s | the signs, the speed loop, the e-stops |
| 5 | Car, empty lot | scripted at 0.5 m/s, 10 m; then a GPS goal | the real thing, with a safety driver |

## 8. What to do first

| # | Task | Who |
|---|---|---|
| 1 | Friday: find out whether the GPS gives fixes (`ros2 topic hz` on the RTK-Pi) | the team |
| 2 | Pick the test lot; measure its datum | the team |
| 3 | A "mark this spot" tool: average `/sensors/gps/fix` and print lat/lon | small, ours |
| 4 | The line driver (way 3), if the demo needs it | ours, about a day |
| 5 | A Gazebo world shaped like the test lot | ours |
