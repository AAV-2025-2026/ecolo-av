# Our own navigator

Ben, 8 Nov: move off Nav2 **one piece at a time**, each beside Nav2 until it wins. The
order: the costmap ([done](own-costmap.md)), the planner ([done](own-planner.md)), then
**the navigator** (this page), the last piece. Nav2 stays the default, and on the car.

> **The short version**
> - **Switch:** `navigator:=own`. Package `aav_navigator` (Rust).
> - **What it is:** what Nav2's `bt_navigator`, our behaviour trees and
>   `waypoint_follower` do for the car, as one state machine.
> - **Drop-in:** Nav2's four actions, under `/drivers/nav/navigator/`. Each goal sender
>   has a `navigator` switch.
> - **All ours:** `navigator:=own planner:=own costmap:=own tracker:=mppi_lag`. Then no
>   Nav2 server navigates.
> - **Scores:** below.

## How it fits

```
goal senders ──▶ navigator (ours) ──ComputePathToPose──────────▶ planner (ours or Nav2's)
 RViz, map,          │            ──ComputePathThroughPoses────▶
 street_router,      │            ──FollowPath─────────────────▶ mppi_lag (or controller_server)
 language_drive,     │            ──ClearEntireCostmap─────────▶ costmaps (ours or Nav2's)
 the tools           └──────────── /drivers/nav/navigator/status
                                   mppi_lag ─▶ velocity smoother ─▶ collision_monitor ─▶ twist_mux
```

The safety locks, collision_monitor and twist_mux never change.

| Action (ours) | Nav2's | Used by |
|---|---|---|
| `/drivers/nav/navigator/navigate_to_pose` | `/navigate_to_pose` | the tools, sim-check, RViz (`/goal_pose`) |
| `/drivers/nav/navigator/navigate_through_poses` | `/navigate_through_poses` | anyone with several poses |
| `/drivers/nav/navigator/follow_waypoints` | `/follow_waypoints` | map waypoints |
| `/drivers/nav/navigator/follow_gps_waypoints` | `/follow_gps_waypoints` | street_router, language_drive |

**Who sends to which.** `vehicle.navigator_action(navigator, name)` gives the name.
`street_router` and `language_drive` have a `navigator` parameter;
`measure controllers --stacks` and `sim-check --navigator` choose by the switch.

## What it does

```
goal ─▶ plan ─▶ follow ─▶ plan again every second
          │        │        (near the goal: keep the path, TODO 17)
          ▼        ▼
   clear global  clear local      ◀── a failure a recovery can fix
          └────────┴─▶ in turn: clear both ─▶ wait 5 s ─▶ back up 1 m (reversing only)
                       up to 6 times, then give up with Nav2's error code
```

| Step | Ours | Nav2's trees |
|---|---|---|
| plan | every 1 s (through-poses 3 s) | the same |
| the final approach | keep the path within 8 m of the goal, under 20 s old | the same |
| a failed replan, while driving a good path | keep driving; give up after 4 in a row | stops the car at once |
| through-poses | drop a pose within 1 m, **or once passed along the path** | within 1 m only |
| waypoints, GPS waypoints | **one through-poses goal**: no stop at each | stop and face each one |
| recoveries | clear, wait, back up, in turn, 6 at most | the same |
| lat/lon to the map | navsat_transform's datum (the same UTM steps) | calls `/fromLL` |
| a new goal | replaces the running one, on any action | refused on the other navigator |

Each change is in `ros/drivers/aav_navigator/PROVENANCE.md`.

**What all ours leaves running from Nav2:** `map_server` (the map), the velocity
smoother, and collision_monitor (the command line in front of the safety locks).

## Try it

| To | Run |
|---|---|
| See it | `pixi run sim navigator:=own planner:=own costmap:=own tracker:=mppi_lag reversing:=false` |
| Score all ours against all Nav2 | `pixi run measure controllers --stacks nav2 own --tours lot obstacle --runs 3` |
| The campus route | `pixi run measure controllers --stacks nav2 own --tours fieldhouse --speed 2.5` |
| The graph and a goal | `pixi run sim-check --navigator own --planner own --costmap own --tracker mppi_lag` |
| Test the maths | `cd ros/drivers/aav_navigator && cargo test -p navigator` |

## Scores

Not run yet.

## What's missing

- **On the car:** untested; `car.launch.py` always passes `navigator:=nav2`.
- **No `IsPathValid`** on the final approach: the navigator reads no costmap.
- **Back up** still calls Nav2's `behavior_server` (reversing only; `mppi_lag` can't reverse).
