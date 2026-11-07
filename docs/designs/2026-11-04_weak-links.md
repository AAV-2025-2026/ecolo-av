# The weak links: every area of the car, what's weakest, and ideas to fix it

* **Author:** Ben (the ask), written up 4 Nov 2026; revised 5 Nov after the
  [EGM review](2026-11-05_egm-review.md)
* **Date:** 2026-11-04
* **Status:** an inventory, not a spec. It points to designs and holds no build detail.
* **What's decided:** Ben's five picks (4 Nov) and his 5 Nov answers. Everything else here
  is **proposed; awaiting Ben**: the order of section 1, every "done means", every
  rejected alternative, and every idea not marked "picked".
* **The schedule:** only in [one car](2026-11-04_one-car.md). This page has none.

Ben's ask, 4 Nov: "what is the weakest ... ideas on how to improve each section of the
driving experience". Word for word: `docs/history/messages-2026-11-04.md`.

**The rule since 5 Nov:** every algorithm stays; each area gets a new best hybrid of our
own; stock stays the default, and ours challenges it until it wins on the same routes and
bags. One design per area is for later, with no date.
Ben: "we want to keep all the algo but we want to create a new best hybrid for each".
The first algorithm is how the car stops. Its design comes after this page.

## In a hurry

| You want | Read |
|---|---|
| what blocks Gate 4, what only improves the car | section 1 |
| the five picks, their designs, what "done" means | section 2 |
| every area's weak point | section 4 |
| how each pick can fail | section 6 |
| every stop rule, in one table | section 7 |

**Tags:** TODO n = a row of `TODO.md`; Q n = the design doc's open questions; A, B, C =
research proposals (section 5); **eng** = a known method, build it; **res** = a research
question; **hw** = the hardware lead's call.

## The chain (section 4 goes through it, then safety, data and screens)

```text
 sensors ──► localization ──► perception ──► behaviour ──► planning ──► control ──► actuators
   (1)           (2)             (3)            (4)           (5)          (6)         (7)
```

## 1. What blocks Gate 4, and what only improves the car

Gate 4 (26 Feb 2027): drive from GPS point A to B at 1 m/s and stop within 1 m. Its driver
is the point driver (`aav_drive_to_point`), not Nav2.

### Blocks Gate 4

| # | Blocker | Kind | What clears it |
|---|---|---|---|
| 1 | **The no-timeout lock** holds every program while the car runs the 2025-26 C++ ESP32 | code gate | the Rust ESP32 flashed (TODO 45, car-day A8), then `frame_version: 2` |
| 2 | **COASTING** holds every program until the running mode's stop is measured | code gate | test 4.3, then `open_loop_decel` or `pi_loop_decel` in `vehicle.yaml` |
| 3 | **The brake doesn't follow a wish**: in `open` the car brakes only below `stop_speed` | physics | `pi`, unless test 4.3 shows `open` can stop within 1 m |
| 4 | **Wheel speed:** not yet seen on the car; the wheel's size is 17 % off loaded | measure | the Arduino's CAN frames seen; TODO 60; TODO 49b for `pi` |
| 5 | **Clocks:** the bridge runs on the Motor Pi, the EKFs on the Orin; where the IMU and GPS plug in is still a TODO | check | `chronyc tracking` on every computer |
| 6 | **Steering:** it pulls right; its ends and centre are unknown | measure | TODO 67 |
| 7 | **No way to score "1 m":** no RTK, no ground truth | decision | Ben or the team: see below |

Open for Ben: the README says stop within 1 m; `docs/tests.md` test 5.2 says "within 1 m
of B (2 m without RTK)". Proposed; awaiting Ben: score it against a tape mark at B.

### Only improves the car

| Weak link | Why it isn't a gate | Where |
|---|---|---|
| reaction time, end to end | B's stop is a planned slow-down, not a lock | 4.6 |
| the speed cap on Nav2, stop at a point (picked) | the point driver plans its own stop | 2 |
| tracking and the person rule (picked; radar paused) | not on Gate 4's route as written | 2, 2.2 |
| the CBF filter (picked) | the locks already stop the programs | 2, 5 |
| a keep-in polygon | the 30 m circle already holds the point driver; Nav2's empty map doesn't touch it | 4.5 |
| the unmeasured numbers beyond those above | they tune the car; 1-6 let it drive | 4.6 |

