# Shadow mode: manual drives as tests of the automatic drivers

* **Author:** the 2026-27 team; written up 5 Nov 2026 from idea 1 of [the research ideas](2026-11-04_research-ideas.md)
* **Date:** 2026-11-05; revised the same day after [the EGM review](2026-11-05_egm-review.md)
* **Status:** **proposed; awaiting Ben.** Nothing here is built.
* **Who chose this:** Ben has not picked shadow mode. It came from the research page's
  proposals. His only word on writing these pages is "please continue writing everything".
* **Work list:** TODO 108.

## The idea in one line

While a person drives, an automatic driver works out what it **would** do. Nothing it says
reaches the car. A tool compares the two and lists the moments to read.

```text
 stage 2: offline, no car involved
 the drive's bag ──► Nav2 on a laptop (no mux, no ego) ──► its commands ──► shadow_score.py

 stage 3, only if stage 2 shows value: live, on the car
 the person (joy 100, rc 95, keyboard 90) ──► twist_mux ──► ego ──► the car
 Nav2 (20), AI slot (10) ──► twist_mux, held by the shadow lock (60) ─╳
                        └──► the bag ──► shadow_score.py, after the drive
```

## How it fits Ben's 5 Nov decisions

| Decision | What it means here |
|---|---|
| "we want to keep all the algo but we want to create a new best hybrid for each" | shadow mode removes nothing; it can give a challenger more bags to be read on |
| Stock is the default; ours challenges | a score never promotes a driver (see Goals) |
| The first build is how the car stops | shadow mode waits; only stage 1 is small enough to go beside it |
| The developer window isn't in the car | it can't be the car's goal sender |
| Radar tracking is paused | no score uses it |

## Goals

- Find moments worth reading in real manual drives: false stops and missed stops.
- Run stock and challenger followers against the **same** bags.
- Keep the person's control exactly as it is: a person always outranks the computer.

## Non-goals

- **Promoting a driver.** A challenger still has to win on the same routes, driving for itself.
- **Proving safety.** Agreement with a person doesn't show the driver would have missed everything.
- **Demonstrations for learning.** `record.sh` records no images and no costmaps, so the
  old claim is dropped. Collecting those would need its own design.
- **Scoring many followers at once.** One follower runs at a time.
- **Scoring on the car.** Scores run on a laptop, after the drive.

## Success criterion

| Stage | It worked if |
|---|---|
| 1 | two real drives are scored, and the team changes one thing because of what the list showed |
| 2 | the Gazebo validation passes, then a real bag shows something the Gazebo trials did not |
| 3 | every failure check passes, and the person's command path is no slower with shadow on |

If stage 2's validation fails, the score is not used as a number. The event lists can stay.

## What holds Nav2 today, by configuration

If the joystick goes quiet while Nav2 has a goal, the next fresh input wins after 0.5 s.

