# Research ideas: the backlog

* **Author:** Ben (the ask), written up 4 Nov 2026
* **Date:** 2026-11-04; revised 5 Nov after the [EGM review](2026-11-05_egm-review.md)
* **Status:** **a backlog, not a plan.** Nothing here is scheduled by this page. The one
  schedule is in [one car](2026-11-04_one-car.md). None of the twelve new ideas is built.

Ben, 4 Nov: "look at all the research ideas we have and really think about what ones will
help us and what improvements or edge can we bring to this?" and "We should be able to come
up wiht some new novel solutions to stuff.?" Word for word: `docs/history/messages-2026-11-04.md`.

## What's decided

| Rule | From |
|---|---|
| Every algorithm stays. "Drop" is now "not pursued; stays available" | Ben, 5 Nov |
| Each area gets a new best hybrid of our own, from papers, known algorithms and current implementations | Ben, 5 Nov |
| Stock stays the default. Ours challenges it until it wins on the same routes and bags | Ben, 5 Nov |
| One design per area is for later | Ben, 5 Nov |
| First algorithm: how the car stops | Ben, 5 Nov |
| Radar tracking is paused (idea 4) | Ben, 5 Nov |

Ben, 5 Nov: "we want to keep all the algo but we want to create a new best hybrid for each".

Everything else on this page is **proposed; awaiting Ben**: the verdicts, the threads, the
must-have list and every guard in the risk table.

## Our edge

| Advantage | Why it helps | Ideas |
|---|---|---|
| Slow: 1 m/s | a second of thinking costs a metre | 6, 12 |
| One lot, driven many times | memory can stand in for sensing | 2, 3, 10 |
| A winter | wheels slip, the map changes, the lidar sees snowflakes | 2, 7, 10 |
| A person always on the joystick | manual drives can test the autonomy | 1, 9 |
| The trials harness | `measure controllers` scores ideas on the same routes | 5, 9 |
| A safety frame | locks only stop; the lattice guards the diffusion planner | 6, 9 |

The honest line on novelty: at 1 m/s in a lot, the new part is mostly **method** and
**setting**, not new algorithms.

## How each idea was judged

| Test | Question |
|---|---|
| Helps car day | does it make the first drives safer or better measured? |
| Feasible this year | data we will have, no GPU farm, one or two students, a term |
| Credit | **known** / **new-ish** / **new to us** |
| Measurable | one number that says it worked |

## Part 1: the ideas we already had

| Idea | From | Verdict | Why |
|---|---|---|---|
| Autoware's designs in Rust: NDT, MPC steering, the smooth stop, the cubes | pick 1, 28 Oct | **built in part; keep** | NDT and the cubes exist; known methods, ours to own |
| Map the lot with KISS-ICP, locate with NDT | pick 2 | **keep; winter thread** | NDT works in Gazebo, on a map built from Gazebo's truth. A KISS-ICP map is untested |
| A safety argument: Simplex + RSS | pick 3 | **keep; thread 1** | the geofence has RSS; the report needs the case |
| IPM, an AprilTag at B, camera-to-lidar calibration | pick 4 | **calibration: yes. The tag: truth rig** | calibration unlocks distances |
| Learned BEV | pick 4 | **not pursued; stays available** | needs data and GPUs we don't have |
| AMCL | 28 Oct | **not pursued; stays available** | lost itself on the lot tour; a comparison, and an input to the position hybrid |
| Trackers: Stanley, LQR, MPC, `mpc_full` | 29 Oct | **no new ones now; all stay** | inputs to the following hybrid |
| Planners: lattice, smac2d, navfn, theta* | 29-30 Oct | **no new ones now; all stay** | the lattice leads in Gazebo; the car hasn't decided it |
| The diffusion planner | 1-2 Nov | **keep; thread 3's testbed** | "better than the teacher" needs the car's own drives |
| The cubes (`voxels:=true`); VoxelLayer next | 30 Oct | **keep as a trial; diagnose TODO 93 first** | see idea 3 |
| Cubes into objects, with names | 29 Oct | **fold into a tracker, later** | waits for calibration and the radar's bench test |
| One model-based controller | 27 Oct | **fold into thread 1** | identification first |
| Learned state-space (Mamba-style) model | 27 Oct | **fold into thread 1, later** | a residual on the identified model, after hours of logs |
| The talking model (VLM) | TODO 78 | **becomes idea 6** | it may also say STOP |
| A model builds our own algorithms | TODO 96 | **becomes idea 5** | the tuner first; the patch loop as a stretch |
| Plain English driving | 15 Oct | **built; the demo** | no research left in it |
| KISS-ICP into `ekf_local` | 1 Nov | **keep; test on snow and ice** | no win in Gazebo; the point is real wheels that slip |
| CARLA | Q31 | **a tool, not research** | cameras in weather, later |
| UniAD, world models, EMMA, MTR/Wayformer | the 2027-28 list | **not pursued; stays available** | paper ideas, none built; no data or GPUs for them |
| Weak links A (identification + CBF) | 4 Nov | **thread 1** | the CBF filter is **planned, not built** |
| Weak links B (lidar teaches camera) | 4 Nov | **later** | the learned follow-up. With idea 4 paused, B's case is reopened |
| Weak links C (degeneracy-aware NDT) | 4 Nov | **winter thread** | NDT slips up to 0.4 m along parallel walls in Gazebo |