## 2. Ben's five picks (4 Nov)

Ben: "all 5 are important. Braking, clock, speed profile, tracking and CBF filter".

| Pick | Gate 4? | Design | Exists | Left |
|---|---|---|---|---|
| The brake follows a wish | **blocks** | [control plan](2026-10-27_control-plan.md), [brake path](brake-path.md), `docs/geofence.md`; how the car stops (next) | `speed_control.py`; the geofence's hold | section 2.1 |
| The clock | **blocks** | none needed: a check. `tools/car_setup.sh` | chrony installed, the Orin serving | a Day A step; the lidar's time source |
| The speed profile, with the behaviour layer | improves | [behaviour and speed](2026-11-05_behaviour-and-speed.md); how the car stops (next) | `aav_track/speed.py`; `approach.py`; ego's `max_jerk` (speeding up only) | a cap on Nav2 that is never 0; a stop at a point |
| Tracking | improves | [tracks and memory](2026-11-05_tracks-and-memory.md) | the radar's clusters; the detector's classes | radar **paused** (2.2); the person rule; the memory |
| The CBF filter (research A) | improves | [knows itself](2026-11-05_knows-itself.md); how the car stops (next) | the geofence's stopping path; `vehicle.yaml` | measured numbers first; then the filter, beside the locks |

What it is: [What a CBF filter is](2026-11-04_one-car.md#what-a-cbf-filter-is).

### 2.1 The brake has three states

`speed_loop.mode: open` stays. A state doesn't count until the one above it is done.

| State | Proves | Doesn't prove | Done means |
|---|---|---|---|
| **1. Wiring, on stands** | the brake and throttle answer, the right way round; on the Rust ESP32, a lost command brakes | any stopping: there's no mass to stop | done in `open`, with a person at the e-stop; never `pi` here |
| **2. Ground, test 4.3** | how the car really stops, in the running mode | any other surface | at least 5 stops from 1 m/s; the average and the spread written down |
| **3. Programs released** | the geofence trusts the number | the Gate 4 stop itself | the number in `vehicle.yaml`; `COASTING` gone in that mode; blocker 1 cleared |

| To run `pi` | Why |
|---|---|
| a driven-wheel speed (TODO 49b, the hardware lead) | `/vehicle/odom` reads the front wheels, the motor drives the rear; on stands the loop raises the throttle, and the preflight refuses it |
| braking measured on the ground (test 4.3) | the geofence holds programs in every mode until `pi_loop_decel` is set |

Test 4.3 on today's car gives the stop's deceleration in g, not a `max_brake` fit
(`docs/actuator-tests.md`). A low number is honest: the stopping path grows with it.

### 2.2 Radar tracking is paused (Ben, 5 Nov)

These must be true before it resumes.

| Must be true | Today | Evidence |
|---|---|---|
| the target parser reads every target | it checks 112-byte records but reads 56 per loop | `TI.py:325-336` |
| the main cloud keeps REP-103 axes | tracking mode leaves it as x right, y forward: wrong input for the stop zone and costmap | `aav_radar_ti/README.md:22, 85` |
| the radar runs the right binary and cfg | another binary; cfg boxes 1.5 m deep; one named cfg has no tracker commands | `cfg/rules.txt:3-8`; `cfg/*tracking*.cfg` |
| a target is called what it is | the target topic has no ID or class: "something moving", not "a person" | `aav_radar_ti/README.md:28` |
| a bench test passes first | nothing shows the mode works on our radar | review, stage 9: reviewer's word |
| the cheaper way was tried | the out-of-box cloud's per-point `velocity`, with `aav_radar_clusters`, needs no firmware swap | `aav_radar_ti/README.md:21` |

No firmware or cfg change on the car until then. The blind-zone memory and the person rule
are not radar tracking; each has its own "done means" below.

### 2.3 Done means, and the alternative set aside

All proposed; awaiting Ben. Ten runs, because three clean runs pass by luck about 30 % of
the time at a 1-in-3 fault.

| Pick | Done means | Set aside | Why |
|---|---|---|---|
| Brake | states 1-3; then 10 stops at 1 m/s within 1 m of a tape mark | "leave it" ([brake path](brake-path.md), option 4) | the car coasts |
| Clock | offset under 10 ms on all six computers; the lidar's time source named | PTP | chrony is installed; hardware stamps are unchecked |
| Speed cap, stop at a point | sign test: slows, stops at the line ±0.5 m, 10 of 10; then beats stock on the same routes | the costmap `SpeedFilter` alone | fixed zones, not a moving stop point; same topic |
| Tracking | 2.2 all true | the firmware's tracking mode on the car now | it changes the stop zone's input |
| Blind-zone memory | TODO 93's cause found; the post test 10 of 10; a held car always gets out | our own memory first | stock `observation_persistence` (`nav2.yaml:305`) is one line, untried |
| Person rule | stops, waits, goes when clear; a false stop ends with a person asked | planning round a person | a cone and a child aren't the same |
| CBF filter | predicted stops fall inside the error bars on a new drive; filter on against off, same routes: fewer lock trips, stop error no worse, people untouched | the filter instead of the locks | Simplex: the simple layer stays |

## 3. Not worth it now

All proposed; awaiting Ben. None of this removes an algorithm.

| Not now | Why |
|---|---|
| another stock follower or planner, with no new idea in it | a new hybrid is the point (Ben, 5 Nov); the inner loops matter more |
| learned bird's-eye-view, world models, prediction networks | parked for the 2027-28 team: data and GPUs we don't have |
| a new sensor | the hardware lead's call, after the radar is measured against a low box |
| research B | the memory and the radar may close most of its gap; memory can't help with what was never seen from afar, so B stays open |
| replacing Nav2 | the verdict: `docs/history/conversation.md`. Set aside 4 Nov: Autoware (too big, Humble, C++, needs an HD map), Apollo (not ROS), openpilot (highways, its own hardware) |

## 4. The weak links, area by area

"Planned" means a TODO row already holds it.

### 4.1 Sensing and calibration (stage 1)

| Weakest | Evidence | Ideas |
|---|---|---|
| **The clocks**: never checked at the car | `car_setup.sh` installs chrony; `car-day.md` has no step for it | **eng, picked:** section 2 |
| Camera and lidar don't know where each other is | the camera layer off (Q22); distance by box height only | **eng:** camera-to-lidar calibration (28 Oct research pick 4: Koide's `direct_visual_lidar_calibration`) |
| One Hall sensor per wheel: no direction | H5; reversing is on, and the speed's sign is the last command's | **hw:** a second sensor; or the command's sign with a check |
| Low things near the bumper (table below) | `vehicle.yaml` `lidar_link`, provisional | **eng:** measure what the radar sees of a low non-metal box; **hw** after that: a bumper lidar or ultrasonics; **res:** B |
| GPS: 1-3 m, no RTK | decided 28 Oct | **eng:** a truth rig for one scoring day ([research ideas](2026-11-04_research-ideas.md), 11) |