| Configuration | What holds Nav2 | Result |
|---|---|---|
| Car, UART, `frame_version: 1` (today's `legacy.yaml`) | no-timeout lock and geofence `COASTING` | held twice |
| Car, UART, Rust ESP32, before test 4.3 is measured | geofence `COASTING` | held once |
| Car, UART, after test 4.3 is measured | only the ordinary locks | **Nav2 drives** |
| Car, spine | only the ordinary locks | **Nav2 drives** |
| Gazebo | only the ordinary locks | **Nav2 drives** |

Those holds are there for other reasons, and they lift for other reasons. A live stage must
not rely on them. Sources: `twist_mux.yaml`, `legacy.yaml`, `geofence.py` (`coasts`).

## Alternatives

| Option | Can it fail open? | Followers per drive | Load on the Orin | Verdict |
|---|---|---|---|---|
| **A. Recording only** | nothing to fail: no goals | none: scores the locks only | the bag | **stage 1** |
| **B. Bag replay through Nav2** | no: `replay.launch.py` starts no mux and no ego | any, one run each | none: a laptop | **stage 2** |
| **C. Heartbeat lock + override file** | no on silence; see "The lock" for what's left | one | Nav2 live | **stage 3 proposal** |
| **D. Air gap**: Nav2's output remapped away from the mux | only by a launch mistake | one | Nav2 live | runner-up (S2) |
| **E. Share the no-timeout lock** | yes: timeout 0 | one | Nav2 live | rejected |
| **F. The first draft**: new lock, timeout 0, one message | yes | one | Nav2 live | rejected |

| Option | Why |
|---|---|
| B's limits | needs `--lidar` bags (about 9 MB/s). Radar and cameras aren't recorded. Same coupling as live (see "Validity") |
| C over D | one lock holds every program; Nav2's topics stay as recorded and checked |
| D's strength | no mux change, and nothing to hold. It covers only Nav2's chain: two wiring points (the smoother's remap, `cmd_vel_out_topic`) and a new topic |
| E's fault | the legacy bridge sends its own value at 5 Hz. With `frame_version` 2 or 3 that's false, so two senders would fight. The preflight would also blame the firmware |
| F's fault | timeout 0 means silence never locks. twist_mux subscribes volatile (`SystemDefaultsQoS`), so a restarted mux misses a one-shot |

## The stages (proposed; awaiting Ben)

| Stage | What | Enter when | Go on when |
|---|---|---|---|
| **1** | `record.sh` gains the topics below; `shadow_score.py` scores the locks against the person | any manual drive. Day A can use it, recording only | the success line above |
| **2** | replay real bags through Nav2, one follower per run; goals taken from the person's own path | stage 1's value; `--lidar` bags; the Gazebo validation passed | a question only the live car can answer |
| **3** | the live lock and `shadow_goals` on the car | all of the list below, and Ben's yes | none: it then runs on chosen drives |

Stage 3 may never be needed. Live adds only real Orin timing and camera-only perception.

**Before stage 3 on the car:**

- [ ] the site file gives the legs (TODO 100; it doesn't exist yet)
- [ ] a map of the lot: on `empty.yaml`, Nav2 plans straight through the buildings
- [ ] wheel speed checked against GPS on a real drive
- [ ] every check below passes in Gazebo and on the bench
- [ ] an Orin timing baseline without shadow

**Day A** records only: it has no legs, no sender, no map and no checked wheel speed.

## The lock (stage 3)

| Part | Proposal |
|---|---|
| Entry in `twist_mux.yaml` | lock `shadow`, `/safety/shadow_lock/lock`, priority 60, **timeout 0**: nobody sending, and it stays open for every other run |
| Override file | `config/shadow_lock.yaml`, loaded last with `shadow:=true`: **timeout 1.0**, so silence locks. The geofence's pattern |
| Heartbeat | `ros2 topic pub -r 5` as the launch's process `shadow_lock`, as `replay_source` does. Only ever `true` |
| Holds | everything below 60: scripted, buttons, replay, point, Nav2, AI |
| Doesn't hold | people (100, 95, 90) and the actuator tests (60: a person runs them); the e-stop still holds all |

The entry stays in `twist_mux.yaml` because `language_drive` reads only that file to say who
drives. It would otherwise report Nav2 as driving while it's held.

| If this happens | Then |
|---|---|
| The heartbeat dies | mux locks within 1 s; `shadow_goals` cancels |
| The mux restarts | locked from start-up until it hears true |
| The override file isn't loaded | the last true holds, but a restarted mux would open: `shadow_goals` sees the timeout in the mux's report and refuses |
| A stray `false` | open until the next true (0.2 s at most); `shadow_goals` cancels |

### Goals are tied to the lock

`shadow_goals` sends a goal only while **both** hold. If either stops, it cancels at once.

| Must be true | Limit |
|---|---|
| a `true` on `/safety/shadow_lock/lock` | under 0.5 s old |
| the mux's own `/diagnostics` report: `lock shadow` is `locked`, with a timeout above 0 | under 3.5 s old (`language_drive`'s limit) |

Other goal senders still exist on the car: the map window's CONFIRM (`/goal_pose`),
`street_router` and `language_drive`. A goal id that isn't its own is logged as FOREIGN, and
that leg isn't scored. The lock still holds the car.

## The goal's lifecycle

Checked in `nav2.yaml`, the behaviour trees and Nav2's source.

| Event | Nav2 does | `shadow_goals` does | The score does |
|---|---|---|---|
| Person stops, under 8 s | keeps asking | nothing | scores it: would-have-driven |
| Person stops for 8 s | would fail at 10 s (0.5 m or 0.5 rad needed) | **cancels**: leg PAUSED | skips it |
| Person moves again, over half the top speed for 1 s | idle | resends the leg | skips the first 2 s |
| Follower fails anyway | zero command; clears costmaps, waits 5 s, up to 6 retries | waits | skips it unless `/follow_path` is executing |
| `/navigate_to_pose` aborts | zero command | resends after 10 s, 3 times; then NO GOAL on the HUD | skips it, counts it |
| Person comes within 1 m and 0.75 rad | **succeeds, moving or not** (no stopped check) | next leg | ends the leg |
| Person misses the leg | keeps replanning | moves on at the next leg's circle, or after 300 s | ends the leg as MISSED |
| Person drives over 2 m off the plan | keeps correcting | nothing | skips it, counts it |
| Reverse command (`reversing` is on where the lidar watches behind) | may plan or back up | nothing | not in agreement; counted |

The total time for a recovery run isn't worked out here: V5 measures it. The 8 s, 10 s, 2 m
and 300 s values are starting values.

### Legs, by profile

| Profile | Goals come from | Sender |
|---|---|---|
| Replay (stage 2) | a goal every 30 m along the person's own path, from the bag | `tools/shadow_replay.py`, always `--local` |
| Gazebo | `controller_compare.py`'s `TOURS` | `shadow_goals` |
| Bench (Nav2 on the empty map) | a short legs file, for the failure checks only | `shadow_goals` |
| Car, `machine:=orin` or `all` (stage 3) | the site file's named legs (**depends on TODO 100**) | `shadow_goals`, on the mux's computer |
| Anything else (`laptop`, `motor_pi`, turtle) | refused | none |

Replay goals use hindsight: Nav2 is told where the person went. Scores from replay and from
live aren't compared with each other.

## What gets scored

| Thing | Treated as | How |
|---|---|---|
| Nav2 with MPPI or RPP | one follower per run | named from `/system/algorithms` |
| A trial tracker | the follower for that run | it takes `/follow_path` and sits in the same chain |
| Live swap of trackers | never | the car never sets `live_swap` |
| The behaviour layer | **not a driver** (its design only publishes a speed limit) | its state is logged beside events; no score row |
| The AI slot | **lane keeping** today, `/drivers/ai/cmd_vel` | a row only on a drive with `lane` on; off on every machine |
| Point, scripted, buttons, replay, tests | not shadowed | they drive only when someone starts them |

## What `record.sh` lacks

It records people's inputs, `/control/cmd_vel`, and the nav, point, scripted and tests
commands. These are missing. Add them in stage 1:

| Why | Topics |
|---|---|
| Other drivers' commands | `/drivers/ai/cmd_vel`, `/drivers/buttons/cmd_vel`, `/drivers/replay/cmd_vel` |
| Inside Nav2's chain | `/cmd_vel_nav`, `/control/cmd_vel_smoothed` |
| Locks | `/safety/geofence/lock`, `/safety/legacy_uart_bridge/lock`, `/safety/sensor_watchdog/lock`, `/safety/stop_hold/lock`, `/perception/stop_sign`, `/safety/shadow_lock/lock` |
| Why a lock fired | `/safety/geofence/state`, `/safety/sensor_watchdog/state`, `/safety/collision_monitor/state`, `/safety/output_mux/state` |
| Goal state (hidden topics) | `/navigate_to_pose/_action/status`, `/follow_path/_action/status`, `/wait/_action/status` |
| What ran | `/system/algorithms`, `/system/shadow/state`, `/diagnostics` |
| For replay | `/sensors/radar/points`; the lidar stays behind `--lidar` |

Cameras stay out: they're huge. So costmaps can't be rebuilt from camera obstacles.

`replay.launch.py` also needs a change: it starts Nav2 with no arguments, so no lidar, and
its play list has no lidar.

## The scores

All of this is `tools/shadow_metrics.py`, with no ROS. Thresholds are starting values, set
by the validation. `v_top` is the run's speed cap, because first drives are slow.

| Term | Definition |
|---|---|
| Grid | 10 Hz. Live: bag arrival time. Replay: header stamps on the bag's clock |
| Person | `/control/cmd_vel`, while a person's input is under 0.5 s old |
| Follower | `/cmd_vel_nav`, under 0.5 s old. **Not the smoother's output** (see "Validity") |
| Car | speed and pose from `/localization/odom/local` and the map pose |
| κ | curvature, ω / v; only when both speeds are over 0.3 · `v_top` |
| κ limit | tan(`max_steering_angle`) / wheelbase from `vehicle.yaml`; 0.35 /m today |
| Scored sample | person and follower both fresh; goal and `/follow_path` executing; 2 s since (re)start; 1 s since any abort; car within 2 m of the newest `/plan`; follower not reversing; no foreign goal; no e-stop |

`/follow_path` goals are replaced as Nav2 replans. Check the status pattern on a Gazebo bag
first: a replaced goal must not count as a restart.

| Number | Exact meaning |
|---|---|
| **coverage** | scored metres ÷ driven metres. Under 50 %: no agreement is reported |
| **agreement** | scored metres with \|Δv\| ≤ 0.2 · `v_top` and \|Δκ\| ≤ 10 % of the κ limit, ÷ scored metres |
| **would-have-braked** | `/drivers/nav/cmd_vel` ≤ 0.1 · `v_top` while the car is ≥ 0.5 · `v_top`, for 0.5 s, on scored samples. Each is one line: time, place, follower or collision monitor (from `/cmd_vel_nav` and `/control/cmd_vel_smoothed`) |
| **would-have-driven** | the car ≤ 0.1 m/s for 1 s while `/cmd_vel_nav` ≥ 0.2 · `v_top` for 1 s, in a stop's first 8 s |
| **locks** | each lock turning on: time, place, speed then, and whether the car fell under 0.1 m/s within 5 s. A lock already on at the start isn't an event, nor geofence `COASTING` or `STANDS` |
| **per leg** | the above by goal, by follower. Followers are never mixed |

Why these changed from the first draft:

- ±0.1 rad/s at 1 m/s is 29 % of the car's turning range. Curvature fixes that.
- would-have-driven's 0.2 is low because MPPI starts from the car's **real** speed
  (`optimizer.cpp:230`), so from a stop it may ask for little. V5 checks this.

## Validity: why a score may mean little

| Problem | Effect | Answer |
|---|---|---|
| Nav2 reacts to a car it isn't driving | its errors never build up; the person keeps resetting it | no claim about how it would drive for itself |
| The smoother runs `OPEN_LOOP` | its output ramps from its own last output, not the car's speed | score `/cmd_vel_nav` |
| Recovery and aborts send zero | looks like "would have braked" | the scored-sample rule |
| The person leaves the plan | Nav2's correction looks like disagreement | the 2 m rule, and coverage |

**The score can't conclude:**

- who was right when they disagree
- that a follower is safe, or would reach the goal
- anything across different people or routes
- anything about perception that wasn't running or recorded
- anything about the car from Gazebo alone

**A score never promotes a driver.** It picks what to read and what to test next. Promotion
still means winning while driving, on the same routes.

### Validation in Gazebo, before any follower score is trusted

| # | Test | Pass (starting values) |
|---|---|---|
| V1 | Known good: MPPI drives the lot tour; replay that bag with MPPI shadowing | agreement ≥ 90 %, 3 runs |
| V2 | Known bad: same bag, a follower broken on purpose (say a tracker's lookahead tripled) | below V1 by more than the spread of 3 runs |
| V3 | Rank: `measure controllers` ranks followers driving for themselves; shadow ranks them on one bag | best and worst match. If not, no ranking is ever published |
| V4 | A person who detours | coverage falls; the detour isn't blamed on the follower |
| V5 | A 30 s stop, then a stop past 8 s | no recovery zeros in the events; would-have-driven fires at the start; recovery timed |

## Contract and code

| Item | Name | Stage |
|---|---|---|
| Lock | `/safety/shadow_lock/lock`, `std_msgs/Bool`, 5 Hz, only true, volatile | 3 |
| State | `/system/shadow/state`, `std_msgs/String`: SHADOW, leg, PAUSED, NO GOAL, HELD | 3 |
| Package | `ros/drivers/aav_shadow`, beside the defaults: node `shadow_goals`, `shadow.launch.py`; README and CLAUDE.md | 3 |
| Lifecycle, no ROS | `aav_shadow/goal_keeper.py`: the table above, with tests | 2 |
| Scores, no ROS | `tools/shadow_metrics.py`; `tools/tests/test_shadow_metrics.py`; reuses `drive_metrics` geometry | 1 |
| Script | `tools/shadow_score.py`: reads bags the way `atob_score.read_bag` does (its topics are fixed, so that part is new) | 1 |
| Task | `pixi run measure shadow`, with a row in the README | 1 |
| Launch | `mux.launch.py` `shadow_lock:=false`; `car`, `sim`, `bench`: `shadow:=false` | 3 |

Contract first: `docs/interfaces.yaml`, then `docs/interfaces.md`.

### The HUD

The HUD's GO / STOP has inputs for the e-stop, the output mux and the watchdog only
(`hud-core/src/gate.rs`). Don't change that verdict: a person may still go.

| Heard on `/system/shadow/state` | The HUD shows |
|---|---|
| nothing, ever | nothing |
| SHADOW | a banner, as REPLAY has: **SHADOW: YOU DRIVE**, and the leg |
| PAUSED or NO GOAL | the banner, with that word |
| silent for 2 s after being heard | amber **SHADOW QUIET** |

## Checks

### Failure injection (Gazebo, then bench)

Stop each with its process group. Each run has its own `ROS_DOMAIN_ID`.

| Inject | Pass |
|---|---|
| Kill `shadow_lock` while Nav2 has a goal and no person drives | no Nav2 command on `/control/cmd_vel`; goal cancelled within 1 s |
| Never start `shadow_lock` | `shadow_goals` refuses; no goal on Nav2 |
| Start without the override file | `shadow_goals` refuses (timeout 0 in the mux's report) |
| Restart twist_mux mid-drive | Nav2 never passes; the person's command returns |
| Publish `false` on the lock | `shadow_goals` cancels; log how long Nav2 passed (expect ≤ 0.2 s) |
| Release the keyboard | the car stops by ego's timeout; Nav2 stays held for 60 s |
| Kill `shadow_goals` | the car stays held; banner SHADOW QUIET |
| Foreign goal on `/goal_pose` | the car stays held; FOREIGN logged; leg not scored |
| Kill Nav2 | the person still drives; samples aren't scored, not "would have braked" |
| E-stop | stops everyone, shadow or not |

### Launch tests (`aav_bringup`, no ROS started, as `test_navigation_launch.py`)

| Arguments | Must be so |
|---|---|
| default | `shadow_lock.yaml` not loaded; no `shadow_lock`, no `shadow_goals` |
| `shadow:=true` | the file is loaded **last**; both processes present; lock timeout above 0 |
| `shadow:=maybe` | raises, as `geofence_lock` does |
| `twist_mux.yaml` | has lock `shadow`, priority 60, timeout 0 |

The first draft's "fails to launch without the lock node" can't be written: a launch file
starts what it lists. These replace it. `tools/tests/test_topic_areas.py` covers the name.

## Risks

| Risk | Answer |
|---|---|
| **Orin load:** Nav2 live while a person drives. Nobody has measured it there (TODO 76), and the mux is on the Orin | `measure timing` with and without; stop if `/control/cmd_vel`'s worst gap grows. Stages 1-2 add almost none |
| A bad score sways a choice | Non-goals; the validation; a score never promotes |
| A hold is taken for autonomy, or autonomy for a hold | the banner; the lock's default stays off |
| The safety driver watches a leg name, not the road | one short banner; legs are planned before the drive |
| A wrong launch leaves programs held | safe; shows as HELD on the banner |
| Disk | lidar about 5 GB per 10 min; only chosen drives |
| Effort taken from how the car stops | stage 1 only, until that design is done |

## Questions for Ben (proposed; awaiting Ben)

| # | Question | Proposed |
|---|---|---|
| S1 | Do this at all, in stages? | yes: stage 1 with the first bags; stage 2 after how the car stops |
| S2 | If stage 3 comes: lock or air gap? | the heartbeat lock |
| S3 | The lock at 60? | yes: above every program, below people; the tests still run |
| S4 | The car's legs? | the site file's named places (TODO 100) |
| S5 | Score where? | a laptop, after the drive |

## Related

[One car](2026-11-04_one-car.md), [the research ideas](2026-11-04_research-ideas.md) (idea 1),
[behaviour and speed](2026-11-05_behaviour-and-speed.md), [EGM review](2026-11-05_egm-review.md).
`tools/record.sh`, `tools/atob_score.py`, `tools/drive_metrics.py`,
`ros/bringup/aav_bringup/launch/replay.launch.py`,
`ros/command_mux/aav_command_mux/config/twist_mux.yaml`. TODO 100, 108.
