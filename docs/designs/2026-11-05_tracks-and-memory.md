# Tracks and memory: the radar's tracker, a person lock, and the blind-zone memory

* **Author:** Ben (the pick), written up 5 Nov 2026
* **Date:** 2026-11-05; revised after the EGM review
* **Status:**
  * **Part A (radar tracking): paused** by Ben, 5 Nov. Nothing on tracking happens until the
    stopping design is done and the radar is confirmed on the car.
  * **Part B (blind-zone memory): proposed; after TODO 93 is diagnosed; awaiting Ben.**
  * Nothing here is built, and nothing here has been run. TODO 103, 93.

Ben, 4 Nov: "I would say all 5 are important. Braking, clock, speed profile, tracking and CBF
filter (i just don't know what this is)".

Ben, 5 Nov: "we want to keep all the algo but we want to create a new best hybrid for each".
His choice that day: stock stays the default, and ours challenges it until it wins.

## Problem

| Gap | Today |
|---|---|
| Nothing gives a thing near the car an identity and a speed | the radar's clusters last one frame |
| The roof lidar can't see a low thing close in front | only the radar is left to see it, and it sees some things poorly |
| The cubes let the car into a post once (TODO 93) | 1 of 3 runs on 3 Nov, 1.30 m in; cause unknown |

## Goals

- Write down what must be true before tracking resumes, so the pause loses nothing.
- Keep every algorithm as a candidate for the tracking hybrid.
- Find TODO 93's cause before fixing anything.
- Close the low-thing gap with stock settings if they can.

## Non-goals

- Any firmware, cfg or driver change on the car now.
- A person lock now: its requirements are kept for later.
- Remembering what the lidar never saw (a thing that steps out from the side).
- Remembering kerbs: cubes start 0.3 m above the road, so they are never stored.
- Changing `voxels:=false`, the default, in any way.

## Part A: what must be true before resuming

Tracking isn't a cfg switch. Each row was checked in the source unless it says otherwise.

| # | Must be true | Today | Done means |
|---|---|---|---|
| 1 | Firmware known | tracking needs a different binary (`cfg/rules.txt`); it is only in `archive/Nav_Radar/.../cfg/bin/`; the repo has no flash steps | written steps to flash and to return to out-of-box, tried on the bench; TI's licence checked before any copy |
| 2 | An outdoor cfg sized to the corridor | the three `3d_tracking_*.cfg` boxes reach 1.5 m forward, and are indoor settings; `AOP_6m_tracking_default.cfg` has no tracker commands, but its name still flips the parser | a new cfg whose box covers the corridor; a target seen at its far end |
| 3 | The target parser works | `TI.py:326-335` splits by 112-byte records and reads 56 each, so every target after the first is misread | fixed in a no-ROS module; a test on captured frames |
| 4 | The header offset is right | `TI.py:115` says its offset is "not suited for official people counting binary", and `rules.txt` ties this binary to TI's people-counting lab | a captured frame confirms the offset and TLV order |
| 5 | The ID survives | `i += 4` (`TI.py:331`) skips the record's first field, and the cloud has no ID column | the ID reaches the topic; TI's docs confirm the field |
| 6 | A short frame can't kill the driver | `unpack` returns `None`, the tuple unpack raises, the generator dies, and after 21 tries the node shuts down (`pc_publisher.py:115-148`). A frame with no target list may do this too | a test feeds cut frames; the driver lives |
| 7 | Both clouds' axes are right | tracking leaves **the main cloud too** in TI's axes (x right, y forward; `TI.py:279-312`). It feeds the costmap and collision monitor | an object straight ahead reads +x in both clouds, on the bench |
| 8 | It works on a moving car | unknown: `rules.txt` names TI's people-counting and small-obstacle labs; no moving run is on record | a bag at 1 m/s: parked things give no false targets; a walker is tracked |
| 9 | A bench go/no-go passed | no test exists | the table below |

Why row 7 matters: 3 m straight ahead would land at (1.8, 3.0) in `base_link`. The stop zone is
x 1.8-2.8, y ±0.7, so the car drives on, with no fault raised. The mode is also picked by the
text "tracking" in the cfg's path, so a folder name can flip it.

### The bench go/no-go

| Check | Go |
|---|---|
| Flash to tracking, then back | `base.cfg` gives the same cloud as before |
| A person walks the corridor | one ID start to end; speed within 0.3 m/s of the walker's |
| A person stands still | what happens is recorded: this sets the clearing rule below |
| Axes | row 7's result in both clouds |
| An hour of frames | the driver is still alive |

No-go means the no-flash way below. No firmware or cfg change reaches the car before a go.

### Ways to track (every one stays a candidate)

| Way | Good | Bad |
|---|---|---|
| **No flash:** the out-of-box cloud's per-point `velocity` with `aav_radar_clusters` | no firmware; axes already right; the safety path's input unchanged | no ID across frames; the velocity is along the ray and includes the car's own speed, so it must be subtracted |
| TI's tracker | IDs, speed and acceleration from the radar | rows 1-9 |
| Our tracker on clusters and cubes | works with any sensor; can become the hybrid | code to write and test |
| A stock open-source tracker | the repo's first choice | not surveyed yet: do it on resuming, with licences |

Proposed; awaiting Ben: the no-flash way first, as the challenger's base. The hybrid is
judged against the default on the same runs, and swaps in only when it wins.

### Later requirements: the person lock

| Requirement | Why |
|---|---|
| Generalise `stop_sign_watcher` rather than write a new node's logic | its rule and hold already exist. Reuse `ground.box_points`, `ROAD_USERS`, `recent.Recent` |
| A fail-safe timeout, not 0 | with 0, silence never locks, so a dead watcher lets the car drive. The sensor lock's 1 s heartbeat is the pattern |
| One trigger each for WAIT and the lock | with one trigger the lock fires first, and WAIT never stops nicely. Likely: the guard at a shorter range; the stopping design decides |
| Clearing never releases toward a standing person | a still person may drop out of the radar: "2 s after the last sighting" would move the car at them |
| A corridor that follows the path | a straight box looks the wrong way on a curve |
| Parked cars don't lock | the radar gives no class, so a target is only "something". Moving, or a camera `person` box, until proven |
| `plan_around` stated | it is on by default (`navigation.launch.py:447`), so the planner can route round a locked walker. Say which is wanted |
| Say who it holds | priority 30 holds Nav2, the point driver and AI; not buttons, replay or scripted |
| Waits over 10 s | Nav2's progress check allows 10 s (`nav2.yaml:88`); the stopping design handles it |
| The camera's `person` reaches it | the car's detector runs with `labels: stop sign` by default (`car.launch.py`) |
| A real bench test | no `--walker` or `--person` flag exists; the bench uses `aav_bench`'s `mock_radar` (`bench.launch.py:131`) |

## Part B: the blind-zone memory

**Proposed; after TODO 93 is diagnosed; awaiting Ben.** Default off, as a trial inside the
`aav_voxels` trial. What the lidar saw on the way in stays marked through its blind zone.

### TODO 93 comes first, and may be a different problem

The post is 0.5 x 0.5 x 1.8 m, taller than the 1.52 m lidar. Level and rising beams keep hitting
it at every range, so it is **not** in the blind zone. The old text's cause was a guess. The
lidar also moved lower and rearward (x 0.90 → 0.49 m), not forward.

| Suspect | Why | Look at |
|---|---|---|
| Few cubes near `min_points: 3` | each point in the stop zone is one cube, and the post's face is 2-3 cubes wide. The flat scan's many rays passed 12 of 12 | cubes inside the zone, cloud by cloud |
| Late under load | "the stop zone fired, too late" (`trials.md`); the scan was late under load on 20 Oct too | `status.ms`, `clouds_dropped`, the time from cloud to stop |
| The roof | Gazebo's roof is 2 cm under the lidar. The real one is at 1.33 m by `vehicle.yaml`'s comment; `body.height` is 1.50, TODO measure | the cloud's forward rings |
| A wrong road fit | it can lift the road | `fitted`, roll and pitch |

The failed run's log (`log/sim-all/...`) isn't on this machine. A new run must log these.

### Where the blind zone really is

From `vehicle.yaml`'s mount now, with the lowest beam 15° down. A cube is hidden when
`r < (z_lidar - z_top) / tan(15°)`, where `r` is its flat distance from the lidar.

| Thing | Hidden within (from the lidar) | From the front bumper |
|---|---|---|
| The road | 5.67 m | 4.36 m |
| A 0.5 m box | 3.81 m | 2.50 m |
| A 1 m box | 1.94 m | 0.63 m |
| The 1.8 m post | never | never |

The 6.7 m in older pages is the old 1.80 m mount. The mount is read at start, never written
in. The real roof may hide more: check the cone against the first car bag.

### Stock first

`collision_monitor` guards the bumper, and it reads the newest message only: none of the stock
options reach it. Whether costmap marks alone stop the car is what the first trial measures.

| Option | What it does | Problem | Proposed |
|---|---|---|---|
| `observation_persistence` (0.0 at `nav2.yaml:305`) | one line: the costmap keeps old clouds in `odom`, by time, then frees itself | everywhere, not only in the cone; a walker's trail; 6 s is 60 clouds of rays; a slow car outruns it | **try first** |
| `VoxelLayer` | 3D rays don't clear a low box under them | no time rule, so it can hold a stopped car; cubes need `lidar_link`; more CPU | second, as the voxels design says |
| A marking-only layer (as `camera_layer`) | marks stay until the window moves off | no filter: every walker leaves a wall | third |
| STVL | clears by view and by time: the closest match | not on `osx-arm64` (`pixi search`, 30 Oct) | look again; no if still absent |
| `memory.py` (ours) | the rules below; reaches the stop zone | code to own; can stop the car for a ghost | only if the stock ones lose, by numbers |

### The rules, if it comes to `memory.py`

All numbers are proposed; Gazebo tunes them.

| Rule | Proposed | Why |
|---|---|---|
| Stable only | a cube joins after 6 of the last 10 clouds in the same `odom` cell | a 1.4 m/s walker fills a cell for about 0.54 s (0.5 m body + 0.25 m cell) |
| In the cone | kept only while hidden, by the formula, for that cube's height | not a fixed 7 m |
| A fresh view clears | once in view, the newest cloud decides: not there, gone. Unless a nearer cube on that bearing hides it | a person's upper cubes clear at once |
| The radar never clears | no radar non-detection removes a cube | it sees some things poorly, and it is another layer |
| Travel limit | 6 m since last seen; forward and back both count | 4.4 m reaches the bumper; replaces 12 m and the "2 m behind" rule |
| Time limit | 20 s since last seen, moving or not | 4.4 m at 0.25 m/s is about 18 s. A stopped car can't be held forever |
| Who is told | at each time-limit drop: `status` goes WARN and counts it; the HUD shows it; the log says where | a person must know the car went on past a remembered thing |
| Reversing | the cone is a circle round the lidar, so cubes behind stay held | backing up doesn't forget; the rear stop zone reads them |
| On the body | a cube inside the car's outline (`body_box`) is dropped | drift can't lock the car from inside |
| Stale odometry | `/localization/odom/local` over 0.5 s old (the watchdog's limit), or a jump over 0.5 m between clouds: drop all, publish the live cubes | back to today's behaviour, never a wrong place |
| Size | at most 300 cubes, nearest kept; the rest counted | the lot gives 1,067-1,378 cubes a cloud; only stable low ones in the cone are stored |
| CPU | the node's 4-6 ms plus at most 2 ms on a Mac; Rust if the Orin's `ms` passes 20 | the voxels design's limit |

A real low box after the time limit: the car may go on and reach it, exactly as today with
the radar still guarding. That choice is Ben's (T4).

### What each reader gets

| Reader of `/perception/voxels/cubes` | `memory:=false` | `memory:=true` |
|---|---|---|
| local costmap | as today | live + remembered: clears, then marks, so they survive |
| planner's costmap (`plan_around`) | as today | the same, so it can route round a ghost |
| **collision monitor** | as today | remembered cubes count to `min_points`: they can stop the car |
| debug HUD | as today | draws both; `remembered` tells them apart |

| Topic | Type | With `memory:=true` |
|---|---|---|
| `/perception/voxels/cubes` | `PointCloud2`, `base_link` | live + remembered. Byte for byte today's when off |
| `/perception/voxels/remembered` | `PointCloud2`, `base_link` | new, debug only: nothing may drive from it |
| `/perception/voxels/status` | `DiagnosticStatus` | adds `remembered`, `dropped_time`, `dropped_travel`, `dropped_view`, `dropped_limit`, `odom_stale` |
| `/localization/odom/local` | `nav_msgs/Odometry` | a new input |

`memory:=true` is refused without `voxels:=true`. The contract changes first
(`docs/interfaces.yaml`). The logic is `memory.py`, with no ROS. The cubes' meaning changes only
when the switch is on.

### The drift budget

| Source | Over the 6 m limit |
|---|---|
| Gazebo's `ekf_local`: 0.30-1.91 m per 100 m (`trials.md`) | 2-11 cm |
| The car, until TODO 60's tape: wheel size 17 % off | about 1 m: the stop zone's whole depth |

Odometry that reads short puts a cube further away than it is, so the car stops late. **No
memory on the car until TODO 60 is measured.** It is simulated first: `memory.py` tests with the
pose scaled 0, 5 and 17 %; in Gazebo, each remembered cube against the truth. Pass: within
one cube (0.25 m) at the bumper.

### Checks (proposed; not run)

**Run counts.** Failing 1 in 3, three clean runs pass by luck about 30 % of the time
((2/3)³). Twelve clean runs: under 1 % at that rate, 3 % at 1 in 4. If the base rate is lower,
use 3 ÷ rate runs. Alternate old and new at the same load, and record the load.

| Test | Pass |
|---|---|
| Base: `sim-check --lidar-obstacle --voxels`, 12 runs, with the new logging | the failure seen again, and a cause named |
| The cause's fix, 12 runs | 12 of 12 stop |
| New `low_box` model, 1 m wide, 0.5 m tall, through `check_obstacle(model=..., depth=...)`, radar off, memory off | the base. If it stops anyway, the memory isn't needed |
| The same with each option on, 12 runs | stops before it every run |
| A box 0.5 m wide | count the cubes: it may never reach `min_points: 3` |
| `check_obstacle`'s `take_away` (it removes the box after 3 s still) | the goal is reached within the time limit + 10 s |
| The box left in place | what happens after the limit is recorded, and `status` warned |
| A post moved across 5 m ahead (needs a small `set_pose` mover) | no hold after it has gone, beyond the time limit |
| `memory.py` units | each rule above; the three pose scales; reversing; a stale pose |
| `measure controllers --voxels --tours lot` | the time within 10 % of memory off; `ms` and `remembered` in budget |

No low box exists today: `models/` has `obstacle` (1 m), `post` and `stop_sign`.

## Alternatives

Part A's ways and Part B's options are weighed above. Doing nothing is also real: the radar
stays the low-thing sensor, as `docs/status.md` says, if the bench shows it sees a non-metal box.

## Risks

| Risk | Effect | Answer |
|---|---|---|
| A ghost stops the car | waits up to 20 s, and Nav2 may retry or abort (10 s check) | the time limit; `status`; off by default |
| The limit frees a real box | the car goes on to it, as today | Ben's call (T4); radar still guards |
| Drift places a cube wrong | a late stop | no car before TODO 60; the scale tests |
| A slow walker passes the filter | low cubes stay until the time limit | Gazebo tunes it; measure |
| Snow held in memory | flakes that repeat become ghosts | the filter; test on the winter lot before winter use |
| A low box seen in few clouds | at 2° between beams, it is seen only in bands; a fast car may miss the filter | the 12-run test; tune by speed |
| Tracking mode reaches the car by mistake | the stop zone's input turns 90° | the pause; row 7; the mode set outright, not by a name |
| A firmware swap can't be undone | no radar on car day | row 1 first, on the bench |

## Order

1. Base runs and TODO 93's cause.
2. `observation_persistence` on the low box, then the other stock options.
3. Ben decides on `memory.py`. Then the contract, `memory.py`, `memory:=`, the checks.
4. On the car: only after TODO 60 and TODO 93.
5. Part A: only after the stopping design and the radar confirmed on the car. Rows 1-9, then the bench.

## Questions for Ben (proposed; awaiting Ben)

| # | Question | Proposed |
|---|---|---|
| T1 | On resuming: TI's tracker, or the no-flash way first? | no-flash first |
| T2 | A lock, WAIT, or both? | the stopping design decides; one trigger each |
| T3 | Build `memory.py` at all, and how far? | only if stock loses; 6 m, 20 s |
| T4 | After the time limit, with something still remembered ahead? | drop it, tell the person, go on: no worse than today |
| T5 | May remembered cubes reach the collision monitor? | yes, when `memory:=true`: otherwise only the costmap's marks act on them |

## Related

[One car](2026-11-04_one-car.md), [the weak links](2026-11-04_weak-links.md) (4.3),
[the research ideas](2026-11-04_research-ideas.md) (3, 4), [the voxels](2026-10-30_voxels.md),
[the EGM review](2026-11-05_egm-review.md), `ros/sources/aav_radar_ti/README.md`,
`docs/perception.md`. TODO 93, 103, 60.