The roof lidar sits 1.52 m up, its lowest beam 15° down. On flat ground (worked out, not measured):

| What | Seen until, from the lidar | From the front bumper |
|---|---|---|
| the ground | 5.7 m | 4.4 m |
| the cubes' lowest height, 0.3 m | 4.6 m | 3.2 m |
| a 0.5 m box | 3.8 m | 2.5 m |
| a 1 m box | 1.9 m | 0.6 m |

### 4.2 Localization (stage 2)

| Weakest | Evidence | Ideas |
|---|---|---|
| **No ground truth** on the car | TODO 96 | **eng:** the truth rig; tape marks |
| NDT slips along walls | 0.4 m along the lane north of the Gazebo lot's building, `docs/trials.md` | **res: C** |
| Drift while parked; wheel size 17 % off | TODO 60 | **eng:** a zero-velocity update when stopped (research ideas, 12) |
| Three maps, three frames, not aligned | TODO 63, 64 | **eng, planned:** one survey bag gives the NDT map, the 2D grid and the fence |
| The lot changes; the map doesn't | NDT's map is one drive | **res**, later: a map that keeps what persists |

| Map | For | Made by | On the car |
|---|---|---|---|
| NDT's cubes (`maps/ndt/*.pcd`) | localization | in Gazebo, from the simulator's true position; a KISS-ICP map is untested | not yet |
| Nav2's grid (`aav_navigation/maps/`) | planning | drawn, or `slam_toolbox` | `empty.yaml` |
| The street graph (`maps/routes/`) | routes | Valhalla, from OpenStreetMap (`pixi run get routes`) | untested |
| The street map (`maps/streets/`) | the map window | `pixi run get street-map` | yes |

