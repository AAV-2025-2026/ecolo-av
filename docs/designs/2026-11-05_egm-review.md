# EGM review of the 4-5 Nov designs

* **Date:** 2026-11-05
* **Status:** All stages run: 5 (zoom out), 6 (comprehension), 7 (design), 9 (accuracy). Stage 8
  was skipped, because no fixes had gone in for it to re-check. Design faults aren't fixed, only
  wrong facts; Ben corrected the direction and the window's scope (below). Start at "What to do, in order".
* **Verdict:** does not pass. Blockers: stage 5, 3; stage 6, 7; stage 7, 28; stage 9, 21. Many
  are the same fault found again.

## Corrected by Ben, 5 Nov

The reviewer judged the set against "simplify down to the best parts", as `one-car` then
read it. Ben: "when I said simplify down to one design i meant down the raod". The aim now
is to build new algorithms of our own from papers, known algorithms and current
implementations.

| Part of this report | What the correction does to it |
|---|---|
| Blockers 1 and 2 | **stand**: they are faults whatever the direction |
| Blocker 3 | the fault **stands** (the laws disagree). The merged stopping law may become our own algorithm, not a cut |
| Finding 4 ("adds and barely converges") | **withdrawn**, except that winners named without numbers are still guesses |
| Findings 12, 18, and the table's rows for KNOW Part 2, KNOW Part 4 and SHD | "not picked" and "premature" **no longer count as reasons to cut**. Their technical faults stand: guessed thresholds, the weak score |
| Findings 5-11, 13-17, 19-22 | **stand** |
| The table's other rows | **stand**: they remove duplicate text, not ideas |

## What the designs add

| | Added by the designs | Removed by the designs |
|---|---|---|
| Nodes | `behaviour`, `person_watcher`, `shadow_lock`, a monitor with no home | none |
| Code | `barrier.py`, `memory.py`, `drive-core`, `drive-app`, `shadow_score.py` | two windows, once the new one is complete |
| Contract | 11 topics, 2-3 locks | none |

## Which documents

| Label | File |
|---|---|
| CAR | `2026-11-04_one-car.md` |
| WEAK | `2026-11-04_weak-links.md` |
| RES | `2026-11-04_research-ideas.md` |
| WIN | `2026-11-05_one-window.md` |
| KNOW | `2026-11-05_knows-itself.md` |
| BEH | `2026-11-05_behaviour-and-speed.md` |
| TRK | `2026-11-05_tracks-and-memory.md` |
| SHD | `2026-11-05_shadow-mode.md` |

## How far each finding was checked

| Mark | Means |
|---|---|
| **checked** | re-checked against the source after the review |
| **part** | some of it re-checked; the rest is the reviewer's word |
| **reviewer** | the reviewer's word only: check before acting on it |

The reviewer ran nothing. It did not read `2026-10-27_control-plan.md`,
`2026-10-28_research-picks.md`, `brake-path.md`, `2026-10-30_voxels.md` or `docs/geofence.md`.

## Blockers

### 1. The stop law's end point means "no limit" to Nav2 (checked)

**Where:** BEH:27, 46, 49, 66.

- BEH publishes `v = √(2·a·(X − s))` on Nav2's `speed_limit`. At X that value is 0.
- In Nav2, `NO_SPEED_LIMIT = 0.0` (`filter_values.hpp:59`). MPPI (`optimizer.cpp:491`) and
  RPP (`regulated_pure_pursuit_controller.cpp:498`) both restore **full speed** on 0.
- So at the moment of stopping, the limit lifts.
- Small limits also shrink MPPI's steering, because `wz` scales by the same ratio
  (`optimizer.cpp:506-510`).

**Fix:** a cap can slow the car but cannot stop it. Floor the cap (say 0.1 m/s) and let an
existing lock make the final stop. BEH:66's "the lock never fires" must change too.

### 2. A filter in ego cannot tell who is driving (checked)

**Where:** KNOW:92, 94; CAR:76.

- KNOW says "people are never trimmed: they bypass it, as they bypass the locks".
- Locks are bypassed by priority **inside twist_mux**. Ego only has `control/cmd_vel`
  (`ego_node.py:52-54`), after the mux, and a `TwistStamped` doesn't say who sent it.
- So the filter would trim the safety driver too. That breaks "a person outranks the computer".

**Fix:** put any trim upstream of twist_mux, on the automatic drivers' path. People then
bypass it by construction. CAR:76 says "in front of ego" and KNOW:92 says "in ego": both
need the new wording.

### 3. "One rule, one model" is designed three times (part)

**Where:** CAR:72-73, 125, 128, 130; BEH:12-15, 49; KNOW:71-76, 84-88; TRK:26, 88.

| Thing to stop for | Designed in |
|---|---|
| A line | the sign lock at 4.7 m; BEH's `√(2a·d)` cap; KNOW's barrier with `v·ρ + v²/2b + k·σ` |
| A person | the collision monitor; the costmap; `/perception/person`; BEH's WAIT; KNOW's barrier; KNOW's 0.3 m/s cap |
| The fence | the geofence lock; BEH's X; KNOW's barrier; KNOW's cap |