## Part 2: which hybrid each idea feeds

The options in each area are in [one car, section 4](2026-11-04_one-car.md). No winner is
named here. A hybrid wins only by numbers.

| Area | Ideas that feed its hybrid | What they add |
|---|---|---|
| **How the car stops (first)** | 7, 8, 2d | a live braking number; a speed cap; snow's deceleration |
| Dead reckoning | 2c, 12 | KISS-ICP when wheels slip; stops that reset the drift |
| Position on the map | 2b, 10, 12, C | a fallback and a guard for when NDT is poor |
| The map | 2, 10 | what changes in snow; what doesn't |
| What's in the way | 2a, 3, 4 (paused) | snowflakes out; memory of what was seen |
| What things are | 6 | a check for what the detector can't name |
| Behaviour and speed | 8 | a cap from how sure the car is |
| The path | 9 | how to run a learned planner behind a guard |
| Following the path | 5 | measured gains |

Reuse for the stopping law: `approach.py` (`aav_drive_to_point`), `dynamics.py`
(`aav_ego`), `geofence.py` (`aav_safety`). The design itself isn't written yet.

Ideas 1, 5 and 11 are also **tools that score** every hybrid, whichever one is built.

## Part 3: the new ideas

### 1. Shadow mode: manual drives test the autonomy

| | |
|---|---|
| What | While a person drives, the automatic drivers keep working. Log what they would have done |
| Why | hours of manual driving, minutes of autonomy |
| New? | **new to us**; known in industry |
| Not free | twist_mux doesn't do this by itself (table below) |
| Test | a "would have stopped" list the team reads after each drive |
| Don't score by | disagreement alone: a person's drive isn't truth, so it can't show quality |
| Try first | offline replay of bags: no live Nav2, nothing can reach the car |
| Rejected because | "every driver at once": only one follower runs at a time |
| Risks | R3, R10 |
| Size | a week for logging and a script; a live mode is more. Design: [shadow mode](2026-11-05_shadow-mode.md) |

| What it really needs | Why |
|---|---|
| A lock | when the person lets go, the mux hands over after 0.5 s, so Nav2 would drive |
| Goals | Nav2 publishes nothing without a goal; who sends them on the car is open |
| A way past Nav2's reactions | Nav2 reacts to a car it isn't driving; a stopped person trips its progress check |
| More in `tools/record.sh` | it has no lock topics, cubes, radar or images, and no buttons, replay or AI commands; lidar only with `--lidar` |

Those missing images and costmaps also mean today's bags aren't "demonstrations" for a
learned driver.

### 2. The winter lot

| | |
|---|---|
| What | Treat the Ottawa winter as the setting, not the problem (parts below) |
| Why | the car will meet snow; numbers from a dry lot may be wrong there |
| Today | nothing under `ros/` or `tools/` mentions snow; the sensor guide has one line (`docs/learn-sensors.md:130`) |
| New? | **new-ish**: a low-cost car in one lot, NDT without RTK, the wheel-slip question |
| Already exists | CADC, Boreas, WADS (road vehicles); NCLT (a Segway on a campus, with snow). So it's a niche, not an empty field |
| Test | each number below, **dry against snow** |
| Needs | dry bags before the snow (R11); the site file; truth (idea 11) |
| Rejected because | a learned snow filter: needs labels and training time. DROR and DSOR come first |
| Risks | R1, R4, R5, R6, R11 |
| Size | data days, then three to four weeks of analysis |