### 4.3 Perception (stage 3)

| Weakest | Evidence | Ideas |
|---|---|---|
| **No identity or speed for anything** near the car | clusters have no track | **picked**, radar paused: section 2.2 |
| A person is "an obstacle" | the car's detector keeps stop signs only, unless `camera_obstacles` is on, and that waits for calibration (Q22) | **eng, picked:** stop and wait; its exit and false stops go in the design |
| The cubes let the car into a post once | TODO 93: cause unknown. The post is 1.8 m, taller than the lidar, so the blind zone alone doesn't explain it | **eng:** diagnose first; then the memory, stock persistence first |
| Thin poles may miss the stop zone | `min_points: 3` is the collision monitor's: three points, so three cubes with `voxels:=true` | **eng:** a thin-pole test |
| A stop sign is forgotten once it leaves the picture | the watcher's 10 s ignore | **eng**, later: a sign seen is a sign on the map |
| "It appears" to "the brake moves" is unmeasured | 0.13 m past the post on a busy Mac | **eng:** stamp the chain end to end |

### 4.4 Behaviour: the missing layer (stage 4)

| Weakest | Evidence | Ideas |
|---|---|---|
| **No behaviour layer**: a lock stops the car at a sign 4.7 m away, with no slowing first | `stop_sign.py`, the locks | **eng, picked:** a small state machine; the locks stay underneath |
| Stuck means Nav2's generic recovery | `nav2.yaml`: 10 s without progress | **eng:** ask a person; define it in the design |

The design decides subtree or node; the two pages disagree today (review, finding 8).

```text
 DRIVE ─► APPROACH (slow to the line) ─► STOPPED ─► WAIT ─► GO ─► DRIVE
   │ a person ahead ─► WAIT
   │ stuck ─► ASK (the HUD's GO / STOP panel)
```

### 4.5 Planning (stage 5)

| Weakest | Evidence | Ideas |
|---|---|---|
| **No keep-in map on the car**: Nav2 may plan onto the grass | `aav_navigation/maps/empty.yaml` | **eng:** the polygon below |
| MPPI picks its own speed; `speed.py` serves only the trial trackers | `aav_track/speed.py` | **eng, picked:** a speed cap on Nav2 with a floor, never 0: to Nav2, 0 means no limit. A lock makes the last stop |
| Weaving up to 1.5 m; a left/right flip at a replan | `docs/path-followers.md`, N7 | **eng, planned:** keep the last plan unless the new one is clearly better |
| The turning circle is a guess × 1.25 | `plan_turning_radius` | **eng, planned:** from the measured steering |

**The polygon:** one polygon, two readers: the geofence (exists) and a stock Nav2
`KeepoutFilter` mask. No design yet; zones, places and missions wait.

| Step | Watch out for |
|---|---|
| 1. Set the datum (TODO 64) | a site drawn on another datum is refused at start-up |
| 2. Walk the edge, record `/sensors/gps/fix` | each corner carries the GPS's own 1-3 m error; σ doesn't cover that |
| 3. Write it to `geofence.yaml` | the lock closes at path + 1 m + σ: at 1 m/s with σ 1-3 m, 3.5-5.5 m from the edge; σ over 3 m is LOST |

### 4.6 Control and actuators (stages 6, 7)

| Weakest | Evidence | Ideas |
|---|---|---|
| **The brake doesn't follow a wish**; no sensor checks the throttle | [brake path](brake-path.md); TODO 0, 79 | **eng, picked:** section 2.1 |
| **The reaction budget**: 1.0 s today (table below) | `geofence.py` `backend_stale`; `legacy.yaml` | **eng:** stamp the chain on the car, then tighten; a firmware reflex only if still too long |
| MPPI's model has no lags; gains from guessed numbers | control plan, step 2; TODO 52b | **eng, planned:** the tests' numbers into `vehicle.yaml`; **res: A** |
| Lurches: ego's `max_jerk` covers speeding up only; the spine's ramp has no jerk limit and doesn't reach today's car | `ego.yaml`; `speed_loop.rs` | **eng:** a braking jerk limit, in how the car stops |
| The steering pulls right | TODO 67 | **eng, planned:** the calibration page, run it |

The geofence's reaction budget, ρ. It's a worst case: the backend's timeout only counts if
ego itself died. No part has been measured.