BEH's law has no reaction term and KNOW's has one, so they disagree about where the car
stops. Neither says how the two interact.

**Fix:** merge BEH and KNOW Part 3 into one "how the car stops" design: one law, in one
place. Then ask Ben whether the CBF filter still adds anything for Nav2. Its clear use
left is the future AI slot (RES:163).

## Majors: the whole set

| # | Finding | Where | Fix | Check |
|---|---|---|---|---|
| 4 | Adds and barely converges. CAR §4 names winners with no numbers: the cubes win despite "slower and once drove into a post" | CAR:28-30, 116, 123; TODO.md:19, 32-33 | every design gets a "What this removes" section; rows are hypotheses until scored | part |
| 5 | Not ordered by the gate. Rank 2 (the 0.9 s reaction) barely has a design. "This week" holds shadow logging, which Ben didn't pick, and a radar not on the car. Three schedules disagree | WEAK:42-51, 63-65; CAR:148-150; RES:216-217 | one schedule, in CAR; before Gate 4, only what the Gate 4 drive needs | reviewer |
| 6 | Three designs lean on a site file with no design, and TODO 100 scopes in extras that WEAK says wait | SHD:75; WIN:90; KNOW:73; WEAK:262 | one page: one polygon, two readers | reviewer |
| 7 | "Questions for Ben (picked the recommended answer)": Ben didn't answer them. His whole 5 Nov record is "please continue writing everything" | WIN:112; KNOW:133; BEH:79; TRK:83; SHD:70 | label "proposed; awaiting Ben"; put D3, K1, T2 in front of him | checked |

## Majors: each design

| # | Finding | Where | Fix | Check |
|---|---|---|---|---|
| 8 | BEH specifies a new node; CAR and WEAK say "not a new node". It sits in `aav_navigation`, whose README says "no node of our own" | BEH:36-38, 53-59; CAR:49; WEAK:65, 115 | pick one, and correct the other documents | part |
| 9 | "One speed profile for the whole stack" reaches only Nav2's controller. Not the point driver, the AI slot or the trial trackers. MPPI still picks its own speed under it | BEH:12, 27; CAR:49, 128 | rename "a speed cap on Nav2"; state the gaps | reviewer |
| 10 | The filter pulls cubes, radar, fence and path into ego, against "everything flows one way". A stock `FootprintApproach` polygon already sits in `nav2.yaml` | KNOW:71-76, 92, 137; `nav2.yaml:596` | try that YAML edit before writing the stop-zone barrier | part |
| 11 | "The locks stay unchanged" is false: `/safety/model_factor` moves the geofence's trip point, and FAILED adds a lock. Six locks become up to nine | KNOW:12, 43, 51, 93; CAR:76-77, 130 | say which locks change; treat it as a safety decision | reviewer |
| 12 | KNOW Part 2's thresholds (0.7, 0.4, three events) are guessed before measuring. Part 4 wasn't picked. The monitor has no node | KNOW:42-44, 102-113 | keep Part 1; delete Part 4; Part 2 back to RES until there's data | reviewer |
| 13 | ρ = 0.9 s is mostly fault-path timeouts. A trim inside ego skips them, so "one model" has the wrong number | WEAK:143-150; KNOW:32, 64 | trace the path first; the waste may be that a lock stops by silence | reviewer |
| 14 | The radar gives no identity or class, so the "person lock" is a "something moving" lock. Tracking mode also changes the main cloud. Nothing shows the mode works on our radar image | TRK:11, 20-26, 61; CAR:50 | bench first; generalise `stop_sign_watcher` | reviewer |
| 15 | The lock and WAIT share one trigger (a target within 8 m), so the lock fires first and "WAIT stops nicely" can't happen | TRK:26, 88; KNOW:111; BEH:68 | pick one, or give the guard a shorter range | reviewer |
| 16 | The blind-zone memory can deadlock: a remembered cube holds a stopped car, and a stopped car never travels, so the cube never drops. "4 cm drift" is Gazebo's. Stock `observation_persistence` (0.0 at `nav2.yaml:305`) is untried | TRK:41-42, 49-55, 89; RES:97-99 | diagnose TODO 93 first; a time rule; try the one-line stock setting | part |
| 17 | The SHADOW lock duplicates the no-timeout lock. With timeout 0, silence never locks, so if `shadow_lock` dies Nav2 can drive. "Latched" isn't how these locks are kept | SHD:27, 45, 53, 62, 74; `twist_mux.yaml:10-11` | non-zero timeout and resend | part |
| 18 | Shadow's score is weak: Nav2 reacts to a car it isn't driving, and a stopped person trips its progress checker. Only one follower can shadow at a time. `record.sh` lacks topics, so "New: nothing" is wrong | SHD:10-12, 26-39, 68; RES:75, 79 | see the table below | reviewer |
| 19 | WIN builds a new app where `debug_hud` already has 3D, the plan and NDT's match | WIN:60-71, 76-77, 107 | grow `debug_hud`. Ship step 1 (RViz off) now: it cures "the nav stuff twice" | reviewer |
| 20 | The world reader draws the file, not the simulation: spawned posts wouldn't appear, and the car would stop for something unseen | WIN:39, 65, 100; CAR:94 | test whether map + cubes satisfies Ben first | reviewer |
| 21 | TODO 90 (Ben, 3 Nov) keeps the map in the car; WIN retires it. WIN also conflicts with itself on where it runs, and on compressed pictures | WIN:17, 69, 82, 92, 110, 116 | keep `map` for the car, or ask Ben | reviewer |
| 22 | Copies have already drifted: QP with Clarabel vs a plain formula; "in front of ego" vs "in ego"; `rviz:=true` vs `--rviz`; 10 m vs 12 m of memory; TODO 105 "EGM-reviewed" vs RES "pending" | CAR:75, 76, 106; KNOW:84-92; WIN:79; RES:8, 97; TRK:48 | one home for each fact | part |

