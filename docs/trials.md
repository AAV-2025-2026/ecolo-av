# Trials: new path followers and localizers beside the main ones

Ben, 29 Oct: "We want to make other nodes or plugins that we can test and then replace
the main ones if they work." Each trial runs **beside** today's default, chosen at launch,
and is **scored on the same routes**. It becomes the default only once it wins.

> **The short version**
> - **Trackers** (`aav_track`): pure pursuit, Stanley, LQR, MPC, and `mpc_full` (speed and steering together), in Nav2's own chain, in controller_server's place. `tracker:=lqr`.
> - **AMCL** (stock `nav2_amcl`): a particle filter on the map and the lidar, scored against the EKF, never steering. `amcl:=true`.
> - **NDT** (`aav_ndt`, ours in Rust): the lidar matched to a saved lidar map, scored against the EKF, never steering. `ndt:=true`.
> - **Score:** `pixi run controller-compare --trackers pure_pursuit lqr --runs 3`.
> - **Results (29 Oct, Gazebo, 3 runs):** pure pursuit, Stanley and MPC finished every leg; MPPI, RPP and LQR lost legs on the U-turn. AMCL lost itself; the EKF wins. [Results](#results-29-october).
> - **NDT**, 29 Oct: about 1-3 cm off on the lot tour, 2 ms a match (below).
> - **Afternoon:** LQR rebuilt with a preview (U-turn 2 of 3 in a quiet run; it weaved on a busy Mac), `mpc_full` 10 of 12. [Results](#results-29-october-afternoon-lqr-rebuilt-and-mpc_full).
> - The design: `docs/designs/2026-10-29_trials.md`.

## What is on trial

| Trial | Scored against | Switch |
|---|---|---|
| Stanley steering | our pure pursuit | `tracker:=stanley` |
| LQR steering, gains by speed and bend, with a preview | our pure pursuit | `tracker:=lqr` |
| MPC steering, within the steering's limits | our pure pursuit | `tracker:=mpc` |
| MPC speed and steering together (sets its own speed) | MPC, MPPI | `tracker:=mpc_full` |
| our pure pursuit (the control) | Nav2's RPP and MPPI | `tracker:=pure_pursuit` |
| AMCL | the global EKF | `amcl:=true` |
| NDT on a saved lidar map | the global EKF, and AMCL | `ndt:=true` (after `pixi run ndt-map drive`) |

## Where a tracker sits

```
goal ─► bt_navigator ─► planner_server (Smac Hybrid-A*, replans every 1 s)
              │ FollowPath ("follow_path")
              ▼
   tracker:=none (default)          tracker:=stanley | lqr | mpc | mpc_full | pure_pursuit
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
| `mpc_full` plans its own speed, but within the same limits: cruise, bends, planned braking | it is on trial for the speed too |
| Nav2's own goal and progress checks (nav2.yaml: 1.0 m, 0.75 rad) | the same "done" for all |
| Track in `odom`; each path moved there once | the map pose jumps with GPS |
| Forward only (`reversing:=false`: a tracker is refused otherwise) | the trackers drive forwards only |
| 3 runs each, mean and spread (`--runs 3`) | MPPI is random; one run names no winner |
| Loop time and missed ticks recorded | a slow MPC mustn't look like bad maths |

## Run it

```bash
pixi run sim world:=test_lot reversing:=false tracker:=mpc      # watch one
pixi run sim world:=test_lot amcl:=true                         # AMCL beside the EKF
pixi run controller-compare --trackers pure_pursuit stanley lqr mpc mpc_full --controllers mppi --runs 3
pixi run controller-compare --amcl                              # score AMCL too
pixi run ndt-map drive                                          # NDT's map, once (~6 min)
pixi run controller-compare --amcl --ndt                        # score NDT beside AMCL
```

## Results

Each run's results go here, with its date and its folder in `log/controller-compare/`.

### 29 Oct, 04:00: NDT and AMCL beside the EKF (one run, MPPI, the lot tour)

`controller-compare --tours lot --controllers mppi --amcl --ndt`, on the map
`ndt-map drive` made at 03:55 (169,121 points, 2,450 clouds). Off = from Gazebo's truth.

| Leg | EKF off, mean (m) | AMCL off, mean (m) | NDT off, mean / worst (m) | NDT: clouds with a pose | NDT match, mean / worst (ms) |
|---|---|---|---|---|---|
| a left turn | 0.17 | 0.66 | 0.009 / 0.02 | 100 % | 2.6 / 3.9 |
| round the building | 0.16 | 7.1 | 0.030 / 0.27 | 98 % | 1.7 / 4.7 |
| turn back | 0.18 | 17.7 | 0.017 / 0.37 | 98 % | 1.7 / 4.7 |
| home (Nav2 gave up) | 0.17 | 35.7 | 0.010 / 0.21 | 100 % | 2.2 / 14.0 |

- NDT was never over 1 m off; one LOST and restart from `ekf_global` (turn back).
  Heading off at most 1.0°.
- AMCL lost the car round the building and never found it again: a look at its
  settings is due before it is scored again.
- The last leg wasn't reached: MPPI and Nav2 gave up, with the EKF 0.17 m off, so that is
  not the localizers.
- Match times are this Mac's (M4 Max), not the Orin's. Gazebo's lidar has no sweep; the
  car's does. One run: no spread yet. `covariance_scale` (k) and the score floor are
  not fitted yet.

## Scoring a localizer fairly

| Number | Why |
|---|---|
| off: mean, worst; heading worst | each pose against the truth at its own stamp |
| the same on one 10 Hz grid (each pose held until the next) | one that publishes more often isn't scored on more samples |
| time over 1 m off, or no pose yet; the longest stretch | lost, and how long it took to recover |
| NDT: share of clouds that gave a pose; each match's wall-clock time | simulated time can hide a slow match |

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

## Results, 29 October (afternoon): LQR rebuilt, and `mpc_full`

Branch `trackers-tuning`. Two changes, then the same lot, 3 runs each, forward only.

| Change | What | Commit |
|---|---|---|
| **LQR** | linearised about the path's bend (gains by speed **and** bend), the input is the command's change per tick (so the steering rate is in the design), and a 2 s **preview** of the bends ahead (LQR with preview, Tomizuka) | 8b4dcf23 |
| **`mpc_full`** | plans speed **and** steering over the next 9 m, as one QP a tick, within full lock, the steering rate, the throttle, the brake and the policy's speed limits; it sets its own speed | 2bede5f6 |

**Why LQR swung wide.** The steering needs 1.7 s to go from one lock to the other. The
old LQR only had the bend's steering at the car as feed-forward, so it began each swing
when the bend had already arrived. On the fake car's U-turn at full lock:

| Fake car, U-turn at full lock, 1 m/s | Worst off the path |
|---|---|
| LQR before | 0.80 m |
| LQR with preview | **0.29 m** |
| MPC / pure pursuit | 0.31 / 0.24 m |
| `mpc_full` | **0.14 m** |

### Gazebo, all six (run `log/controller-compare/20261029-152311/`, not in git)

15:23-16:28. **The Mac was busy** (load average 24-30; other helpers' and Ben's runs):
Stanley's runs had sensor-watchdog stops, and LQR's run 1 had 125 planner-loop misses
(the others 1-13).

| Follower | Legs (of 12) | U-turns (of 3) | U-turn time | Tick mean / worst | CPU |
|---|---|---|---|---|---|
| pure pursuit | **12** | 3 | 42 s | 0.2 / 3 ms | 23 % |
| Stanley | **12** | 3 | 41 s | 0.3 / 24 ms | 23 % |
| MPC | **12** | 3 | 48 s | 3.5 / 16 ms | 32 % |
| `mpc_full` | 10 | 2 | 49 s | 2.6 / 13 ms | 30 % |
| MPPI (Nav2) | 10 | 2 | 80 s | - | 18 % |
| LQR | 6 | 1 | 45 s | 0.35 / 3 ms | 26 % |

Off the path, mean: 0.08-0.16 m for every follower.

### LQR and pure pursuit alone (run `log/controller-compare/20261029-041845/`)

04:18, load average 17-21 at the start. **LQR 10 of 12 legs, the U-turn 2 of 3** (was 8
and 1 of 3 at 02:42); pure pursuit 12 of 12 (its U-turn 3 of 3). LQR's failed
U-turn was the planner's clockwise loop, to the south wall.

### What it shows

- **The preview fixed what it was for**: on the fake car, and in the quiet run. In the
  busy run LQR lost legs it used to make: run 1 was starved, run 2 **weaved** (heading
  swinging ±0.5 rad round the building). The fake car with the car seen 0.2 s late
  doesn't weave (a new test), and the design keeps 15 ticks of delay margin at 1 m/s. So
  the cause is still open: see the questions.
- **`mpc_full` drives the whole A-to-B**: the same times as MPC, with its own speed. At
  1 m/s it hardly slows for the U-turn (0.92 m/s at least): over distance, at that speed,
  the steering can swing in time, so its model sees no gain in going slower. At 2 m/s on
  the fake car it slows to 1.4 m/s to swing the steering (the bend alone allows 1.7).
- Every U-turn, any follower, drives 2-5 m wider than the planner's first loop: the planner
  replans every second from where the car is, and each new loop starts a little further
  on. A planner setting, not a tracker one (open).
- MPC and `mpc_full` stay inside a 20 Hz tick in Python (worst 16 ms on a busy Mac).

**Open questions**

1. LQR's weave in Gazebo: rerun on a quiet Mac, then log `/drivers/nav/track/status`
   (its preview and feed-forward) to see if the path's jagged curvature drives it.
2. `mpc_full` slows only when its model says the steering can't keep up. Should it also
   value slowing for the U-turn at 1 m/s (a cost on the steering's rate per second)?
3. The planner's growing loops: replan less often in a U-turn, or keep the old path?