| Part | On a lock's normal path? | Today's UART car | The future spine |
|---|---|---|---|
| the geofence's tick | yes | 0.1 s | 0.1 s |
| the pose's lag | yes | 0.1 s | 0.1 s |
| ego's command timeout (the mux goes quiet) | yes | 0.3 s | 0.3 s |
| the brake's lag (a guess) | yes | 0.2 s | 0.2 s |
| the backend's timeout | no: only if ego died | 0.3 s | 0.2 s |
| **ρ** | 0.7 s without the backend | **1.0 s** | **0.9 s** |
| **Stopping path at 1 m/s**, b 1.0 m/s² | | **1.5 m** | **1.4 m** |

The 1.5 m assumes a brake today's car doesn't use. In `open` it coasts about 10 m (an
estimate: 1 m/s ÷ the guessed `drag`), so **today braking dominates, not reaction**.

### 4.7 Safety

| Weakest | Evidence | Ideas |
|---|---|---|
| **Stop rules with no shared model**: only two use a stopping sum, and the sums differ | section 7 | **eng:** measure, write `vehicle.yaml`, read it; keep a margin no shared number can remove; **res: A** beside them |
| Today's car has no firmware timeout | TODO 45; A8 | blocker 1 |
| Faults on purpose cover sensors, not actuators | `docs/simulation.md` | **eng:** steering stuck, brake weak, throttle stuck |
| No written safety case | the final report | **eng:** one page per hazard: what stops it, the number, who measured it |

### 4.8 Data, compute and plumbing

| Weakest | Evidence | Ideas |
|---|---|---|
| No bag has ever been scored | TODO 63, 96 | **eng, planned:** the first bags; the trials scored on them |
| Gazebo flatters: no lidar sweep, suspension, slip or people | Gazebo stays stock (1 Nov) | **eng:** write the gap down after the first bag; change the sim only for a measured gap |
| Python on the Orin unmeasured | TODO 76 | **eng, planned:** `measure timing` on the car; the cubes to Rust only if they miss |
| Cyclone's one network card on the Orin | TODO 28 | **eng, planned:** the file on the Orin |

### 4.9 Mission and screens

| Weakest | Evidence | Ideas |
|---|---|---|
| Too many windows; the nav map twice | TODO 73, 87, 90, 107 | Ben, 5 Nov: [one developer window](2026-11-05_one-window.md): Gazebo's 3D view, the Nav2 map, the cubes and NDT, with a swap list. The street map and HUD stay raylib, in the car |
| "Why am I stopped?" shows on the HUD only | TODO 44a | **eng:** the same reason in the developer window |

## 5. The three research proposals

A is one of Ben's picks. B and C are proposed; awaiting Ben.

| # | Idea | Needs first | Measured by | Doesn't show |
|---|---|---|---|---|
| **A** | learn the car's numbers, with error bars; a brake-health monitor; a CBF filter beside the locks | the actuator tests; wheel speed; `pi` for the monitor | numbers: predicted stop against actual. Filter: on against off, same routes | a good fit doesn't test the filter |
| **B** | the lidar teaches the camera free space, with no hand labels; the car ignores the model when unsure | camera-to-lidar calibration; recordings | a cone at 3 m, caught or not | |
| **C** | NDT reports how sure it is in each direction; the EKF ignores it in the unsure one | nothing: Gazebo shows the slip | Gazebo's 0.4 m slip gone, then a lot bag | Gazebo alone says nothing about the car |

A needs a solver only if the design does: `aav_track/qp.py` exists, and Clarabel isn't a
dependency.

## 6. Risks

Proposed; awaiting Ben. Each design holds the detail.

| Pick | How it fails | Who detects it | Fallback |
|---|---|---|---|
| Brake | `pi` on a wheel that doesn't turn: the throttle winds up | the preflight refuses; the person at the e-stop | `open`; programs stay held |
| Brake | test 4.3 on dry ground, Gate 4 on February snow: the car stops longer than counted | rerun 4.3 on the day's surface | write the lower number; the path grows |
| Clock | a computer drifts after Day A's check | nobody yet: the watchdog checks arrival, not stamps | check at each start; a person holds the drive |
| Speed cap | the cap reaches 0 (no limit to Nav2), or its node dies and leaves it stale | a Gazebo check on both | the locks stay underneath |
| Tracking | a tracking cfg turns the stop zone's input 90°, with no fault | only a bench test | paused; `base.cfg` stays |
| Person rule | a false stop holds the car, or a person never clears | the safety driver; the HUD's reason | ask a person; the joystick outranks it |
| Memory | a remembered cube holds a stopped car forever; a walker leaves a wall of cubes | a Gazebo test of each | a timed expiry; off by default |
| CBF filter | a wrong shared number makes every rule wrong at once | a stop against prediction; the monitor later | locks keep their own margin; filter off |
| The polygon (not a pick) | corners off by the GPS's error: the car crosses the real edge | a person, at the first walk-through | the safety driver; a smaller polygon |