## What should go or be merged

| Part | Recommendation |
|---|---|
| CAR overall | keep as the short index: direction, convergence table, the one schedule |
| CAR §3, §5 | delete; link to WIN and RES |
| CAR §2 table | cut to links; keep "What a CBF filter is", which Ben asked for |
| CAR §7 | move to history; it goes stale |
| WEAK §2 | merge with CAR §2 |
| WEAK §6-9 | move to `docs/history/conversation.md` |
| RES overall | keep as a backlog, explicitly not a plan |
| RES Part 4 | delete: a third schedule |
| RES Part 5 | delete: Ben answered it |
| RES Part 6 | delete: repeats Part 1 |
| BEH + KNOW Part 3 | merge into one stopping design (blocker 3) |
| KNOW Part 2 | back to RES for now |
| KNOW Part 4 | delete from this design |
| SHD | not a build design yet: `record.sh`, plus a score script on real bags after the first drives. The rest back to RES idea 1 |

## Nits (reviewer's word)

- RES:87 says nobody has written "snow"; `docs/learn-sensors.md:130` has.
- KNOW:64 adds `k·σ` to metres, but σ belongs to ρ (s) and b (m/s²).
- KNOW:119 demands the example table "exactly", but the table omits `k·σ`.
- KNOW:28 nests `max_brake` in a map; at least 20 files mention it. Keep it flat with a sibling sigma?
- "Six stop rules" (WEAK:156) and "six locks" (CAR:130) are different sixes.
- WIN:19's "six windows" omits `hw_panel`; CAR:131 includes it and omits Gazebo.
- "One window" (WIN:15) becomes "plus the HUD" at WIN:101.
- WIN:62 lists `/tf` for the map panel; the map node reads `/localization/odom/global`.
- CAR:12, BEH:7 and WIN:8 clean up Ben's typos while CAR:12 says "word for word". "More
  pleasant" (BEH:7) is a reading of his "spesent".
- WEAK and RES run to about 260-290 lines, against "short pages". The cuts above fix this.

## Stage 6: comprehension

**Verdict: fails.** 7 blockers, 19 majors, 8 nits. A fresh reader would have to guess the core
behaviour of the safety filter, stop at X, the blind-zone memory and shadow mode. All of
this is the reviewer's word so far. It ran after the 5 Nov corrections to CAR and WIN.

### Blockers