| Part | What | The number |
|---|---|---|
| a | snowflakes out of the lidar: DROR (radius grows with range), or DSOR | false cubes per cloud; posts kept |
| b | NDT, KISS-ICP and the EKF on snow; C's guard on bare slopes | drift per 100 m; NDT's error |
| c | wheels against lidar on ice: KISS-ICP's twist into `ekf_local` | drift with and without it |
| d | braking on snow: fit the deceleration again | deceleration, dry and snow |
| e | a small winter dataset with truth | whether it's usable by others |

### 3. Blind-zone memory

| | |
|---|---|
| What | Keep the cubes from the last stretch of travel in `odom`, and publish them with each new cloud |
| Why | a low thing seen from afar stays known once it drops out of the lidar's view |
| Limit | it can't help with something never seen from afar |
| New? | **new to us** |
| Size | a week, after TODO 93's diagnosis. Details and the memory's length: [tracks and memory](2026-11-05_tracks-and-memory.md) |
| Risks | R5, R12 |

The blind zone, from `vehicle.yaml`'s mount today (x 0.49 m, z 1.52 m; it moved **lower and
rearward** on 1 Nov). The lowest beam is 15° down. Range = (1.52 − height) / tan 15°.

| Height of the thing | Last seen, from the lidar | Ahead of the bumper (x 1.8 m) |
|---|---:|---:|
| The road | 5.7 m | 4.4 m |
| 0.3 m (the cubes' floor) | 4.6 m | 3.2 m |
| 0.5 m | 3.8 m | 2.5 m |
| 1.0 m | 1.9 m | 0.6 m |
| Above 1.52 m | never lost | never lost |

This is geometry only. The lidar's tilt isn't calibrated, and the car's body may hide more.
The cubes store nothing under 0.3 m, so kerbs aren't remembered.

| Corrected | What's true |
|---|---|
| "TODO 93 smells like the blind zone" | **an undiagnosed suspicion.** The post is 1.8 m tall, above the lidar, so it never leaves the view |
| "Too few hits, below `min_points`" | a guess. `min_points: 3` belongs to the collision monitor, and with `voxels:=true` it counts cubes. The trial recorded "the stop zone fired, too late" |
| "Only the radar clears it" | wrong. The radar and lidar are separate costmap layers, so a radar ray can't clear a lidar mark |
| Should a radar clear it? | no: the radar sees low things poorly, and a miss would erase a real mark |
| "Good to centimetres" | only without slip. A 17 % wheel error (0.36 or 0.42 m, not yet taped) over 7 m is about 1.2 m |
| "Needs nothing new" | it needs a rule for what's stored and when it expires (below) |

| It must also handle | Why |
|---|---|
| A stopped car | a stopped car never travels, so a travel-only rule holds it forever. It needs a time rule too |
| Moving things | a walker would leave a wall of cubes |
| Snowflakes | R5 |

| Test | Why |
|---|---|
| A new low-box check | `sim-check --lidar-obstacle` uses the 1.8 m post; no low-box flag exists |
| TODO 93 first, then its rerun | a fix needs a known cause |
| **Eight** clean runs | at TODO 93's 1 in 3, three clean runs pass by luck 30 % of the time; eight, about 4 % |

| Option | Verdict |
|---|---|
| Stock `observation_persistence` (0.0 in `nav2.yaml`) | **try first**: one line, and it expires by time |
| VoxelLayer | keep as the trial already planned |
| STVL | rejected: RoboStack has no `osx-arm64` build, and Macs are first-class |

### 4. The radar's own tracker: PAUSED

| | |
|---|---|
| Status | paused (Ben, 5 Nov). No firmware or cfg change on the car |
| The idea | the radar's tracking firmware gives targets with position and velocity |
| Why it's kept | a person (1.4 m/s) outruns the car, and the radar sits where the roof lidar is blind |
| New? | **known**; the shortcut is new to us |
| Risks | R3, R9 |
| Size | unknown until the bench test. "A week" was wrong |

**What must be true before resuming:**

| Must be true | Today | Source |
|---|---|---|
| Firmware | tracking needs `3D_people_track_6843_demo.bin`, not the out-of-box binary | `cfg/rules.txt` |
| Parser | it checks 112-byte records but reads 56 per loop, so every target after the first is misread | `TI.py` |
| Axes | tracking mode leaves the main cloud in TI's axes (x right, y forward). The costmap and stop zone read that cloud, turned 90° | `aav_radar_ti/README.md` |
| Cfg range | the `3d_tracking_*` boxes are 1.5 m deep; `AOP_6m_tracking_default.cfg` has no `trackingCfg` | `cfg/*tracking*.cfg` |
| A moving car | unproven: needs a bench test, then a drive | nothing shows it works |
| Meaning | the target has no class: it's "something moving", not a person | `README.md` fields |

**The no-flash option (proposed; awaiting Ben):** use the out-of-box cloud's per-point
`velocity`, through `aav_radar_clusters`, which already carries it.

| Note on that option | |
|---|---|
| Keeps | the firmware, the axes, the cfg range |
| Must add | subtracting the car's own motion: on a moving car, a still thing shows a velocity too |
| Gives | "something moving" only; no identity |
| Later | a tracker of our own on the cubes, if a gap remains |

### 5. The tuner, then the model that writes algorithms (TODO 96)

| | |
|---|---|
| Step 1 | An optimiser turns a **few** knobs, scored by `measure controllers` overnight |
| Step 2 | A model proposes a code change as a patch; the harness scores it; the best survive |
| Why | every gain in the repo is a guess; a night of tuning is cheap |
| New? | step 1 **known**; step 2 **new-ish** (FunSearch, AlphaEvolve; not on a student car that we found) |
| Rejected because | grid search and hand tuning: too many runs |
| Compare | CMA-ES against Bayesian optimisation, which suits few runs |
| Needs | a quiet machine; a new way to pass parameters: the harness has no flag for it |
| Risks | R2, R10 |
| Size | two weeks for step 1; step 2 a stretch |

| Corrected | What's true |
|---|---|
| "at `sim_speed:=3`" | that's a top speed, not faster time, and it would tune a 3 m/s car. The harness flag is `--speed`. Tune at 1 m/s |
| "A hundred evaluations a night" | about right (a tour is about 186 s), but `--runs 3` is the harness's real comparison, so about 30-50 candidates |
| "MPPI's thirty weights" | `nav2.yaml` has 8 critics; "thirty" isn't confirmed. A night's budget can't fit that many anyway. Start with five or fewer |
| "The stop zone's size" | a safety setting: proposed to leave it out of the tuner |
| "MPPI weaves 1.5 m" | check the cause first: TODO's N7 points at the bench's GPS noise |
| "Wins on bags" | **a bag can't score closed-loop gains**: a recording can't show how the car would respond to other gains |

What a closed-loop winner must pass instead: Gazebo routes it wasn't tuned on, then the car,
with a person on the joystick. Bags do still score perception and localization.

### 6. The VLM that may only say STOP

| | |
|---|---|
| What | A small vision-language model looks at the front picture. Its only power is a lock on twist_mux. It also writes the HUD's sentence (TODO 78) |
| Why | the detector knows its classes; the long tail (a dog, a chain across the lane) is where it fails |
| New? | **new-ish**; VLMs as runtime monitors are a research line (Sinha et al.) |
| Input from that paper | a fast anomaly check first, the slow model only if it fires. Weigh this against one question a second |
| Test | staged scenes: catch rate, false-stop rate, latency measured |
| Rejected because | more detector classes alone: the long tail can't all be listed |
| Risks | R1, R3 |
| Size | three weeks for a trial, once the plumbing below exists |

| Plumbing | What's true |
|---|---|
| `aav_language` | text only, with tools. It sends no pictures |
| Default backend | Apple MLX, and the `llm` feature is Mac-only, so **not on the Orin** |
| Orin route | `llm_openai.py` can talk to a local server (llama-server, for one). Its docs record no run on an Orin |
| Model | a vision model that fits: not chosen |
| Latency | unmeasured. "One second" is a hope |
| Camera stream | works on a Mac; untested on the Orin and Pi (`docs/status.md`) |
| The lock | no such lock exists; the stop sign's is the pattern to copy. What silence means must be chosen |

### 7. The brake-health monitor

| | |
|---|---|
| What | At each braking event: predicted deceleration against measured. A running residual |
| Why | a brake can degrade quietly; this checks "where I will stop" stays true |
| New? | **known** in theory; **new-ish** as a live input to the safety envelope |
| Test | a new Gazebo `brake weak` fault (`sim-fault` covers sensors only). Then a wet lot, measured |
| Compare | a fixed winter margin: simplest, and may be enough |
| Risks | R4, R6 |
| Size | two weeks after identification. Details: [knows itself](2026-11-05_knows-itself.md) |

| Must be solved | Why |
|---|---|
| `pi` first | in `open` the car coasts, so there's no braking wish to compare |
| `pi`'s own needs | a driven-wheel speed (TODO 49b) and braking measured on the ground (test 4.3) |
| Short stops | a stop from 1 m/s lasts about a second or less: few samples |
| The closed loop hides weakness | the loop asks for more brake, so compare the effort too |
| Thresholds | none until there's data; any number now is a guess |
| A lock changes | a growing margin moves the geofence's trip point: a safety decision, not "locks unchanged" |

### 8. Drive as fast as you can trust

| | |
|---|---|
| What | The speed cap follows the least sure module |
| Why | it joins several parts into one sentence: the car drives as fast as it can trust itself |
| New? | **new-ish**, if measured on a real car |
| Test | the cap drops within a second of a `sim-fault`; the clean tour is under 20 % slower |
| Compare | a flat 1 m/s, today's baseline. At this speed the gain may be small |
| Risks | R10 |
| Size | two weeks after the behaviour layer and the signals exist |

| Signal | Exists today? |
|---|---|
| The EKF's spread | yes |
| The detector's confidence | yes |
| NDT's score | only with NDT on |
| A tracker's covariance | no tracker |
| The model's residual | no (idea 7) |
| Latency, as a live number | not confirmed |

| Must be solved | Why |
|---|---|
| Two mechanisms | a cap and the CBF's margins would both act. Choose in the stopping design |
| It reaches Nav2 only | not the point driver or the trackers |
| A cap can't stop the car | Nav2 reads 0.0 as "no limit". The cap needs a floor; a lock makes the stop |
| Numbers | 0.5 and 0.3 m/s are guesses |

### 9. Shielded learning as the method

| | |
|---|---|
| What | Every learned part runs behind a classical guard. Write this up as a method, then try a small learned driver in the AI slot (`/drivers/ai/cmd_vel`, priority 10) |
| Why | Ben, 4 Nov: "we can't use end to end like tesla because we are a school project". A guard makes small learned parts safe to try |
| New? | **new-ish** as a framing with measurements; the parts are known |
| Test | below; a scored drive, not disagreement with the person |
| Rejected because | a learned driver with no guard: nothing can take over |
| Needs | ideas 1 and 5; recorded images (not in today's bags) |
| Risks | R10 |
| Size | a term alongside the others: a stretch |

| Two different guards | What it does |
|---|---|
| The diffusion guard (built) | checks a plan and falls back to the lattice: it can take over |
| The CBF filter (**planned, not built**) | trims a command: it can't take over. Any trim must sit upstream of twist_mux, or it trims people too |

The diffusion numbers (Gazebo, `docs/trials.md`):

| | 2 Nov | 3 Nov |
|---|---:|---:|
| **Share of plans from the model** | 63 % (167 of 267) | 73 % (305 of 418) |
| **The guard's own rate** (passed, of those it judged) | 76 % (167 of 221) | 81 % (305 of 378) |
| Plans too late | 17 % | 8 % |

The share rose 10 points, and 9 of them match fewer late plans, on a less busy Mac. So
"63 → 73 %" isn't a measure of learning. If this becomes the method's metric, use the guard's
own rate, on the same machine load.

### 10. Pole landmarks

| | |
|---|---|
| What | Poles and posts from the lidar, signs from RF-DETR, in a very small map. Locate by matching poles |
| Why | a fallback when NDT's score drops; poles stick out of snow |
| New? | **known** (Schaefer et al., 15 months with a mobile robot in an urban area); **new to us** in a lot, beside NDT |
| Test | error against truth, dry and snow; the switch when NDT is LOST |
| Needs | the first bag; a pole detector (the paper presents one as a contribution, so expect more than "a few lines") |
| Risks | R6 |
| Size | three weeks |

### 11. The truth rig

| | |
|---|---|
| What | A way to know where the car really was, for a scoring day |
| Why | without truth, nothing on the car can be scored |
| New? | **known** |
| Test | against surveyed points, not only tape marks: under 5 cm |
| Risks | R8 |
| Size | a few days, then a scoring day per season |

| Option | Verdict |
|---|---|
| Borrowed RTK receiver or total station | **proposed first choice**, if one can be borrowed |
| Two cameras, crossing views | possible; needs its accuracy measured |
| One tripod camera, two tags | rejected for scoring: good side to side, poor along the view. At 30 m, roughly 1 m or more (a 0.3 m tag, 1000 px lens, half a pixel of error) |

### 12. Stop-and-stare

| | |
|---|---|
| What | Use each stop: a full NDT match, a zero-velocity update, the gyro's bias |
| Why | cheap accuracy each time the car waits |
| New? | **known** pieces (ZUPT); the bundle is ours |
| Test | drift after stops, with and without it |
| Size | a week; fold into localization work |

## Part 4: programme risks

All guards here are **proposed; awaiting Ben**.

| # | Risk | Ideas | Proposed guard |
|---|---|---|---|
| R1 | **Publishing camera data with people and plates:** consent, ethics | 2e, 6 | Ask the university's ethics office before recording for release. Blur or leave out images. Nothing in the public repo |
| R2 | **Unattended model-written patches** | 5 | No network or secrets. `tools/ros.sh --local`, own `ROS_DOMAIN_ID`. Never touch safety code. A person reviews every patch; normal PR |
| R3 | **Staged scenes near a moving car** | 1, 4, 6 | Pictures and bags first. Then props, then a still car. No person in the path of a moving car. A person on the deadman always |
| R4 | **Braking on ice** | 2d, 7 | Empty lot, walking pace, a person on the joystick, room to slide. Hardware lead's OK. Dry numbers first |
| R5 | **Flakes held in memory** | 2a, 3 | The filter runs before the memory. A cube must be seen in several clouds before it's stored |
| R6 | **DROR removes thin posts** | 2a, 10 | Measure posts kept on dry bags. Not on the safety path until measured. Poles read before filtering |
| R7 | **Ice read as a bad brake** | 7, 2d | Grow the margin either way, but report them apart: check slip (wheels against IMU or KISS-ICP). No refusing autonomy on winter data until both are seen |
| R8 | **No truth on the scoring day** | 2, 10, 11 | Book the receiver early. If there's none, say "not scored" |
| R9 | **Radar tracking breaks the safety path** | 4 | Stays paused. Bench first |
| R10 | **Wins in Gazebo, not on the car** | 1, 5, 8, 9 | Gazebo's wheels don't slip. The same test on the car decides |
| R11 | **No dry baseline**: snow comes before the first bags | 2 | Get dry bags at the first chance. If snow wins, score against the next thaw |
| R12 | **The memory stays off the car**: it lives in `voxels:=true`, which TODO 93 keeps away | 3 | TODO 93 first |

## Part 5: capacity

The sizes are guesses. No owners are named: that's for the team.

| Group | Ideas | Weeks (guess) |
|---|---|---:|
| All new ideas, without 4 and 9 | 1, 2, 3, 5, 6, 7, 8, 10, 11, 12 | about 20 |
| Radar, if it resumes | 4 | unknown |
| The learned driver | 9 | a term |
| **The capacity** | one or two students, a term | about 12 per full-time student (an assumption), and capstone isn't full-time |

So **not all of this will happen.** The five picks and Gate 4 (26 Feb 2027) come first.

### Must-have (proposed; awaiting Ben)

| Must-have | Why | Size (guess) |
|---|---|---:|
| Diagnose TODO 93; try `observation_persistence` | a safety bug in a trial we want to use | up to a week |
| Truth for a scoring day (11) | without it, no number counts | days |
| Dry baseline bags (2) | a winter comes once a year | data days |
| More in `record.sh`, one offline score script (1) | every hybrid needs scoring | a week |

That's about three weeks, and the order is the [one car](2026-11-04_one-car.md) schedule's.

| Next, if there's time | Stretch |
|---|---|
| 7, after `pi` and the numbers | 5, 6, 8, 9, 10, 12 |
| 2's snow analysis | 3's full memory, if the stock setting isn't enough |

## Part 6: three threads (proposed; awaiting Ben)

No dates: those are in [one car](2026-11-04_one-car.md).

| Thread | The sentence | Ideas | Report chapter |
|---|---|---|---|
| **1. The car that knows itself** | its numbers measured, with error bars; it notices when they change | A, 7, 8 | the safety case |
| **2. The winter lot** | the same car, the same lot, in snow, measured | 2, C, 10, 11 | localization and perception in winter |
| **3. It learns safely** | every drive teaches it; a guard keeps it honest | 1, 5, 9, 6 | shielded learning |

## Questions for Ben (proposed; awaiting Ben)

| # | Question | Suggestion |
|---|---|---|
| 1 | Is the must-have list right? | yes, as above |
| 2 | Will the winter dataset be public? | decide after the ethics answer; lidar first, no images |
| 3 | May patches run unattended at all? | only with R2's guards; or leave step 2 out |
| 4 | Is the stop zone's size off limits to the tuner? | yes |

## Papers

"Found" means a search on 5 Nov found the title and authors. The contents weren't checked
in full. "**Unchecked**" means not confirmed at all.

| Paper | For | Check |
|---|---|---|
| Charron, Phillips, Waslander, *De-noising of Lidar Point Clouds Corrupted by Snowfall* (DROR), CRV 2018 | 2 | **Unchecked**: seen cited; paper not found |
| Kurup, Bos, *DSOR*, arXiv 2109.07078, with the WADS dataset | 2 | Found |
| Pitropov et al., *Canadian Adverse Driving Conditions Dataset*, IJRR 2021 | 2 | **Unchecked** |
| Burnett et al., *Boreas: A Multi-Season Autonomous Driving Dataset*, IJRR 2023 | 2 | Found; year not confirmed |
| Carlevaris-Bianco, Ushani, Eustice, *NCLT Dataset*, IJRR 2016 | 2 | Found |
| Rosen, Mason, Leonard, *Towards Lifelong Feature-Based Mapping in Semi-Static Environments*, ICRA 2016 | 2, 10 | Found |
| Schaefer et al., *Long-Term Urban Vehicle Localization Using Pole Landmarks Extracted from 3-D Lidar Scans*, ECMR 2019 | 10 | Found |
| Isermann, *Fault-Diagnosis Systems*, Springer 2006 | 7 | **Unchecked** |
| Taylor and Ames, *Adaptive Safety with Control Barrier Functions*, ACC 2020 | 7, 8 | Found |
| Hansen, *The CMA Evolution Strategy: A Tutorial*, 2016 | 5 | **Unchecked** |
| Romera-Paredes et al., *Mathematical discoveries from program search with large language models* (FunSearch), Nature 2024 | 5 | Found |
| Google DeepMind, *AlphaEvolve*, arXiv 2506.13131, 2025 | 5 | Found |
| Sinha et al., *Real-Time Anomaly Detection and Reactive Planning with Large Language Models*, RSS 2024 | 6 | Found |
| Tesla Autonomy Day, 2019 (shadow mode, public talk) | 1 | **Unchecked** |
| The weak links' list: Ames (CBF), Sha (Simplex), Zhang (degeneracy), Hadsell (free space) | threads 1, 2 | **Unchecked** |

## Related

[One car](2026-11-04_one-car.md) (the schedule), [the EGM review](2026-11-05_egm-review.md),
[the weak links](2026-11-04_weak-links.md), [the research picks](2026-10-28_research-picks.md),
[the control plan](2026-10-27_control-plan.md), [the diffusion planner](2026-11-02_diffusion-planner.md),
`docs/trials.md`, `docs/geofence.md`, TODO 78, 93, 96, 99-108.
