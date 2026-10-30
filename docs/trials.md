# Trials: new path followers and localizers beside the main ones

Ben, 29 Oct: "We want to make other nodes or plugins that we can test and then replace
the main ones if they work." Each trial runs **beside** today's default, chosen at launch,
and is **scored on the same routes**. It becomes the default only once it wins.

> **The short version**
> - **Trackers** (`aav_track`): pure pursuit, Stanley, LQR, MPC, in Nav2's own chain, in controller_server's place. `tracker:=lqr`.
> - **AMCL** (stock `nav2_amcl`): a particle filter on the map and the lidar, scored against the EKF, never steering. `amcl:=true`.
> - **NDT** (`aav_ndt`, ours in Rust): the lidar matched to a saved lidar map, scored against the EKF, never steering. `ndt:=true`.
> - **Score:** `pixi run controller-compare --trackers pure_pursuit lqr --runs 3`.
> - **Results (29 Oct, Gazebo, 3 runs):** pure pursuit, Stanley and MPC finished every leg; MPPI, RPP and LQR lost legs on the U-turn. AMCL lost itself; the EKF wins. [Results](#results-29-october).
> - **NDT**, 29 Oct: about 1-3 cm off on the lot tour, 2 ms a match (below).
> - The design: `docs/designs/2026-10-29_trials.md`.

## What is on trial

| Trial | Scored against | Switch |
|---|---|---|
| Stanley steering | our pure pursuit | `tracker:=stanley` |
| LQR steering, gains by speed | our pure pursuit | `tracker:=lqr` |
| MPC steering, within the steering's limits | our pure pursuit | `tracker:=mpc` |
| our pure pursuit (the control) | Nav2's RPP and MPPI | `tracker:=pure_pursuit` |
| AMCL | the global EKF | `amcl:=true` |
| NDT on a saved lidar map | the global EKF, and AMCL | `ndt:=true` (after `pixi run ndt-map drive`) |

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

### 29 Oct, afternoon: AMCL tuned, and why it was lost

Each run: `controller-compare --tours lot --controllers mppi --amcl`, with a bag of the
scan, the truth and AMCL beside it (`ros2 bag record`, not in git). Off = from Gazebo's truth.

**What the bags showed:**

| Suspect | Finding |
|---|---|
| things in the world not in the map | **no**: at the truth, 3 of 83,000 beam ends were over 0.75 m from a wall in `example_lot` |
| the scan's 0.3-2.0 m band vs the 1.5 m walls | **no**: the lidar's beams (15° down to 15° up) cross the band on every wall from ~2.4 to 30 m |
| the odometry | **no**: `ekf_local` within 0.3 % of the distance and 0.5° per 4 m |
| the scan's stamp | small: it fits the truth ~0.07 s earlier (7 cm at 1 m/s) |
| the scan's directions | **a bug, fixed**: each point went to the direction below it, 0.25° clockwise |
| AMCL's motion noise (alpha 0.2) | **the main cause**: ~9° of heading noise per particle per 0.25 m driven |
| AMCL's laser model (z_hit 0.5, 60 beams) | **weak**: a perfect fit scored only ~6x a hopeless one |
| the 0.25 m solid map | **a bias**: a beam on a wall's face lands in the free cell before it; pushing beams into the building scored better than the truth |

**What changed** (each with its reason in `config/amcl.yaml`):

| Step | Change | Leg 1 / leg 2 off, mean (m) | Worst (m) |
|---|---|---|---|
| before | the defaults | 0.69 / 6.98 (lost, 95° off) | 21.1 |
| A | alpha 0.2 → 0.01-0.05; z_hit 0.9, z_rand 0.1; 180 beams; resample every 2nd scan; the scan's directions | 0.54 / 0.86 | 1.68 |
| B | A + sigma_hit 0.4 (as wide as the map's cells) | 0.40 / 0.27 | 0.79 (whole tour) |

B, the whole tour, one run (`log/controller-compare/20261029-110651/`):

| Leg | AMCL off, mean (m) | worst (m) |
|---|---|---|
| a left turn | 0.40 | 0.63 |
| round the building | 0.27 | 0.46 |
| turn back | 0.19 | 0.33 |
| home | 0.47 | 0.79 |

- Never lost. The worst is in the open (leg 1, home): only one wall within 30 m, so
  along the car's way nothing pins it, and the solid map's bias pulls it 0.2 m back.
- **AMCL's own map** (step C): the lot at 0.05 m with each obstacle only its outline
  (`maps/example_lot_amcl.yaml`, [why](../ros/drivers/aav_navigation/maps/README.md#why-amcl-has-a-map-of-its-own)).
  Offline, on these bags, its best-scoring pose is 0.07 m from the truth (0.25 m map:
  0.2-0.3 m). Its run: below.

**Step C: AMCL's own map, sigma_hit 0.2** (`log/controller-compare/20261029-213729/`,
one run, `--tours lot --controllers mppi --amcl`):

| Leg | AMCL off, mean (m) | worst (m) | B's mean / worst (m) | Lost? |
|---|---|---|---|---|
| a left turn | 0.11 | 0.15 | 0.40 / 0.63 | no |
| round the building | 0.06 | 0.12 | 0.27 / 0.46 | no |
| turn back | 0.06 | 0.12 | 0.19 / 0.33 | no |
| home | - | - | 0.47 / 0.79 | not scored: the car never moved |

- **C wins: 3-6x closer than B, and it's the default** for `amcl:=true` (sigma_hit 0.2
  in `config/amcl.yaml`; `sim.launch.py` always gives AMCL its own map).
- Heading off: 1° at worst (B: 6°). The first 10 s of leg 1 have no pose yet (AMCL waits
  for 0.25 m of driving), as in B.
- Nav2, not AMCL, failed the last two legs: it gave up on the turn back (status 6,
  collision_monitor stopped it once) and never started home. The Mac was at load ~25 then
  (another worktree's Gazebo). Run it again on a quiet computer for the home leg.
- **A bug found on the way:** until this run AMCL never read its own map. Under
  `sim.launch.py`'s global `use_sim_time`, `amcl.yaml`'s `map_topic: /map` beat the launch
  file's, so the runs at 11:20 and 19:31 (`20261029-112022/`, `-193140/`) were Nav2's 0.25 m
  map with sigma 0.2: 0.5-0.8 m mean, 1.8 m worst, worse than B. That shows 0.4 is right on
  the coarse map, 0.2 only on the fine one. `map_topic` left `amcl.yaml`; the launch test
  checks that nothing the launch file sets is in the file too.
- An earlier try at the same setup (`20261029-213056/`), beside another Gazebo: leg 1 0.08 m
  mean, then AMCL dropped 68 scans (its transforms came late) and published nothing more.
  With the computer this loaded, AMCL's numbers are only worth what its pose count says.

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