| # | Finding | Where | Fix |
|---|---|---|---|
| B1 | "People are never trimmed" can't be built: ego can't see the source. The e-stop also holds everyone, so "as they bypass the locks" is untrue (same as blocker 2) | KNOW:92, 94 | a table of which driver is filtered |
| B2 | The worked example contradicts the geofence: NEAR closes with the stopping path within 1 m + σ of the edge, about 2.4 m + σ of room at 1 m/s. So at 1.6 m the lock has already fired | CAR:73-77; KNOW:78-82, 119-120; `geofence.md:20-21, 58` | redo the table with the geofence's real rule |
| B3 | The filter's maths can't be computed: `k·σ` units; b is 3.0 or 1.0; no α; no "allowed acceleration" formula; ego takes a speed, not an acceleration; input topics missing | KNOW:64, 67-69, 84-86, 97 | write it out in full |
| B4 | The sign lock fires anyway: after the car stops at the line and goes on, the sign comes inside 4.7 m, and the "unchanged" watcher holds it 4 s | BEH:30, 50-51, 66; `stop_sign.py:18` | a handshake with the watcher; X short of the lock's distance |
| B5 | v = 0 is undefined (blocker 1's cause). WAIT has no bound, and Nav2's progress check allows only 10 s. "Give the trackers the same X" has no mechanism | BEH:27, 37-38, 49-51, 85; `nav2.yaml:88` | define the stop and long waits |
| B6 | The memory can hold the car still forever (same as finding 16). "15 s" has no rule behind it, and "12 m past" is ambiguous | TRK:39-43, 51 | a timed expiry; define the cube-to-track match |
| B7 | Shadow's Nav2 has no lifecycle: stopped people abort goals. One follower runs at a time. The diagram makes the behaviour layer a driver, and BEH says it isn't | SHD:17, 28, 39, 60 | define aborts and resends; what is recorded |

### Majors

| # | Finding | Where |
|---|---|---|
| M1 | The filter: "in front of ego, a QP" vs "in ego, a formula"; WEAK lists Clarabel as needed | CAR:81-83; KNOW:84-92; WEAK:186 |
| M2 | Behaviour layer: subtree, "not a new node" vs a new node, under a heading saying the opposite | CAR:56, 110; WEAK:65, 115; BEH:36-38, 53 |
| M3 | The 5 Nov direction didn't reach older pages: they still say drop AMCL, no more followers or planners. CAR's column is "The one to keep" | RES:42-44, 232-233; WEAK:71; CAR:103 |
| M4 | The first priority has no design; the brake and clock picks have none in this set | CAR:35 |
| M5 | "Drive window" survives in three pages. If the window isn't in the car, shadow's goals on the car have no sender | WEAK:179-180; CAR:135; SHD:28, 68 |
| M6 | The order of work disagrees across three pages; Day A has no date; first bags Day A vs January; "0.4" isn't in the release table | CAR:133-137; RES:90, 216-219; WEAK:63-65 |
| M7 | What's decided is unclear ("picked" by whom?); review status is stale | KNOW:133; BEH:79; TRK:83; SHD:70; CAR:7, 141, 155; RES:8 |
| M8 | RES wasn't updated after the designs: logging only vs a lock; 10 m vs 12 m; autonomy refusal; the weak brake | RES:75-79, 97, 141, 152 |
| M9 | "Today Nav2 drives" isn't true of today's car: the no-timeout lock and geofence COASTING already hold every program | SHD:27, 68 |
| M10 | The monitor: no "predicted" formula, no state between the error bar and 0.7, no exit from WEAK, no node. In `open` mode the car coasts, so r looks like FAILED | KNOW:42-51 |
| M11 | "Locks unchanged" vs a margin factor read by the geofence (same as finding 11) | KNOW:13, 51, 93; RES:141 |
| M12 | The `vehicle.yaml` shape change and `--fit` are unspecified | KNOW:28, 34-36 |
| M13 | The trust cap's inputs aren't in BEH's table; NDT is off by default; "half" of what? | KNOW:104-113; BEH:42-47 |
| M14 | Stop at X only covers the sign. The sign's distance is straight-line, not along the path. `a` has no value: at 1.5 m/s², slowing starts about 0.33 m before the line, not "from about 10 m" | BEH:12, 27, 45, 66 |
| M15 | ASK has no contract: "stuck", reply, timeout, exit | BEH:20, 32, 77 |
| M16 | Person rules collide (same as finding 15). Any radar target, cars included, triggers the "person" lock. Its timeout is missing | TRK:26, 30, 88; KNOW:75, 111 |
| M17 | The radar has no ID field. Tracking mode leaves the main cloud in TI's axes, and the README says only out-of-box mode feeds a costmap. Wrong mock named | TRK:11, 20, 25; CAR:57 |
| M18 | The memory lives in a trial not in the default stack, and TODO 93 keeps it off the car. TRK states the post's cause as fact | TRK:53-55 |
| M19 | SWAP: "a swap means a restart" ignores the existing live tracker swap (`switches.md:50`). `controller:=` is missing, and trackers refuse `reversing:=true`. `destination.rs` is a search flow, not click-to-go | WIN:36-40, 59, 68-81 |

### Nits

- Terms with no definition or link: Day A, stands, lot tour, harness, site file, mission file, STVL, RSS (it means two things). Share one glossary.
- Long pages: RES 259 lines, WEAK 293; paragraphs inside table cells.
- The 0.9 s chain's parts differ between pages.
- KNOW:32 says "five timeouts and a guess", but the table has five items with the guess.
- "Six" means different sets (same as stage 5's nit).
- TODO numbers 28, 63, 73 and 78 each appear twice.
- WIN: D-numbers out of order; "Step B" clashes with the Order; `pixi run sim` not addressed.
- Small wording: "today" on a page edited on two days; "throttle" where the filter trims a speed command.

## Stage 7: design

**Verdict: all seven fail.** Each lacks the alternatives and risks sections the standard requires.

| Document | Blockers | Majors | Nits |
|---|---|---|---|
| WEAK | 2 | 12 | 4 |
| RES | 3 | 15 | 4 |
| WIN | 4 | 7 | 5 |
| KNOW | 6 | 14 | 5 |
| BEH | 3 | 11 | 4 |
| TRK | 6 | 10 | 4 |
| SHD | 4 | 8 | 4 |

### Re-checked against the source (5 Nov)

| Claim | Evidence |
|---|---|
| The mode is `pi`; `closed` makes the bridge raise `ValueError` | `legacy_uart_bridge.py:113-115` |
| Leaving `open` mode lifts the geofence's COASTING hold, with nothing measured | `geofence.py:194-195` |
| Nav2's message says 0.0 means no limit | `SpeedLimit.msg:5` |
| After CLEAR, a close sign always goes to STOPPING: nothing tells the watcher the car already stopped | `stop_sign.py:86-91` |
| Ego's `max_jerk` covers speeding up only: "Braking: never softened" | `ego.yaml:12-13` |
| `sim_speed:=3` is a top speed, not faster time, so RES's tuner would tune at 3 m/s | `switches.md:87`; RES:119 |
| The target parser checks 112-byte records but reads 56 per loop, so every target after the first is misread | `TI.py:325-336` |
| Tracking needs a different radar binary | `cfg/rules.txt:3-8` |
| The tracking cfgs' box is 1.5 m deep; `AOP_6m_tracking_default.cfg` has no tracker commands | `cfg/*tracking*.cfg` |
| Tracker swaps are already live | `switches.md:50` |
| NEAR closes at the stopping path + 1 m + σ, so the 1.6 m example is already locked | `geofence.md:20-21` |

The rest is the reviewers' word. Nothing was run.

### WEAK

| Severity | Finding | Where |
|---|---|---|
| Blocker | The brake's proof can't show it works: stands have no mass to stop, and the mode switch alone lifts COASTING. Split it: wiring on stands, ground test 4.3 with a number, then release programs | 47, 57, 137 |
| Blocker | No risks section | whole |
| Major | "Ranked by cost to Gate 4" has no costs; the two hard gates (no-timeout lock, COASTING) aren't ranked | 42-51 |
| Major | 0.9 s is a worst-case budget of alternative timeouts on a backend not yet flashed. Today's car rolls about 10 m, so braking dominates | 36, 143-150 |
| Major | `closed` doesn't exist (now fixed) | 57, 137 |
| Major | Radar tracking can change the safety path's input | 49, 60, 105 |
| Major | "A person = stop and wait" has no exit or false-stop plan | 49, 106, 119 |
| Major | The fence's GPS error (1-3 m) isn't set against its 1 m margin; the datum step is skipped | 89, 127, 259-262 |
| Major | Research C can pass in Gazebo and say nothing about the car | 96, 188, 190 |
| Major | "Six stop rules" is overstated; one shared model is a common-mode failure | 38, 51, 156 |
| Major | Research A's test doesn't test the filter | 51, 61, 186 |
| Major | Conflicts with the 5 Nov rules and designs | 3-8, 63-65, 71, 115, 179 |
| Major | Alternatives only partly met; memory can't help with things never seen from afar | 67-74, 265-273 |
| Major | No "done means" column; no clock threshold; no braking jerk limit | 55-61, 85, 140 |

### RES

| Severity | Finding | Where |
|---|---|---|
| Blocker | Shadow's claim that twist_mux "already does this" is false | 75, 79 |
| Blocker | No risks: a public camera dataset (consent, ethics), unattended model-written patches, people near a moving car, braking on ice | whole |
| Blocker | Memory can be erased by a radar that can't see what it remembers | 97, 109 |
| Major | Blind-zone numbers are stale (6.7 m was at 1.80 m; now about 5.7 m), and three clean runs pass by luck about 30 % of the time | 97-100 |
| Major | "Good to centimetres" holds only without slip; 17 % wheel error over 7 m is about 1.2 m | 97 |
| Major | Winter ideas interact: flakes held in memory; DROR removes thin posts | 86, 89, 97, 174 |
| Major | Radar tracking isn't "turn it on"; unproven on a moving car | 108, 111, 225 |
| Major | The brake monitor can read ice as a bad brake and block winter drives; the closed loop can hide weakness | 141, 145, 86 |
| Major | Speed by trust: signals that don't exist yet; two mechanisms | 152, 155 |
| Major | Idea 9's filter isn't a guard; "63 → 73 %" isn't a measure of learning | 163-166 |
| Major | The tuner: `sim_speed:=3` error; 100 evaluations for 30 parameters; bags can't score closed-loop gains | 119-124 |
| Major | The VLM: the default backend is Apple MLX, so not on the Orin; latency unmeasured | 130-135 |
| Major | The truth rig's accuracy looks doubtful: about 1 m along the view at 30 m | 185, 188, 90, 205 |
| Major | Dry vs snow has no dry baseline scheduled | 89, 90, 216-218 |
| Major | The body predates the 5 Nov direction | 5-6, 38-56, 221-236 |
| Major | About 20 weeks of ideas against "one or two students, a term"; no owners; Gate 4 absent | 30, 202-219 |
| Major | Alternatives rarely weighed | whole |
| Major | Disagreement with a person doesn't measure quality | 78 |

### WIN

| Severity | Finding | Where |
|---|---|---|
| Blocker | "Exists today" was false for the Nav2 map, the costmap and ICP (table now fixed) | 58, 62, 100 |
| Blocker | Click-to-go doesn't exist; `destination.rs` is a search flow. Goal heading is lost | 59, 81, 100 |
| Blocker | SWAP has no design: launch split, who restarts, wrong pose seeds after a restart, failed restarts | 73-75, 102 |
| Blocker | No risks section | whole |
| Major | Goals aren't gated to local runs; `screen.sh` runs `debug-hud` non-local; "publishes nothing" is a stated invariant | 16, 75, 82 |
| Major | "Developer only" contradicts shadow mode and TODO 90 | 16 |
| Major | The window drops "why am I stopped?" and, by D7, the e-stop button | 56-64, 121 |
| Major | The swap list doesn't match the switches: live tracker swap, `pixi run pick` exists, tracker forces `reversing:=false`, localizers aren't one choice | 49, 63-69, 92 |
| Major | What `demo` starts is undefined | 14, 94 |
| Major | macOS blocks scripted clicks, so checks can't run as written; Ben's M4 Max is the only performance bar | 89-95 |
| Major | Unweighed cheaper option: Gazebo's chase camera already streams its render. Also RViz or Lichtblick as the one window | 30-40, 90-91, 119 |

### KNOW

| Severity | Finding | Where |
|---|---|---|
| Blocker | No alternatives or risks | whole |
| Blocker | "People are never trimmed" can't be built in ego | 94 |
| Blocker | The brake prerequisite is missing: in `open` mode a trim coasts and r reads FAILED | 42-43, 125-131 |
| Blocker | The monitor may miss its fault: a stop from 1 m/s lasts 0.5 s, so doesn't count; closed loop restores r | 42-45, 121 |
| Blocker | The barrier equation is undefined: `k·σ` units, which b, and the test can't pass | 64, 78-82, 119 |
| Blocker | Handoff gaps: locks don't fire at h = 0, and between 1.4 m and 1.0 m nothing acts | 68-69, 78-82, 120 |
| Major | "Locks unchanged" is false | 12-13, 43, 51, 93 |
| Major | Three meanings of ρ merged | 32-36, 64, 113 |
| Major | Barriers aren't all along the path: 0.5 m/s gives 1.275 m (geofence) vs 0.575 m | 63, 84-88 |
| Major | Filter details: which v, curvature kept, trim to speed | 67, 92 |
| Major | Part 1 overstates what the car can measure today | 28-31 |
| Major | `vehicle.yaml` shape breaks readers; `--fit` is an unguarded writer into lock margins | 28, 34-36 |
| Major | Fit residuals are the wrong σ | 28, 95, 139 |
| Major | Monitor states are inconsistent and smoothing doesn't meet the check | 43 |
| Major | The monitor fails open | 44, 47-51 |
| Major | The cap reaches Nav2 only, and zero means no limit | 43, 104-113 |
| Major | Ego takes perception inputs at 50 Hz with no budget | 67-76, 92, 137 |
| Major | Stale handling: one barrier or all? Release is a step | 93 |
| Major | Radar targets aren't people | 75, 111 |
| Major | No owner for overlapping authority | 71-76, 104-113 |

### BEH

| Severity | Finding | Where |
|---|---|---|
| Blocker | A limit of 0 means no limit (same as blocker 1). A small positive floor still creeps | 28, 38, 46, 49-51, 84 |
| Blocker | The guard fires on every clean run: stop, go, stop again. `sim_check.py:736` also requires the lock to fire | 30, 50-51, 66, 83 |
| Blocker | No alternatives or risks: costmap `SpeedFilter`, a goal at X, slow-down + lock | whole |
| Major | `a` is never chosen: at 1.5 m/s² braking starts 0.33 m before X, inside the delay chain | 28, 49, 66 |
| Major | X has no geometry: camera range vs path, `map` vs `odom`, no stamp, rear lenses, ±0.4 m per pixel at 10 m | 28-29, 42-43, 49, 66 |
| Major | "Whole stack" overclaims: a cap, for Nav2 only | 12, 27, 37, 85 |
| Major | Waits over 10 s hit Nav2's recovery and abort | 19-20, 32, 50, 68 |
| Major | Person handling conflicts with TRK | 19, 44, 50, 68 |
| Major | The state machine is incomplete | 17-21, 50-51, 65 |
| Major | A dead node leaves a stale cap, silently | 14, 37-47, 66-67 |
| Major | Jerk: ego doesn't soften braking; the spine's ramp doesn't reach today's UART car | 31, 69, 76 |
| Major | The topic table can't deliver X for the fence and goal, or the caps | 12, 44-49 |
| Major | Breaks repo rules: new node in a "no node" package; no switch or default | 36-38, 55-59, 67 |
| Major | No path to the car; low-speed MPPI assumed | 5, 63-77 |

### TRK

| Severity | Finding | Where |
|---|---|---|
| Blocker | Tracking isn't a cfg switch: different binary, a named cfg with no tracker, a 1.5 m box | 17-21, 25, 61 |
| Blocker | Tracking mode would corrupt the main cloud for the costmap and collision monitor: 3 m ahead lands outside the stop zone, with no fault | 25 |
| Blocker | The target parser is broken; a short frame can kill the driver; the ID is discarded | 11, 20, 61, 70 |
| Blocker | The memory has no filter for moving things or noise: a walker leaves a wall of cubes | 41-42, 48-51 |
| Blocker | The memory can hold a stopped car forever | 41-42, 51, 89 |
| Blocker | No alternatives: `VoxelLayer`, `observation_persistence`, a marking-only layer | whole |
| Major | "Person" means anything in a loose corridor, straight on a curve | 12, 26, 28, 30, 88 |
| Major | The lock and WAIT share one trigger | 26, 88 |
| Major | The lock fails open, and doesn't hold buttons, replay or scripted | 26 |
| Major | Clearing has no mechanism: a person standing still may drop out, and the car moves toward them | 26, 71 |
| Major | Radar claims unbacked on a moving car | 30, 70, 81 |
| Major | Checks can't prove the risky parts; wrong mock named | 27, 70-71, 78-81 |
| Major | TODO 93's cause is stated as fact: the post is 1.8 m, above the lidar's 1.52 m | 53-55, 74 |
| Major | The drift figure is Gazebo's best: later runs give 4-23 cm over 12 m | 40, 89 |
| Major | Stale geometry; kerbs never stored; reversing forgets | 35-36, 41, 48, 72-73 |
| Major | Lives in a trial kept off the car; no switch; changes the topic's meaning | 9-13, 47-51, 63-64 |

### SHD

| Severity | Finding | Where |
|---|---|---|
| Blocker | The SHADOW lock fails open. Consider remapping Nav2's output instead, so nothing can fail open | 27, 45, 53, 62, 74 |
| Blocker | Goals aren't tied to the lock: a missing flag hands the real car to Nav2 | 28, 45, 68 |
| Blocker | The score has no shown validity: coupled state, `OPEN_LOOP` smoother, recovery counted as "would have driven" | 10-13, 28, 35-39, 60-61, 68 |
| Blocker | No alternatives, risks or non-goals. Offline bag replay is unweighed | whole |
| Major | "Every driver's commands recorded" is wrong | 26, 29, 38-39 |
| Major | "Per driver" isn't possible: one follower at a time | 10, 17, 39 |
| Major | "From Day A" can't be met: no legs, sender, map or wheel speed | 28, 68, 75 |
| Major | "Today Nav2 drives" isn't true on today's car | 27 |
| Major | "Demonstrations": no images or costmaps recorded | 13 |
| Major | Score definitions are incomplete; ±0.1 rad/s is 29 % of the range | 29, 35-38 |
| Major | Checks cover only the normal path | 60-62 |
| Major | Wiring and neighbours unspecified: `language_drive` could be misled | 28, 46, 53-54, 66 |

## Stage 9: accuracy against the code

**Verdict: all eight fail.** The names mostly exist; the errors are in how the pieces behave
together. Reviewers read the code and ran nothing.

| Document | Blockers | Majors | Nits |
|---|---|---|---|
| CAR | 3 | 12 | 7 |
| WEAK | 0 | 11 | 8 |
| RES | 1 | 15 | 7 |
| WIN | 2 | 13 | 6 |
| KNOW | 4 | 15 | 5 |
| BEH | 2 | 14 | 8 |
| TRK | 5 | 13 | 6 |
| SHD | 4 | 5 | 3 |

### New in this stage

| Document | Finding | Evidence | Check |
|---|---|---|---|
| CAR, WEAK | **`pi` on stands is what the preflight refuses**: `/vehicle/odom` reads the front wheels, the car drives the rear, so the loop raises the throttle. Fixed in both designs. `legacy.yaml:45` still says "until pi is tried on stands" | `safety.py:311-324`; `vehicle.yaml:64-67` | checked |
| CAR | The Rust ESP32 has no wheel speed and no feed-forward, so "the loop into the ESP32" is a port, not a move | `esp32-umod/src/main.rs:34, 110` | reviewer |
| CAR | Day A's runbook has no chrony or `speed_loop` step; there are six computers, not four | `car-day.md:54-60` | reviewer |
| WEAK, KNOW | Today's car: ρ is **1.0 s**, a 1.5 m path; 0.9 s is the future spine | `geofence.py:178-179`; `legacy.yaml:8` | reviewer |
| WEAK, CAR | The car discards the detector's `person` class unless `camera_obstacles` is on | `car.launch.py:268, 297-311` | reviewer |
| WEAK | `min_points: 3` means three cubes, and belongs to the collision monitor; `stop_signs.yaml` doesn't exist | `nav2.yaml:590`; `stop_sign.py:52` | reviewer |
| WEAK | Reversing is on where the lidar watches behind; the street graph is in `maps/routes/` | `car.launch.py:541-545`; `get.sh` | reviewer |
| RES | The lidar moved lower and **rearward**. The 0.5 m box stays in view to 3.8 m from the lidar | `vehicle.yaml:144` | reviewer |
| RES | A radar ray can't clear a lidar mark: separate layers. "Nothing new" is wrong | `nav2.yaml:201-275` | reviewer |
| RES | The harness flag is `--speed 3`; `measure controllers` can't pass arbitrary parameters | `controller_compare.py:937-979` | reviewer |
| RES | The guard's own acceptance on 2 Nov was about 76 %, not 63 % | `trials.md:686-688` | reviewer |
| RES | The Gazebo NDT map comes from truth, so a KISS-ICP map is untested | `ndt_map.py:20, 57` | reviewer |
| WIN | `demo` appears to open **two** RViz windows: step 1 needs two changes | `demo_all.sh:86`; `sim.launch.py:362` | checked in part |
| WIN | Turning RViz off first removes `demo`'s only click-to-go | `map-app/main.rs:417-439` | reviewer |
| WIN | Plain `demo` runs no NDT, AMCL, ICP or tracker, so those panels are empty | `demo_all.sh:40-53` | reviewer |
| WIN | The cockpit sends goals in the sim; only the car's bridge is watch-only | `foxglove.md:148-151` | reviewer |
| WIN | `/system/algorithms` reports what was asked for, not what is alive | `aav_run_info/README.md:52-53` | reviewer |
| KNOW | `max_brake` as a map raises `TypeError` in five readers | `vehicle.py:210, 422`; `geofence.py:213` | reviewer |
| KNOW | Stopping at h = 0 parks inside NEAR, which only a person can clear | `geofence.py:226-233, 392-394` | reviewer |
| KNOW | `drive.acceleration` is a limit, not the deceleration asked for | `ackermann.py:95-101` | reviewer |
| KNOW | `brake` (4.3) gives no `max_brake` fit on today's car | `actuator-tests.md:123-133` | reviewer |
| KNOW | With today's holds there's nothing to filter on the car | `geofence.py:185-195` | reviewer |
| BEH | The law is misquoted: `√(2a(d − lead·v))`, plus creep and stop band | `approach.py:10, 76` | reviewer |
| BEH | `measure controllers` has no jerk column; ASK has no reply path | `atob_score.py:279`; `aav_hud/README.md` | reviewer |
| BEH | TODO 100's stock speed filter publishes on the same `speed_limit` topic | `speed_filter.cpp:69` | reviewer |
| TRK | No `--walker` flag; the bench uses `aav_bench`'s `mock_radar` | `bench.launch.py:131` | reviewer |
| TRK | `plan_around` is on, so the planner can route round a locked walker | `navigation.launch.py:447` | reviewer |
| SHD | No sender for goals on the car; `shadow_lock` has no package | `controller_compare.py:124-130` | reviewer |
| SHD | The HUD's GO / STOP has no lock input, so it won't show SHADOW | `gate.rs:4-8` | reviewer |

### Reuse the designs miss

| For | Existing code |
|---|---|
| **One stopping law** | `approach.Approach`, `SpeedPolicy`, `turn_speed_limit`; `dynamics.stopping_distance`, `dynamics.braking_limit`; `geofence.py` (no ROS imports): `stopping_distance`, `motion_from`, `depth` |
| A QP, if one is needed | `aav_track/qp.py` (Clarabel isn't a dependency) |
| Easing off near the stop zone | the stock `FootprintApproach` polygon, `nav2.yaml:596` |
| The sign's distance | `sign_distance_m`, `stop_sign.py:39`, called only by tests |
| Moving things, no firmware swap | the out-of-box cloud's per-point `velocity`, with `aav_radar_clusters` |
| A person's distance | `ground.box_points`, `ROAD_USERS`, `recent.Recent` |
| Blind-zone memory | stock `observation_persistence` (0.0 at `nav2.yaml:305`) |
| The window | `goal_for`, `map_core::view`, `grid.rs`, `debug-core/swap.rs`, `pick.py`'s rows, the chase camera |
| Shadow scoring | `atob_score.read_bag`; `drive_metrics`; the geofence's heartbeat lock pattern |
| Fits and σ | `analysis.py`, `reports.py`, `braking_imu`, `wheel_check.py` |

## What to do, in order

| # | Do | Why |
|---|---|---|
| 1 | Keep `speed_loop.mode: open`. Gate the mode switch on a driven-wheel speed and measured braking. Fix `legacy.yaml:45` | a risk in today's code, not a design |
| 2 | Write **how the car stops**: one law from the existing pieces; the cap never 0; a handshake with the sign's watcher; waits over 10 s; `h` with margin and σ; trims upstream of twist_mux; ρ per backend | Ben's first pick; resolves blockers 1-3 |
| 3 | The radar: a bench test before any tracking design. No firmware or cfg change on the car until then | it can turn the stop zone's input 90° |
| 4 | The window: keep a click-to-go before RViz goes; two changes to turn it off; design SWAP properly | what Ben asked for; less to build than first feared |
| 5 | Every design: alternatives, risks, non-goals, what's still Ben's to answer | the standard's required sections |
| 6 | One schedule, in CAR; bring RES and WEAK up to the 5 Nov direction; one home per fact | copies have already drifted |
