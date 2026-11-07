# The car that knows itself: measured numbers, a brake-health monitor, the maths of a safety filter

* **Author:** Ben (the pick), written up 5 Nov 2026
* **Date:** 2026-11-05
* **Status:** Parts 1 and 2 proposed; awaiting Ben. Part 3 now lives in the
  **how the car stops** design. Part 4 is a proposal. Research A of
  [the weak links](2026-11-04_weak-links.md); TODO 104. EGM findings folded in, 5 Nov.

## What Ben has decided

| Ben said | What it means here |
|---|---|
| 4 Nov: "all 5 are important ... CBF filter (i just don't know what this is)" | the filter stays |
| 5 Nov: "we want to keep all the algo but we want to create a new best hybrid for each" | nothing here replaces an algorithm |
| 5 Nov: how the car stops comes first; stock stays the default, ours challenges | that design owns the one stopping law; everything here is off by default |

Everything else on this page is **proposed; awaiting Ben** (see [Questions](#questions-for-ben)).

## The idea in one line

Measure how the car really stops, keep checking it while it drives, and give the stopping
design true numbers.

```text
   MEASURE                     WATCH                        USE
   test 4.3, repeated  ──►  vehicle.yaml  ──►  brake monitor  ──►  the stopping design's filter
   value + sigma            flat keys          r = real / model     the trust cap (Nav2 only)
                                               WEAK, FAILED         the fence's trip point (K5)
```

## Goals and non-goals

| Goals | Non-goals |
|---|---|
| replace guessed stopping numbers with measured ones, with an error bar | writing the stopping law: the stopping design owns it |
| notice a weak brake while driving | a filter on today's car: there is nothing to filter yet ([Step E](#step-e-the-closed-loop)) |
| state the maths any filter must meet | trimming people or tests |
| say which locks change | steering barriers (sideways): later, if ever |
| | telling a bad brake from ice: both stop long, and both count |

## Step E: the closed loop

The entry step for the monitor and the filter **on the car**. Gazebo's loop is closed
already, so Gazebo work doesn't wait. Today the car can't use either:

- `speed_loop.mode` is `open`: the brake acts only below `stop_speed`, so a trim just coasts.
- The no-timeout lock and the geofence's COASTING hold every program, so nothing is left to filter.

| Step | Do | Unlocks | Owner |
|---|---|---|---|
| E1 | flash the Rust ESP32 firmware, frame version 2 or more, pass test 3.9 | the no-timeout lock lifts | team |
| E2 | a driven-wheel speed (TODO 49b) | `pi` on stands; the preflight refuses it until then (`safety.py`) | hardware lead |
| E3 | `pi` on the ground, test 4.3; paste `pi_loop_decel` | COASTING lifts (`geofence.py` `coasts`, `measured_stop`) | team |
| E4 | a brake level or demand reaches ROS: the uplink (H9), or K6 | the monitor can watch; `max_brake` can be fitted | hardware lead, team |

The spine gives E1 and E4 by itself, and the geofence doesn't count it as coasting. Run
test 4.3 there too.

## Part 1: measure

### What each setup can give

From `docs/actuator-tests.md` and `reports.py`. On the car the tests stop at 1 m/s, so the
stops are from 0.5 and 1 m/s, not 2 or 3.

| Number | Test | Today: `open`, no uplink | `pi`, with K6 or the uplink | Spine |
|---|---|---|---|---|
| `open_loop_decel` | 4.3 | **yes** | | |
| `pi_loop_decel` | 4.3 | | **yes** | |
| `max_brake`, `brake_lag` | 4.3 | **no**: only the whole stop's timing, no `vehicle.yaml` line | **yes** (`brake_imu`, or the level) | **yes** |
| `max_accel` | 4.1 | the gain only (speed ÷ `full_throttle_speed`) | the same; better with the uplink | **yes** |
| `throttle_lag` | 4.1 | only if the wheel pulses resolve it | the same; better with the uplink | **yes** |
| `drag` | 4.2 | **no**: a low command pushes, 0 brakes | to check | **yes** |
| `steer_rate`, `steer_lag` | 3.11 | by video only | with the uplink and the steering actuator's feedback | **yes** |
| see-delay ρ_see | new: stamps | **yes**, on the Orin | **yes** | **yes** |

Until `drag` is measured, the guess (0.1 1/s) is 5 % of a 2 m/s² stop at 1 m/s.

### The error bar

| Rule | Why |
|---|---|
| σ = the **spread between repeat stops**: at least 5 per speed, same surface, same load | a fit's residual (`rms` in `Report.suggest`) says how well the curve fits one run, not how much the stop varies |
| Computed from the runs' reports (`reports.py`, `analysis.stopping`, `braking_imu`), read back with `actuator-test --analyse` | no new fitting code |
| The tests **print** the lines; a person pastes them | they feed lock margins, and today's tools never write the file (`reports.yaml_lines`). So no `--fit` writer. `vehicle_model.py --set` is a what-if: it doesn't write either |

### `vehicle.yaml`: flat keys

`max_brake` as a map would raise `TypeError` where readers call `float()` on it
(`vehicle.py` twice, `geofence.py`, `legacy.launch.py`, `drive_to_point.launch.py`). So the
value stays, with a sibling:

```yaml
actuators:
  max_brake: 2.6         # m/s^2. MEASURED test 4.3, 5 stops each from 0.5, 1 m/s (example)
  max_brake_sigma: 0.3   # m/s^2: the spread of those stops (example)
  brake_lag: 0.2
  brake_lag_sigma: 0.05
```

| New key | Who reads it |
|---|---|
| `max_brake_sigma`, `brake_lag_sigma`, `pi_loop_decel_sigma` | the filter |
| `brake_ratio_sigma`: σ_r, the spread of r over the repeat stops | the monitor |
| `see_delay`, `see_delay_sigma` (a new flat `timing:` section) | the filter, the cap |

Each new `actuators` key also goes in `NOT_LINEAR` (`vehicle_model.py`) and `IGNORED`
(`actuator_model.py`): `test_vehicle_model_tool.py` checks. No sigma key: the filter refuses
to start on the car, and the monitor stays NOT_WATCHING.

## Part 2: watch: the brake-health monitor

### What it compares

`/ego/actuator_cmd`'s `acceleration` is a **limit**, not a demand (`ackermann.py`), so it can't
be the prediction. A closed loop also hides weakness: it just brakes harder. So r compares the
brake's **strength**, not the stop:

```text
   B(t)   brake level, 0..1: /vehicle/brake measured; else its command through brake_lag
          (analysis.lag_response)
   D(t)   real deceleration = −(ax(t) − ax_before) − drag·v(t)     (as braking_imu)

   r  =  ∫ D dt  /  ∫ B(t)·max_brake dt      over one event
```

`ax_before` is the IMU's mean over the steady second before the event: it takes off the
slope and the bias. With the brake halved, r is 0.5 however hard the loop pushes.

### What counts as an event

| Condition | Value (placeholder until 4.3) |
|---|---|
| brake on and throttle 0, throughout | |
| start speed | ≥ 0.4 m/s |
| predicted loss of speed | ≥ 0.4 m/s |
| mean predicted deceleration | ≥ 0.5 m/s² |
| a steady second before it, every input fresh, going forward | required |
| who is driving | anyone: a person's stop counts too |

There is no minimum duration: ego's stop from 1 m/s lasts 0.5 s.

### Signal strength at 1 m/s

Worked from the model. The IMU's real noise on the car isn't known yet.

| Stop | Deceleration | Lasts | Rolls | Wheel pulses (0.14 m each) | Counts? |
|---|---|---|---|---|---|
| ego's full stop | 2 m/s² | 0.5 s | 0.25 m | 2 | yes |
| half of that | 1 m/s² | 1 s | 0.5 m | 4 | yes |
| a filter's easing | about 0.4 m/s² | about 4 s | about 2 m | 14 | **no**: too weak |

| What it means | Rule |
|---|---|
| the wheels can't see a short stop: `encoder_udp` averages over 0.5 s | r uses the IMU; the wheels are only a cross-check on stops over 1 s |
| a 1° slope is 0.17 m/s²: 9 % of a 2 m/s² stop | hence `ax_before` |
| a smooth car makes few events | the **check stop**: `actuator-test brake --speeds 1.0`, run by a person at the start of a session |
| r might be too noisy to use | σ_r from 4.3. Over 0.1: the monitor stays NOT_WATCHING and says why |

### The states

r3 = the median of the last three events. One bad reading can't change the state, and two
weak stops can. There is no running mean: a five-event mean of three halved stops is only
0.7, which would miss its own check.

| State | When | Factor on b | Lock |
|---|---|---|---|
| NOT_WATCHING | `open` mode; or no brake level; or no sigma key; or σ_r over 0.1 | 1.0 | open |
| UNPROVEN | watching, under 3 events since start | r_weak | open |
| OK | r3 ≥ r_weak | 1.0 | open |
| WEAK | r_fail ≤ r3 < r_weak | r3 | open |
| FAILED | one event under r_fail | r_fail | **on** |

| Number | Value |
|---|---|
| r_weak | 0.7, a placeholder. Set from 4.3: at most 1 − 3·σ_r |
| r_fail | 0.4, a placeholder |

| Change | Rule |
|---|---|
| OK → WEAK | r3 under r_weak |
| WEAK → OK | r3 ≥ r_weak + 0.1 (by itself: a wet drum dries). Between the two, WEAK stays |
| UNPROVEN → OK or WEAK | the third event: r3 decides |
| any → FAILED | one event under r_fail |
| FAILED → WEAK | a person clears it, standing still; three new events then decide |
| restart | UNPROVEN: it can't remember FAILED, so it assumes weak |
| r over 1 | noted; never shrinks a margin |

### What it does in `open` mode

The brake acts only below `stop_speed`, so B is 0 while the car coasts, and no event is ever
counted. It says NOT_WATCHING, gives factor 1.0, keeps its lock open and shows
"BRAKE NOT WATCHED" on the HUD. It never reads coasting as FAILED. COASTING is what protects
the car in this mode.

### FAILED's contract

| Question | Answer |
|---|---|
| Holds | every program: scripted, buttons, replay, point, Nav2, AI |
| Never holds | people; the actuator tests (they re-measure the brake) |
| How the car stops | the lock silences programs, so ego stops. The brake is the weak part: the HUD says BRAKE FAILED and tells the safety driver to take over |
| Clearing | `pixi run clear brake-health`; a person only; refused while moving |
| Mechanism | twist_mux lock `brake_health`, priority 51, timeout 1 s, sent at 10 Hz (the geofence's pattern) |

### When it fails

| Failure | What happens |
|---|---|
| the node dies or hangs | 1 s of silence closes the lock: programs held |
| IMU or brake input silent | no new events; state and factor stay; the state text says stale. The watchdog already stops on the IMU |
| factor silent | readers keep the lowest factor they've seen |

### Steering: STEER SLOW

Commanded against measured steering rate (`/vehicle/steering`). Needs the uplink or the spine.
A HUD line only: no lock, no factor.

### Home and contract (K4: proposed; awaiting Ben)

Node `brake_health`, in `aav_safety`: `brake_health.py` (no ROS, tested) and
`brake_health_node.py`, beside the geofence, which has the same lock pattern. Off by default
(`brake_health:=true`). The launch reads the mode and the numbers as `motion_from` does.

| Topic (contract first) | Type | Dir |
|---|---|---|
| `/ego/actuator_cmd`, `/vehicle/odom`, `/vehicle/brake`, `/vehicle/steering`, `/sensors/imu/data` | | in |
| `/safety/brake_health/lock` | `std_msgs/Bool`, 10 Hz | out |
| `/safety/brake_health/state` | `std_msgs/String`: `STATE: why` | out |
| `/safety/brake_health/factor` | `std_msgs/Float32`: 0 to 1, multiplies b | out |
| `/diagnostics` | r, r3, the last events | out |
| `/safety/brake_health/clear` | `std_srvs/Trigger` | serves |

**A new sim fault, `brake weak`:** `gazebo_adapter` scales `max_brake` in its actuator model,
and `tools/sim_fault.sh` routes `brake` to that node. Today's faults cover sensors only.

## Part 3: the filter

The filter's equation, placement (K1), worked table and rules now live in [how the car
stops](2026-11-05_how-the-car-stops.md), with the one stopping curve. This page supplies what it
needs: the σ from Part 1 and the factor `r` from Part 2.

CBF = *control barrier function*: a bumper made of maths.

### Which locks change

The filter adds no lock and changes none. The rest of this page does:

| Lock | Change |
|---|---|
| `estop` 255, `no_timeout` 60, `stop_sign` 30, `sensors` 30, `stop_zone` 21 | none |
| `geofence` 51 | **proposed, K5:** on WEAK, its b drops, so NEAR closes earlier: `braking(ego, r·max_brake)`. At r = 0.5: 1.57 m, not 1.4 m. A new input to a safety node |
| `brake_health` 51 | **new**: this page takes twist_mux from six locks to seven |

## Part 4: drive as fast as you can trust (a proposal)

The behaviour layer's speed cap on Nav2's `speed_limit` topic: the lowest of these.

| Signal | Cap | The signal exists? |
|---|---|---|
| everything OK | the configured cruise (1 m/s) | yes |
| the EKF's σ over 1 m | 0.5 m/s | yes: `/localization/odom/global` |
| NDT LOST | 0.5 m/s | only when NDT runs: off by default |
| something moving within 8 m | 0.3 m/s | **no**: waits, as its barrier does. Must reach further than any lock |
| monitor WEAK | half the cruise: 0.5 m/s | with Part 2. Still fast enough to make events, so it can recover |
| monitor FAILED | the floor | with Part 2. The lock does the stopping |
| ρ_trim + ρ_see over 1.2 s | 0.5 m/s | a measured number, read at start-up; not live |

| Rule | Why |
|---|---|
| **Never publish 0.** Floor: 0.1 m/s | to Nav2, 0.0 means **no limit** (`NO_SPEED_LIMIT`, `SpeedLimit.msg`): the car would speed up |
| A cap slows; it doesn't stop | stops are the filter's or a lock's |
| Reaches Nav2 only | the point driver and AI get only the filter |
| One publisher on `speed_limit` | stock `SpeedFilter` (TODO 100) uses the same topic (`speed_filter.cpp:69`) |

## Alternatives

| For | Alternative | Why not (yet) |
|---|---|---|
| Part 1 | a `--fit` writer | feeds lock margins unreviewed; the tools print on purpose |
| Part 1 | `max_brake: {value, sigma}` | breaks five readers |
| Part 1 | the fit's residual as σ | measures the fit, not the stop |
| Part 2 | offline only: score stops from bags | cheap, and a first step; but says nothing during the drive |
| Part 2 | inside `sensor_watchdog` beside `wheel_check.py` | its lock is priority 30: it wouldn't hold scripted, buttons or replay |
| Part 2 | deceleration against demand, not brake strength | a closed loop hides it. At half brake, 1.5 against 2.0 gives 0.75: never WEAK |
| Part 3 | see [how the car stops](2026-11-05_how-the-car-stops.md) | |
| Part 3 | the lock's own curve as the barrier | it hardly shrinks with speed, so it asks for a sudden stop at the cap |
| Part 4 | no cap: the filter alone | the filter trims only near a barrier; a cap covers doubt about the numbers |

## Risks

| Risk | Mitigation |
|---|---|
| ice or a wet drum reads as a bad brake and blocks a winter drive | the stop really is longer. A person clears it; it drops to WEAK. Thresholds come from dry stops: say so in the winter tests |
| a smooth car makes too few events | the check stop; UNPROVEN assumes weak until proven |
| IMU noise or mounting drowns r | σ_r gate; `imu_link` orientation is still a TODO; void the event if there's no steady second |
| one wrong number moves the filter, the monitor and the cap together | the geofence keeps its own halved b; K5 is a separate decision; a person pastes each number |
| the filter hides the locks, so they stop being tested | off by default; every release runs the fence check with it off |
| two trims fight (collision_monitor, cap, filter), or Nav2 gives up | only lowering is allowed; the stopping design handles waits over 10 s |
| a frozen barrier leaves the car crawling | the HUD and `/safety/barrier/state` say which barrier; the locks still act |
| guessed numbers look measured | the filter refuses to start on the car without sigma keys |

## Checks

Nothing here has been run. The model figures above came from a throwaway script.

| Test | Pass |
|---|---|
| `brake_health.py`: every state and change above, with made-up events | unit tests |
| `barrier.py`: the worked table to 0.01; `L(v) ≥ S_lock(v)`; curvature kept; never raises; freeze on stale, per barrier | unit tests |
| Gazebo, `brake weak` | WEAK by the third event; r between 0.4 and 0.6 with the closed loop on; mended: OK after three more |
| the ESP32 stand-in (`gazebo_esp32`) in `open`, if it can run that way; else a unit test | NOT_WATCHING; never FAILED |
| kill `brake_health` by its process group | programs held within 1.2 s; the joystick still drives |
| Gazebo, the fence at 1 m/s, filter off | NEAR closes (today) |
| Gazebo, the fence at 1 m/s, filter on | NEAR doesn't close; the car stands clear of NEAR's distance, and keeps its lock open |
| Gazebo, the filter's speed output | slope changes under 1 m/s³ down to 0.1 m/s (`max_jerk` covers only speeding up, so this is its own check) |
| Gazebo, stop zone with a box, `FootprintApproach` on, then the barrier | each eases before the zone; the numbers compared |
| the joystick through a running filter | its commands unchanged |
| the stop error, measured against guessed numbers (`measure atob`) | recorded, either way |

## Order

1. Gazebo: repeat-stop σ in `reports.py`, the flat keys. No car needed.
2. Gazebo: the monitor, `brake weak`, the HUD line.
3. The car: test 4.3 in `open` (`open_loop_decel`), then [Step E](#step-e-the-closed-loop).
4. The car: test 4.3 in `pi`, repeated: the real numbers with σ. The monitor with its lock off,
   then on.
5. **[How the car stops](2026-11-05_how-the-car-stops.md)** builds the filter: Gazebo first, `FootprintApproach`
   first.
6. The cap, with the behaviour layer.
7. The car: the filter computing but not trimming (watch `/safety/barrier/state`), then on.

## Questions for Ben

All **proposed; awaiting Ben**. The right-hand column is a recommendation, not an answer.

| # | Question | Recommended |
|---|---|---|
| K1 | Where does the filter go? | upstream of twist_mux, on Nav2, point and AI. Not in ego |
| K2 | Speed only first? | yes: a formula, testable |
| K3 | The filter's home? | its own package, `aav_barrier`, Python, off by default; final say in the stopping design |
| K4 | The monitor's home? | `brake_health` in `aav_safety` |
| K5 | Does WEAK move the fence's trip point? | yes, after Gazebo. It changes a lock, so it's your call |
| K6 | May `legacy_uart_bridge` publish its brake demand in `pi` without the uplink? | yes: `/vehicle/brake`, `command` only, `measured` NaN. Gives `max_brake` and the monitor without waiting for H9 |
| K7 | A seventh lock for FAILED? | yes, priority 51, with silence holding programs |
| K8 | Should a person run a check stop each session? | yes, until events prove common enough |

## Related

[One car](2026-11-04_one-car.md) (section 2), [the weak links](2026-11-04_weak-links.md)
(section 5), [the control plan](2026-10-27_control-plan.md), `docs/geofence.md`,
`docs/actuator-tests.md`, `docs/vehicle-model.md`. Papers: Ames et al. 2017, 2019;
Taylor and Ames 2020; Isermann 2006; Shalev-Shwartz et al. 2017 (RSS).
