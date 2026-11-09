# The diffusion planner: a model that draws the path, the lattice as its guard

* **Author:** Ben (the ask), written up 2 Nov 2026
* **Date:** 2026-11-02
* **Status:** 0.3 (Ben, 7 Nov: "We want diffusion"): allowed **on the car as a trial**,
  `car.launch.py diffusion_trial:=true`, 0.5 m/s at most, the guard and every lock as
  always; not yet run on the car. Steps 1-3 done in 0.2; step 4 (the Orin) made ready
  without the Orin: [As built, 0.3](#as-built-03-7-8-nov). Off by default. TODO 78, 83, 133

Ben, 1 Nov: "Diffusion planners: This sounds interesting. Is this using a model to make
this happen. Can we do it", then "lets keep them around like the diffusion path finding.
I want that in." And: "the diffusion I guess that might run on either coreml or tensorrt
so I guess that's just loading a model."

## Overview

**Yes, it is a model.** A diffusion planner starts from random noise and cleans it, in
a few steps, into a path. A small neural network does the cleaning. It looks at the map
round the car and the goal.

**Yes, we can do it**, small and safe:

- it is **one more planner**, `planner:=diffusion`, beside the lattice (a trial);
- it learns by **copying our own planners** (the lattice, Hybrid-A*) in Gazebo first;
- every path it draws is **checked by a guard**. If a path fails, or the model is slow,
  the car gets the lattice's path instead;
- the node is **Rust**; the model file runs on **TensorRT** (Orin) or **Core ML** (Mac),
  through ONNX Runtime.

```text
                         ┌───────────── aav_diffusion_planner (Rust) ─────────────┐
 bt_navigator ──goal──►  │  costmap crop + goal ─► model (ONNX) ─► 16 sample paths │
 (ComputePathToPose)     │                                              │          │
                         │                                         the guard       │
                         │      lattice's path ◄── planner_server      │           │
                         │      (asked at the same time)    pass? ─────┤           │
                         │                                   │ yes     │ no / late │
                         │                         best sample      lattice's path │
                         └───────────────────────────────┬───────────────────────────┘
                                                         ▼
                                    the path ─► MPPI ─► collision_monitor ─► mux ─► ego
```

## Analysis

### What a diffusion planner is

| Word | Means |
|---|---|
| Diffusion | train a network to **remove noise** from a path. To plan: start from pure noise, remove a little, many times |
| Flow matching | the same idea with straight lines from noise to path: **fewer steps** (1-10) |
| Step | one call of the network. Fewer steps = faster |
| Sample | one path from one starting noise. Many samples = many different paths (left or right of the building) |
| Guidance | push the samples towards low cost (away from obstacles) while cleaning |
| Teacher | the planner whose paths it copies (imitation learning) |

Why people like it: it gives **several good paths at once** (a left and a right way
round), where a network that outputs one path averages them into a crash.

### Who has built one: the survey

| Name | What | Steps, speed | Trained on | Licence |
|---|---|---|---|---|
| [Diffusion Planner](https://arxiv.org/abs/2501.15564) (Zheng et al., ICLR 2025) | transformer; lanes, 32 cars, the route → the car's path and its neighbours' | 10 (DPM-Solver++), about 20 Hz on an A6000 | nuPlan, 11 million scenes; 8 × A100, 500 epochs | **none** in the [repo](https://github.com/ZhengYinan-AIR/Diffusion-Planner): read only, don't copy |
| [Flow Planner](https://github.com/DiffusionAD/Flow-Planner) (Tan, Zheng et al., NeurIPS 2025) | the same group, flow matching | not stated | nuPlan | MIT |
| [DiffusionDrive](https://arxiv.org/abs/2411.15139) (Liao et al., CVPR 2025) | cameras + lidar → path; **truncated**: starts from 20 ready-made path shapes plus a little noise | **2 steps**, 45 FPS on an RTX 4090 | NAVSIM (human driving) | [MIT](https://github.com/hustvl/DiffusionDrive) |
| [GoalFlow](https://arxiv.org/abs/2503.05689) (2025) | flow matching, aimed at a chosen goal point | **1 step** | NAVSIM | [Apache-2.0](https://github.com/YvanYin/GoalFlow) |
| [Diffusion-ES](https://arxiv.org/abs/2402.06559) (Yang et al., CVPR 2024) | sample paths, score them with any cost, mutate the best (evolution) | many calls: slow | nuPlan | **none** in the [repo](https://github.com/bhyang/diffusion-es) |
| [Motion Planning Diffusion](https://github.com/joaoamcarvalho/mpd-public) (Carvalho et al., IROS 2023; [splines version](https://github.com/joaoamcarvalho/mpd-splines-public)) | robot arm and 2D paths among obstacles; cost guidance | tens of steps | **paths from classic planners** (RRT-Connect, then GPMP2) | MIT |
| [Diffusion Policy](https://github.com/real-stanford/diffusion_policy) (Chi et al., RSS 2023) | the 1D U-Net over a path that most of these reuse | 10-100 | robot demos | MIT |

Licences checked on GitHub, 2 Nov 2026 (its licence field, and the files in the repo).

### What this means for us

| Finding | For our car |
|---|---|
| The road ones are trained on **nuPlan or NAVSIM**: city streets, lanes, other cars | our car drives a **parking lot** with a costmap and no lanes. Their weights don't fit. We train our own |
| The big ones need 8 GPUs for days | our job is much smaller: one car, one costmap, no other cars. A **few million weights** (guess) |
| MPD trains on **classic planners' paths** | so can we: the lattice and Hybrid-A* are our teachers |
| 1-2 steps are enough with flow matching or truncation | fast even on a CPU |
| Everyone ranks the samples with a cost | the guard does this too |
| nuPlan's data has its own non-commercial terms | we don't use it |

**What we write ourselves:** the model (a small 1D U-Net, Diffusion Policy's shape), the
training, the guard, the node. We may copy from the MIT ones (with their notice, and a
`PROVENANCE.md`); we read, but don't copy, the two with no licence.

### Our numbers, from the repo

| Thing | Value | From |
|---|---|---|
| Turning radius the planners plan with | 3.59 m (full lock 2.87 m × 1.25) | `vehicle.plan_turning_radius` |
| Reverse speed | 0.5 m/s at most | `vehicle.yaml` `max_reverse_speed` |
| The car's outline | 2.0 × 1.0 m (to measure) | `vehicle.yaml` body |
| Map cells | 0.25 m; the lot is 80 × 60 m | `maps/example_lot.yaml` |
| Replanning | once a second; kept in the last 8 m | the behaviour trees' `RateController hz="1.0"` |
| The lattice's planning time | 10 ms mean, 33 ms worst | `docs/trials.md`, 30 Oct |
| The lattice's lot tour | 16 of 16 legs, 184 s | `docs/trials.md`, 30 Oct |

## Options

### Where it plugs in

| | A. Nav2 planner plugin | **B. Our own path server** | C. Controller level | D. A driver (end-to-end) |
|---|---|---|---|---|
| What | a C++ plugin inside `planner_server` | a node that answers `ComputePathToPose`, as `planner_server` does | replaces MPPI: speed and turn, 20 times a second | publishes `/drivers/ai/cmd_vel` |
| Language | **C++ only** (pluginlib) | Rust | Rust | any |
| Guard | inside Nav2 | **the lattice, asked at the same time** | needs a new one, at 20 Hz | twist_mux and the spine only |
| Rate | 1 Hz | 1 Hz: lots of time | 20 Hz: tight on the Orin | 10-20 Hz |
| Downstream | unchanged | **unchanged**: MPPI, collision_monitor, mux, ego | MPPI gone | Nav2 gone |
| Fits "learned parts inside a layer" | yes | **yes** | yes, but a riskier layer | no: "later" (road to 0.2) |
| Cost | C++ against our rules | small | big | big, and unsafe first |

**B** is the one. Nav2's behaviour trees already let a `ComputePathToPose` node name its
action server (`server_name`, `bt_action_node.hpp`). So the planner swap is one name in the
tree; `planner_server` keeps running with the lattice, for the fallback.

### Its training target

| | DDPM (classic diffusion) | **Flow matching** | Truncated (DiffusionDrive) |
|---|---|---|---|
| Steps to plan | 10-100 | **1-10** | 2 |
| Training | easy | **easy: one simple loss** | needs anchor paths first |
| Export | the network; we loop in Rust | **the network; we loop in Rust** | the same |

**Flow matching**, 10 steps to start, then try fewer. Truncation is a later trial.

### The node's language

| | Python (rclpy + onnxruntime) | **Rust (rclrs + `ort`)** |
|---|---|---|
| The model call | the same C++ library under it | the same C++ library under it |
| The guard: 16 paths × 64 points × the outline's cells, each plan | NumPy, or slow loops | **plain loops, fast** |
| Safety code | dynamic types | **types for metres, radians; no `unwrap`** (our Rust rules) |
| Ben's rule | hot loops in Python: no | yes |
| Our Rust ROS nodes | | `aav_imu_yahboom`, `aav_spine_bridge` already; rclrs 0.8.0 (crates.io, Sept 2026) has **action servers and clients** |

**Rust.** The guard is safety code and the hot loop; Python stays only for **training and
the data generator**, which run offline, not on the car.

## Proposal

### 1. The pieces

| Piece | Where | Language |
|---|---|---|
| The node `aav_diffusion_planner` | `ros/drivers/aav_diffusion_planner/` (a new package, beside `aav_navigation`: "trials beside defaults") | Rust, rclrs |
| The guard and the costmap crop: no ROS | a crate in that package, `diffusion-guard`, tested with `cargo test` | Rust |
| The data generator | `tools/diffusion_data.py` | Python, rclpy, offline |
| Training and export to ONNX | `ros/drivers/aav_diffusion_planner/training/` | Python, PyTorch (BSD-3), in its own Pixi environment `learn`, as `kiss` is |
| The model file (`.onnx`) | not in git: `pixi run get models` | |
| The switch | `planner:=diffusion` in `vehicle.PLANNERS`, **not** in `CAR_PLANNERS` (the car refuses it, as it refuses `smac2d`) | Python, the launch files |

### 2. What the model sees and draws

| In | Shape |
|---|---|
| The global costmap round start and goal, turned to the car's heading | 128 × 128 cells; the cell size fits both ends (0.25 m at least), and is an input too |
| The goal, in the car's frame | x, y, cos θ, sin θ |
| May it reverse? | 0 or 1 |

| Out | Shape |
|---|---|
| 16 sample paths, each 64 points | x, y, cos θ, sin θ, and gear (+1 forward, −1 reverse) |

The node turns the best one into a `nav_msgs/Path` in `map`, as `planner_server` does, so MPPI
can't tell the difference.

### 3. The guard: the simplex part

The review asked for this (road to 0.2: "the simplex guard is named, not designed").
**The clever part draws; the simple part checks; a failed check means the trusted path.**

```text
  16 samples ─► check each ─► any pass? ── yes ─► the cheapest one that passed
                                 │
                                 no, or over 150 ms, or no model ─► the lattice's path
                                                                     (already asked for)
```

**Every sample must pass every check:**

| # | Check | Rule | From |
|---|---|---|---|
| G1 | Numbers | every value finite; points 0.1-0.6 m apart; no jumps | |
| G2 | Start | first point within 0.3 m and 15° of the car | the car's pose |
| G3 | End | last point within the goal checker's tolerance (1.0 m, 0.75 rad) | `nav2.yaml` |
| G4 | Collisions | the car's outline, at every point, on no lethal or inscribed cell; unknown cells refused | the global costmap |
| G5 | Turns | between cusps, every turn ≥ 3.59 m radius (a small tolerance); never under full lock, 2.87 m | `vehicle.plan_turning_radius` |
| G6 | Heading | each point's heading follows its direction of travel (forward, or backward when reversing): no sliding sideways | |
| G7 | Reversing | with `reversing:=false`, no reverse at all. With it: at most 4 cusps and 15 m backwards a path (to tune) | `docs/trials.md`: the U-turn backs up 9 m |
| G8 | Length | no longer than 1.5 × the lattice's path | |

**The cheapest** of the samples that pass: length, plus the costmap's cost along it, plus
a price on each cusp.

**Who switches, and when:**

| Level | Who | What |
|---|---|---|
| Each plan | the node's guard | sample or lattice, every second; never waits for a person |
| Each run | the operator | `planner:=diffusion`, sim and bench only |
| The car | Ben, once it wins | adds it to `CAR_PLANNERS`; until then the car refuses it |
| Always, below it | the classic stack | MPPI's own costmap checks, `collision_monitor`, twist_mux, ego, the spine's watchdog: unchanged |

**Fallback, in detail:**

- The node asks `planner_server` (the lattice) for the same path **at the same time** as
  it runs the model. The lattice takes 10-33 ms, so the fallback is always ready, and each
  plan logs how far apart the two are.
- No model file, a model error, more than **150 ms**, or every sample fails: the lattice's
  path, and `/planning/diffusion/status` says why (`DiagnosticStatus`).
- The lattice fails too: the node returns Nav2's own error (`NO_VALID_PATH`), exactly as
  `planner_server` would. Nav2's recovery runs as it does today.

### 4. Speed: the budget

| Part | Budget on the Orin | Why |
|---|---|---|
| Costmap crop | 2 ms | 128 × 128 cells |
| The model: 10 steps × 16 samples, one batch | **50 ms** | |
| The guard | 10 ms | |
| Total | **under 100 ms** | it plans once a second: 10% of the time |
| Hard stop | **150 ms** → the lattice | the lattice's worst was 33 ms |

**Where the model runs** (one `.onnx` file, through [ONNX Runtime](https://github.com/microsoft/onnxruntime), MIT, and the Rust crate [`ort`](https://github.com/pykeio/ort), Apache-2.0):

| Machine | Runs on | Note |
|---|---|---|
| The Orin | TensorRT or CUDA | `ort`'s `tensorrt` and `cuda` features; its docs list Jetson Orin for CUDA. TensorRT comes with JetPack (NVIDIA's licence, free) |
| Ben's Mac | Core ML | `ort`'s `coreml` feature (Apple's, free) |
| Any laptop, CI | the CPU | a tiny model at 1 Hz should fit even here (to measure) |

So Ben's "just loading a model" is right: one file, a different engine on each machine.

### 5. The data: copying our own planners

**No driving is needed for the first data.** `ComputePathToPose` takes a start
(`use_start: true`), so the generator only runs `map_server`, the costmaps and
`planner_server`, with no Gazebo physics, and asks:

```text
 random map ─► random start and goal (free cells) ─► lattice ─► (map, start, goal, path)
                                                  └─► hybrid ─► (map, start, goal, path)
```

| Item | Plan |
|---|---|
| Maps | the lot, plus about 200 copies with **random boxes** added, so it learns to avoid things, not to remember one lot; 20 held back for the test |
| Pairs | 100,000 to start (MPD-sized). The lattice at 10-30 ms: **about an hour** on one computer |
| Reversing | half with it, half without |
| Kept | the map's name, start, goal, path: small (the crop is made again while training) |
| Later: the car's own drives | bags from `record.sh --lidar`: where the car went, with the end as the goal ("hindsight" goals). After car day |

**Training time (guesses, to measure in step 1):**

| Computer | 100,000 paths, about 100 passes |
|---|---|
| Ben's Mac (M4 Max, PyTorch on Metal, MPS) | a few hours |
| The lab desktop's NVIDIA GPU | under an hour or two |

### 6. How it is scored

The harness we already have, with no new tour:

```bash
pixi run measure controllers --planners lattice diffusion --reversing --runs 3 --tours lot
pixi run measure controllers --planners lattice diffusion --tours obstacle
```

| Number | From | To win |
|---|---|---|
| Legs finished | the harness | 16 of 16, as the lattice |
| Tour time | the harness | under the lattice's 184 s |
| Path tighter than full lock | the harness | 0 m |
| Closest to the box | the harness | no closer than the lattice |
| Planning time, mean / worst | the harness | under 100 / 150 ms |
| **Share of plans from the model** (not the fallback) | new: `/planning/diffusion/status` | 90% or more |
| Guard refusals, by check G1-G8 | new | shows what the model gets wrong |
| Offline: share of samples that pass, on the 20 held-back maps | the training script | 80% or more |

Results go in `docs/trials.md`, as every trial's do. Ben decides a swap.

**Honest note:** copying the lattice, it can at best **equal** the lattice. It gets better
than its teacher only with: paths re-ranked by how fast MPPI really drove them, guidance,
or the car's own drives. Step 1 is for learning how; step 5 is where it may win.

## Steps, smallest first

| Step | What | Done when | Effort (guess) |
|---|---|---|---|
| 0 | Spike: rclrs 0.8 action server answering `ComputePathToPose`; `ort` loading a dummy `.onnx` on the Mac (Core ML) and Linux (CPU) | a fake straight path reaches MPPI in Gazebo | 1 day |
| 1 | The data generator; a tiny flow-matching model that copies the lattice; export to ONNX | offline: 80% of samples pass the checks on held-back maps | 4-5 days |
| 2 | The guard crate (G1-G8, `cargo test`), the node, the lattice fallback; `planner:=diffusion` in sim | the lot tour finishes, whatever the model does | 4-6 days |
| 3 | Scored in the harness, beside the lattice; the share and refusals in its tables | a `docs/trials.md` section | 1-2 days |
| 4 | The Orin: TensorRT (or CUDA), timed (after JetPack 7.2, car Day B) | under 100 ms on the Orin | 1-2 days |
| 5 | Better than the teacher: re-rank by driven time; guidance; car bags | beats 184 s | open |

Each step is its own branch and pull request; each one leaves `pixi run test` green and
the default (the lattice) untouched.

## Risks

| Risk | What we do |
|---|---|
| It remembers one lot instead of learning | random boxes; held-back maps; the guard catches the rest |
| Paths that look fine but the car can't drive | G5, G6; then MPPI and the car's turning radius |
| An `ort` release candidate (2.0.0-rc.15 on 2 Nov) changes | pin the version; step 0 shows if it works on all three |
| TensorRT on JetPack 7.2 isn't ready in ONNX Runtime | CUDA, or the CPU: at 1 Hz a tiny model may not need TensorRT at all |
| A slow model blocks Nav2 | the 150 ms stop; the lattice already asked |
| Too much work for 0.2 | it's a 0.3 trial (review finding 7); this page only designs it |
| Students think the model drives the car | the docs say it: it only proposes a path; the classic stack checks and drives |

## Open questions

1. **The crop:** one window that fits start and goal (as above), or a fixed 40 m round the
   car with a sub-goal on the lattice's path? The second can't plan long legs alone.
2. **Fallback only, or the lattice's path as an input?** Feeding it the lattice's path
   ("improve this") is easier to learn, but less of a planner of its own.
3. **`ComputePathThroughPoses`** (several goals): the lattice keeps it for now?
4. **The teacher mix:** lattice only, or Hybrid-A* too? Two teachers give two styles; is
   that what we want from the samples?
5. **Where training runs:** Ben's Mac, or the lab desktop (it's also CARLA's and the
   Orin's flashing host)?
6. **Guard limits** G7 (cusps, metres backwards) and the 150 ms stop: the numbers to start
   with?

## As built (2 Nov)

| Part | Where | Status |
|---|---|---|
| The data | `tools/diffusion_data.py`, `pixi run diffusion data` | 45,092 paths on 791 maps, about 30 min on 6 workers |
| The model, training, ONNX | `ros/drivers/aav_diffusion_planner/training/`, `pixi run diffusion train` | 3.9 M weights, 30 epochs in 19.5 min (MPS) |
| The guard | `aav_diffusion_planner/guard.py` (no ROS, `test/test_guard.py`) | G1-G8, `decide()` |
| The node | `aav_diffusion_planner/planner_node.py` | `planner:=diffusion`; the car refuses it |
| The score | `docs/trials.md`, Diffusion, 2 Nov | 4 of 4 legs; 68 % of plans from the model |

### Where it differs from the design, and why

| Design said | Built | Why |
|---|---|---|
| A Rust node (rclrs, `ort`) | **Python** node (rclpy); the model in a child program, the learn environment's ONNX Runtime, as `kiss_icp` does | the model runs in the same ONNX Runtime either way. rclrs 0.8's action server and client are untried in this repo; `ort` downloads its library when it builds, which the car kit's offline build can't. The guard in NumPy: 19 ms for 16 paths. Step 0's Rust spike is still open |
| `/planning/diffusion/status` | `/drivers/nav/diffusion/status` | `planning` isn't one of our areas (`docs/naming.md`); Nav2 is a driver, as `/drivers/nav/track/status` |
| G4: no lethal **or inscribed** cell under the outline | lethal or unknown under the outline (padded as the costmap pads it) | Smac's own rule for a car-shaped footprint. With inscribed cells too, the lattice's own paths failed |
| G5: every turn ≥ 3.59 m (the plan radius) | ≥ 0.95 × full lock (2.73 m), on a circle through points 1 m either side | the teachers' own smoothed paths measure 2.8-3.2 m at their tightest. 3.59 m refused most of them |
| G1: points 0.1-0.6 m apart | no step over 3 × the mean step; checks run on the path made dense (0.25 m) | 64 points over a 50 m leg are 0.8 m apart |
| G6: the model's own headings | each heading from the travel (`window.smooth`) | the model's points wobble and its headings disagree with them: 0.9 % of samples passed; smoothing x, y over 5 points and taking headings from the travel, 36 % |
| A sample failing any check is checked on | one failing G1 or G8 isn't checked further | a long, wild sample took 0.8 s to check |
| A reverse "cusp" is any change of gear | a run of one gear under 0.5 m is noise | the teachers' paths end with such wobbles |
| Teachers: lattice, Hybrid-A* (Q4) | both: 70 % lattice, 30 % Hybrid-A*, half reversing | only the paths the guard accepts are used |

### Open questions, answered for now

| # | Answer (2 Nov) |
|---|---|
| 1 The crop | one window round start and goal (min 32 m a side, 8 m margin), turned to the car's heading |
| 2 The lattice as an input | no: fallback only |
| 3 `ComputePathThroughPoses` | stays with planner_server's lattice |
| 4 The teacher mix | both, filtered by the guard |
| 5 Where training runs | Ben's Mac (M4 Max, MPS): 19.5 min |
| 6 G7 and the stop | 4 cusps, 15 m backwards, 150 ms, as written |

### Found on the way

- **The forward-only lattice backs up.** With `allow_reverse_expansion: false`, 800 of its
  1,871 paths in a sample of the data (43 %) failed the guard, most of them for reversing
  (G7): they begin with 2-4 m backwards. Of all 45,092 teacher paths, the guard refused
  29 %. The car's forward-only default is Hybrid-A*, so the car doesn't meet it; worth a
  look before the lattice is ever used forward only.
- **Late plans.** In Gazebo the model and guard took 130 ms on average, against a 150 ms
  stop: 18 of 135 plans were late (the lattice's). 5 Euler steps: 44 ms a plan, but 60 %
  of plans with a passing sample against 75 %.

## As built, 0.3 (7-8 Nov)

Ben, 7 Nov: "We want diffusion." The work: more plans from the model (73 % in Gazebo on
3 Nov; the design's target 90 %), the U-turn, the Orin, and the car, gated.

### Why the guard refused the model

The 0.2 recipe trained again (44,644 teacher paths on 800 maps, 30 epochs) and scored on
300 held-back plans, 16 samples each:

| Check | Refusals (samples) | What it was |
|---|---:|---|
| G5 turns | **2,197** | the model's points wobble: a circle through points 1 m apart reads a tight turn |
| G4 collisions | 1,152 | the outline over a lethal cell, mostly where the model cut a corner |
| G6 heading | 725 | headings from the smoothed travel, turned sideways at the **reversing cusp** |
| G8 length | 96 | longer than 1.5 × the lattice's |
| G1, G2, G3, G7 | 0-3 | |

The U-turn's cause: one moving average over the **whole** path, across the cusp. It
rounds the cusp into a tight turn (G5) and, at the cusp, the travel's direction swings
round, so the headings there point sideways (G6).

### What changed (the guard's checks did not)

| Change | Where | Why |
|---|---|---|
| **Each gear's run smoothed on its own**, from the model's own gear channel; the cusp stays where it is | `window.smooth(gears=)`, `gear_runs()` | the U-turn's G5 and G6 |
| A sample that fails **only** G5 or G6 is smoothed wider (9 points) and **checked again in full** | `guard.choose(again=)`, `window.smoothed()` | most G5 refusals were wobble, not the route. Nothing is waived: G4 failures are never tried again |
| **More U-turns** in the data: 400 more maps, 60 % of their pairs a goal 4-25 m behind or beside, facing back, reversing allowed (21,420 paths) | `diffusion data --uturn 0.6 --first 800` | the U-turn was the weakest leg |
| **More replans** per path (3 suffixes, not 2) and 40 epochs: 196,124 examples | `diffusion train --suffixes 3` | the car replans from along its path once a second |
| The sampler **encodes the map once**, not 16 times | `training/model.py` `Sampler` | the same paths (within 2e-7), 2.4 times faster: fewer late plans |
| The guard's `densify` and `lookup` vectorised | `guard.py`, `window.py` | 35 → 19 ms a plan (16 samples) |
| Each plan's inputs recorded in the sim, **replayed offline** through any model | `diffusion_record:=`, `pixi run diffusion replay` | the same plans, before and after, without the simulator's load |

### Offline: 300 held-back plans (before → after)

| | 0.2 recipe (before) | 0.3 (after) |
|---|---:|---:|
| Samples that pass every check | 38 % | **63 %** |
| Plans with a passing sample | 77 % | **87 %** |
| Refused by G5 turns | 2,197 | **850** |
| Refused by G4 collisions | 1,152 | 1,053 |
| Refused by G6 heading | 725 | **451** |
| Refused by G8 length | 96 | 111 |
| A passing path's length against the teacher's | 1.00 | 0.99 |

The smoothing alone (the 0.2 model, the new smoothing), on 444 plans recorded in Gazebo
on 7 Nov (a run stalled by the Mac's load, so many plans repeat): plans with a passing
sample **86 → 94 %**, the U-turn's **68 → 86 %**, G5 refusals 1,907 → 1,237.

### In the simulator: the lot tour, reversing on, MPPI (8 Nov)

Our own simulator (`next-0.3`'s default), Ben's Mac, one simulator at a time
(`lockf /tmp/aav-sim.lock`), before and after taken in turns; load 7-15. Runs:
`log/controller-compare/agent106-*` (not in git).

| | Lattice (the default) | Before (0.2 recipe) | **After (0.3)** |
|---|---:|---:|---:|
| Legs finished | 12 of 12 | 12 of 12 | **12 of 12** (and 4 of 4 after the merge) |
| Tour time, each run (s) | 182, 185, 180 | 180, 175, 180 | **171, 175, 175** (175) |
| **Plans from the model** | - | 307 of 397 (**77 %**): 80, 73, 79 % | 343 of 389 (**88 %**): 84, 89, 92 % (92 %) |
| The U-turn ("turn back"), from the model | - | 47 of 117 (**40 %**) | 81 of 112 (**72 %**) (80 %) |
| The lattice's: refused (no sample passed) | - | 67 (17 %) | **25 (6 %)** |
| The lattice's: late (over 150 ms) | - | 14 (3.5 %) | 13 (3.3 %) |
| The lattice's: no model answer | - | 9 | 8 |
| Samples that passed | - | 57 % | **86 %** |
| Refused by G5 / G6 / G4 / G8 (samples) | - | 2,120 / 761 / 556 / 46 | **300 / 208 / 254 / 251** |
| Model and guard, mean | - | 108 ms | 104 ms |
| Tightest planned turn (full lock 2.86 m) | 3.27 m | 3.06 m | 3.06 m |

**The same plans, replayed** (`pixi run diffusion replay`, the 405 plans the "before"
runs recorded, through each model): plans with a passing sample **82 → 91 %**; the
U-turn's **43 → 71 %**; G5 2,204 → 435, G6 828 → 250, G4 637 → 388, **G8 75 → 401**.

- **88 % of plans from the model** over three runs (84, 89, 92 %), 92 % in a fourth
  after the merge: the 90 % target is reached on a quiet machine, not yet on average.
  What's left: 6 % refused, 3 % late, 2 % no answer.
- **The U-turn: 40 → 72 %** from the model, and its leg 44-51 s against the lattice's 51-56 s.
- **Faster than the default**: 171-175 s a tour against the lattice's 180-185 s, every leg,
  never a plan tighter than full lock.
- **G8 (length) rose** (46 → 251 samples): the U-turn data taught longer swings; the
  guard refuses them, and the next sample usually passes. Worth a look before more data.


### The Orin, made ready without it

| Part | What | Where |
|---|---|---|
| Engines | TensorRT (FP16, its engine cached in `models/diffusion/engines/`), then CUDA, then the CPU; the worker falls down the list, never fails a plan for it | `engines.py`, `worker.py`; `diffusion_provider:=` |
| FP16 | `pixi run diffusion export --fp16`: `planner_fp16.onnx` (8.7 MB, against 16 MB), FP16 inside, float32 in and out; the time embedding kept in float32. The same paths within 8e-4 of a half-side (under 2 cm) | `training/model.py` `HalfSampler` |
| Its Python | `diffusion_python:=` (the worker's), so the node can use JetPack's ONNX Runtime with the GPU | `navigation.launch.py`, `car.launch.py` |
| Timing | `pixi run measure diffusion` (or `python3 .../training/measure.py --provider TensorrtExecutionProvider` with any Python that has ONNX Runtime): crop, model, guard, total, each against its budget, OK or OVER | `training/measure.py`; [car day A12](../car-day.md#a12-the-diffusion-planners-trial) |

**The budget** (`engines.BUDGET`), one plan, 16 samples, 10 steps:

| Part | Budget | Ben's Mac, CPU (8 Nov, load 17): mean / 95th, ms |
|---|---:|---:|
| Crop | 2 ms | 0.7 / 1.1 |
| Model | 50 ms | 82.6 / 125.9 |
| Guard | 10 ms | 11.6 / 21.2 |
| Total | **100 ms** (95th percentile) | 94.9 / 141.1 |
| Hard stop | **150 ms**: then the lattice's path | |

### The car, gated

| Rule | How | Tested by |
|---|---|---|
| `planner:=diffusion` refused on the car **without** `diffusion_trial:=true` | `vehicle.check_planner(real, trial)` | `test_vehicle.py`, `test_navigation_launch.py` |
| The switch is for diffusion only | the same | the same |
| **0.5 m/s at most** for ego, Nav2 and the geofence; empty gives 0.5; above it refused | `vehicle.diffusion_trial_speed`, `car.launch.py` | the same, and `test_car_launch.py` (below ego's own 1.0) |
| The guard on, the lattice its fallback | the node, unchanged | `test_guard.py` |
| The locks unchanged | nothing touched below the planner | |

Why 0.5 m/s: walking pace; the car's own reverse limit, so forwards and backwards alike;
at ego's 2 m/s² it stops in 6 cm, plus 15 cm for a 0.3 s stale command. The procedure:
[car day A12](../car-day.md#a12-the-diffusion-planners-trial), test 4.27: the Orin's
timing, then stands, then the ground, with the e-stop person. **Not run.**

## Related

- `docs/designs/2026-11-01_road-to-0.2.md`: the direction (learned parts inside a layer,
  the classic stack as the guard) and review finding 7 (ideas to 0.3)
- `docs/designs/2026-10-28_research-picks.md`, pick 3: Simplex and runtime assurance
- `docs/controllers.md`, Planners; `docs/trials.md`, Planners, 30 Oct; `docs/path-followers.md`
- `docs/history/conversation.md`, 1 November: the diffusion planner