## 7. Every stop rule

Six locks in twist_mux, plus timeouts that aren't locks. COASTING and NEAR are states of
the geofence's one lock. People are held only by the e-stop.

| Rule | Priority | Number | Holds | Stopping sum? | File |
|---|---|---|---|---|---|
| e-stop | 255 | | everyone | no | `/safety/estop` |
| no-timeout | 60 | on with `frame_version: 1` | every program | no | `legacy.yaml` |
| geofence | 51 | 30 m circle; path + 1 m + σ | every program | **yes:** ρ, b | `geofence.yaml`, `car.launch.py` |
| stop sign | 30 | 4.7 m; hold 4 s; ignore 10 s | point, Nav2, AI | no: a camera-view choice | `stop_sign.py:52-57` (code defaults) |
| sensor watchdog | 30 | 0.5-2 s quiet, NaN, a jump | point, Nav2, AI | no | `sensor_watchdog.yaml` |
| stop zone | 21 | 1 m past the bumper; 3 points | Nav2, AI | **yes:** its own | `nav2.yaml`, `vehicle.py` |

| Not a lock | Number | File |
|---|---|---|
| stale command, ego | 0.3 s | `ego.yaml` |
| stale command, the backend | 0.1 s + 0.1 s (spine), 0.2 s (Gazebo), 0.3 s (UART) | `spine.yaml`, `geofence.py`, `legacy.yaml` |
| stale command, firmware | 100 ms on the Rust ESP32; none on today's C++ | TODO 45 |
| limits | ego's 1.0 m/s; drive-to-point's 200 m | `ego.yaml`, `drive_to_point.yaml` |

The stop zone guards only Nav2 and the AI slot, so it doesn't guard the Gate 4 driver.

## 8. The four names (Ben asked, 4 Nov)

`docs/history/conversation.md` points here for these. The stack checked, the Nav2 verdict
and how the cubes differ are in that record.

| Name | Who | The idea | For us |
|---|---|---|---|
| **CBF** (control barrier function) | Ames et al., 2017 | a bumper made of maths: trim the command the least that keeps room to stop | research A |
| **Simplex** | Lui Sha, 2001 | a clever controller, a simple one you trust, a switch that hands over before harm | the locks stay |
| **Degeneracy** | Zhang, Kaess, Singh, 2016 | matching to a wall pins you across it, not along it; trust only the sure directions | research C |
| **Self-supervised free space** | Hadsell et al., 2009 | a camera model with no human labels: the lidar labels the pictures | research B |

## Papers

| Paper | For |
|---|---|
| Ames, Xu, Grizzle, Tabuada, *Control Barrier Function Based Quadratic Programs for Safety Critical Systems*, IEEE TAC 2017; Ames et al., *Control Barrier Functions: Theory and Applications*, ECC 2019 | A |
| Sha, *Using Simplicity to Control Complexity*, IEEE Software 2001 | A, the safety case |
| Shalev-Shwartz, Shammah, Shashua, *On a Formal Model of Safe and Scalable Self-driving Cars* (RSS), 2017 | the geofence's stopping path |
| Zhang, Kaess, Singh, *On Degeneracy of Optimization-based State Estimation Problems*, ICRA 2016 | C |
| Hadsell et al., *Learning Long-Range Vision for Autonomous Off-Road Driving*, J. Field Robotics 2009 | B |
| Biber and Strasser 2003; Magnusson 2009 (NDT); Vizzo et al. 2023 (KISS-ICP) | cited in their designs |

## Related

[One car](2026-11-04_one-car.md) (the direction, the one schedule);
[the EGM review](2026-11-05_egm-review.md); [research ideas](2026-11-04_research-ideas.md);
`docs/geofence.md`; `docs/history/conversation.md`.
