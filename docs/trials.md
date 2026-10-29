# Trials: new path followers and localizers beside the main ones

Ben, 29 Oct: "We want to make other nodes or plugins that we can test and then replace
the main ones if they work." Each trial runs **beside** today's default, chosen at launch,
and is **scored on the same routes**. It becomes the default only once it wins.

> **The short version**
> - **Trackers** (`aav_track`): pure pursuit, Stanley, LQR, MPC, in Nav2's own chain, in controller_server's place. `tracker:=lqr`.
> - **AMCL** (stock `nav2_amcl`): a particle filter on the map and the lidar, scored against the EKF, never steering. `amcl:=true`.
> - **Score:** `pixi run controller-compare --trackers pure_pursuit lqr --runs 3`.
> - **Results (29 Oct, Gazebo, 3 runs):** pure pursuit, Stanley and MPC finished every leg; MPPI, RPP and LQR lost legs on the U-turn. AMCL lost itself; the EKF wins. [Results](#results-29-october).
> - The design: `docs/designs/2026-10-29_trials.md`.

## What is on trial

| Trial | Scored against | Switch |
|---|---|---|
| Stanley steering | our pure pursuit | `tracker:=stanley` |
| LQR steering, gains by speed | our pure pursuit | `tracker:=lqr` |
| MPC steering, within the steering's limits | our pure pursuit | `tracker:=mpc` |
| our pure pursuit (the control) | Nav2's RPP and MPPI | `tracker:=pure_pursuit` |
| AMCL | the global EKF | `amcl:=true` |

## Where a tracker sits

```
goal ─► bt_navigator ─► planner_server (Smac Hybrid-A*, replans every 1 s)
              │ FollowPath ("follow_path")
              ▼
   tracker:=none (default)          tracker:=stanley | lqr | mpc | pure_pursuit
   controller_server (MPPI, RPP)    aav_track's track node; controller_server's own
                                    action is renamed follow_path_unused
              └──────► cmd_vel_nav ◄──────┘
                            │
        velocity_smoother → collision_monitor → /drivers/nav/cmd_vel (twist_mux 20) → ego
```

Nothing after `cmd_vel_nav` changes: the same smoother, stop zone, mux slot, locks and
e-stops.

## Fair rules

| Rule | Why |
|---|---|
| One speed policy for every tracker: RPP's cruise speed, slower in bends, stop by distance | off-path error grows with speed |
| Nav2's own goal and progress checks (nav2.yaml: 1.0 m, 0.75 rad) | the same "done" for all |
| Track in `odom`; each path moved there once | the map pose jumps with GPS |
| Forward only (`reversing:=false`: a tracker is refused otherwise) | the trackers drive forwards only |
| 3 runs each, mean and spread (`--runs 3`) | MPPI is random; one run names no winner |
| Loop time and missed ticks recorded | a slow MPC mustn't look like bad maths |

## Run it

```bash
pixi run sim world:=test_lot reversing:=false tracker:=mpc      # watch one
pixi run sim world:=test_lot amcl:=true                         # AMCL beside the EKF
pixi run controller-compare --trackers pure_pursuit stanley lqr mpc --runs 3
pixi run controller-compare --amcl                              # score AMCL too
```

## Results

Not run yet. Each run's results go here, with its date and a link to its folder in
`log/controller-compare/`.

## Before a winner goes on the car

- Gazebo's map is perfect and its GPS noise simple: **AMCL feeds the EKF only after it
  also wins on a bag from the real lot.** On the car, slam_toolbox's map needs aligning
  to the GPS `map` frame first.
- AMCL publishes only after the car moves (`update_min_d`): parked, few samples.
- The trackers don't read the costmap: MPPI stays for the obstacle tours (design T3).

## Results, 29 October

Gazebo's test lot, 4 legs, 3 runs per follower, forward only, on branch `thursday-29oct`
(6bfd0021), one after another on a Mac. Run `log/controller-compare/20261029-024252/` (not
in git). **Every car number is still a guess** (`docs/measure-the-car.md`), so this ranks
the followers in the sim, not on the car.

| Follower | Legs finished (of 12) | Off the path, mean | Tick, worst | CPU |
|---|---|---|---|---|
| **pure pursuit** (ours, the control) | **12** | 0.11-0.13 m | 0.8 ms | 21 % |
| **Stanley** | **12** | 0.10-0.13 m | 0.8 ms | 21 % |
| **MPC** | **12** | 0.11-0.12 m | 6.3 ms | 28 % |
| RPP (Nav2) | 10 | 0.11-0.14 m | - | 7 % |
| MPPI (Nav2, today's default) | 8 | 0.11-0.14 m | - | 22-30 % |
| LQR | 8 | 0.11-0.12 m | 0.6 ms | 21 % |

**What it shows:**

- On the straight and the easy bends, every follower stays about 0.12 m off the path: steering law isn't what matters there.
- **The U-turn** ("turn back", a 14 m lane, forward only) decides it. MPPI, RPP and LQR got collision_monitor stops near the walls and Nav2 gave up (status 6); the failed U-turn then left the next leg ("home") unreachable, so each U-turn failure counts twice.
- LQR is linearised about driving straight: at full lock it swings wide. A curvature-scheduled LQR or a tighter feed-forward is the next try.
- MPC never missed a 20 Hz tick (2 ms mean, 6 ms worst) in Python.
- `aav_track`'s 21 % CPU is mostly rclpy's executor and TF, not the trackers (0.2 ms a tick).

**AMCL** (`--amcl`, one MPPI run): 0.71 m mean off on the first leg (EKF: 0.16 m), then lost
on the second: 6.9 m mean, 21 m worst. Gazebo's GPS is easy (white noise), so the EKF has the
advantage here; AMCL's settings are untuned. Run `log/controller-compare/20261029-034402/`.

**Next:** tune LQR for the U-turn; AMCL's laser model and particle count; NDT beside both
(`docs/designs/2026-10-29_ndt.md`); then the same table on the car once it's measured.
