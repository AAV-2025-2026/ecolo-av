# The full simulation: the whole car in Gazebo

Written 15 October 2026, for Ben. The goal (Ben, 15 Oct): "fully simulate the car inside
Gazebo with all the sensors, and build the full pipeline." This page says what we have,
what's missing, and how the car's measurements feed in.

> **The short version**
> - **Most of it exists.** Gazebo already plays the car: IMU, GPS, wheel speed, three cameras, the radar, the lidar. The same EKFs, Nav2, perception and HUD run on it.
> - **The big gap is the actuators.** Gazebo's car sets its speed directly, with made-up limits. It ignores the weight, the motor and the brakes. So it doesn't yet speed up, brake or steer like the real car.
> - **The fix:** an **actuator model** between our commands and Gazebo, filled with the numbers from the tests (`READ-ME-TESTS.md`, stage 4). Then the real firmware logic **in the loop**, as the bench already does.
> - **Measurements come first:** the sheet (`READ-ME-MEASURE-THE-CAR.md`) for where everything is, the tests for how it moves.

## Status (15 Oct, branch `wt/full-sim-1`)

| # | Step | Status |
|---|---|---|
| 1 | `/system/source` + the SIMULATED banner | ✅ built: Gazebo, turtlesim, the bench, the car's backends and replay announce; the raylib HUD shows the banner and a tag per topic |
| 2 | `/vehicle/steering`, `/throttle`, `/brake`, `/wheels` | ✅ built: Gazebo all four; the bench and the car (spine_bridge) steering, throttle, brake; turtlesim steering |
| 3 | The actuator model (A), guessed numbers | ✅ built: `aav_gazebo/actuator_model.py`, numbers in `vehicle.yaml` `actuators:`, on by default (`actuator_model:=false` for the old car) |
| 4 | the spine in the loop | not started |
| 5 | The lidar into Nav2 | ✅ 15 Oct: `lidar_scan` (`aav_lidar`) flattens the roof lidar into a 2D scan; the local costmap's `lidar_layer` and `collision_monitor` read it. `lidar:=true` in Gazebo, **off on the car** (no lidar driver yet). With the radar off, the lidar alone stopped the car 0.16-0.55 m before a post |
| 6 | Sensor failures on purpose | ✅ 15 Oct: `pixi run sim-fault <sensor> <fault>`, and the sensor watchdog (`aav_safety`): it stops Nav2 and the AI slot, and says why on the HUD. All 10 faults stop the car within 4.1 s ([the table](#sensor-failures-before-and-after)) |
| 7 | The actuator test script (`READ-ME-TESTS.md` 1.10) | ✅ 15 Oct: `pixi run actuator-test <test> --sim`, all 9 tests in Gazebo; they give back the model's numbers ([docs/actuator-tests.md](docs/actuator-tests.md)). It found Gazebo's IMU blind to the car's acceleration: fixed in `gazebo_adapter` |
| 8-10 | the real numbers, the test lot, forces | not started |

Tested (15 Oct, Ben's Mac):

| Run | Result |
|---|---|
| `pixi run sim-check` (the model on) | ✅ all 6: graph vs contract (the new topics too), drive 6.01 m of 6.5 |
| `pixi run sim-check --obstacle --lane` | ✅ all: stood still 0.51 m before the box; lane keeping back within 5 cm in 5.4 s |
| `pixi run sim-check --obstacle --lidar-obstacle` (steps 5, 6 branch; twice) | ✅ the box: 0.32-0.46 m before it (radar and lidar); the post, radar off: 0.16-0.55 m before it, the costmap 100 of 100 there; both goals reached once they were gone |
| `pixi run sim-check --faults` | ✅ all 10 faults: the car stood still 1.7-4.1 s after each, the watchdog (or `collision_monitor`, for the radar) said why, and let go once mended |
| `pixi run bench-check` | ✅ all 6, graph vs contract with the bench's new topics |
| turtle profile vs contract | ✅ `/system/source` and `/vehicle/steering` from `turtlesim_adapter` |
| Gazebo with `actuator_model:=false` | ✅ the old car: no throttle or brake (NaN), an instant steer |
| The HUD's banner | ✅ its logic (`cargo test`); ❌ not seen on screen: the window couldn't open from that session |

What's where:

| Thing | Where |
|---|---|
| The messages | `aav_interfaces`: `DataSource` + `SensorSource` (REAL, SIM, BENCH, REPLAY per sensor), `ActuatorState` (command + measured), `WheelSpeeds` |
| The contract | `docs/interfaces.yaml`; `/system/` is a new topic area (`docs/naming.md`) |
| The model and its tests | `src/backends/aav_gazebo/aav_gazebo/actuator_model.py`, `test/test_actuator_model.py` |
| How it's documented | `docs/simulation.md`, "The actuator model"; `docs/hud.md` for the banner |

## 1. The full pipeline, in one picture

```text
  drivers (keyboard, joystick, Nav2, plain English)
        │
  twist_mux → ego ──────────── /ego/actuator_cmd (speed + steering)
        │
  ┌─────┴───────────────── TODAY in Gazebo ──────────┐   ┌──────── THE FULL VERSION ────────┐
  │ gazebo_adapter → Gazebo sets the speed directly  │   │ spine_bridge → CAN frames        │
  │ (fixed limits: +1.5 / −3.0 m/s², a quick steer)  │   │   → the spine's real logic       │
  │                                                  │   │     (timeouts, e-stop, limits)   │
  │                                                  │   │   → ACTUATOR MODEL: throttle,    │
  │                                                  │   │     brake, steering, as measured │
  │                                                  │   │   → Gazebo                       │
  └──────────────────────────────────────────────────┘   └──────────────────────────────────┘
        │
  Gazebo's sensors → /sensors/... → EKFs, Nav2, perception, HUD   (the same as the car)
```

## 2. What we have, and what's missing

| Part | Today in Gazebo | Missing for the full version |
|---|---|---|
| IMU, GPS, wheel speed | ✅ with noise | noise levels from the real devices (Friday) |
| 3 cameras | ✅ 15 Oct: two front, one rear | the real lens of each (N4); perception reads only the front left |
| Radar (grill) | ✅ a stand-in, shaped like the TI radar | its real config file, from the car |
| Lidar (roof) | ✅ a generic 16-beam one, on by default (15 Oct); ✅ Nav2's costmap and the collision monitor read it (step 5) | its real model (probably a Velodyne), and a driver for the car |
| **Throttle and brake** | ✅ 15 Oct: the actuator model, with **guessed** numbers | the real numbers, from tests 4.1-4.4 |
| **Steering** | ✅ 15 Oct: speed, lag, centre offset, deadband, with **guessed** numbers | the real numbers and angles, from tests 3.10-3.12 and 4.5 |
| Weight | in the model, but hardly matters (see the box below) | the real weight (scales, M7) |
| The firmware's safety logic | ❌ skipped in Gazebo (the bench has it) | **the spine in the loop**: CAN frames, timeouts, e-stops, as on the bench |
| What's real and what's fake | ✅ 15 Oct: `/system/source`, and the HUD's orange SIMULATED banner | - |
| Per-actuator readings | ✅ 15 Oct: `/vehicle/steering`, `/vehicle/throttle`, `/vehicle/brake`, `/vehicle/wheels` (and still `/vehicle/status`) | the real measured values from the car |
| The world | a test road, an empty lot | **a copy of the real test lot** |
| Sensor failures | ✅ 15 Oct: `pixi run sim-fault`, and the sensor watchdog stops Nav2 (step 6) | the same on the car, on stands: pull a cable |

!!! note "Why the weight hardly matters in Gazebo today"
    Gazebo's Ackermann system **sets the wheels' speed** and limits how fast it changes
    (`aav.gazebo.xacro`: 1.5 m/s² up, 3.0 down). A heavier car gets the same numbers. For the
    weight to matter, the model must push with a **force** (from the motor) against the
    **mass**. For driving well, what matters most is the **measured g**: how fast the real
    car speeds up and stops. The tests give that directly.

## 3. Two ways to model the actuators

| | A. An actuator model in front of Gazebo (recommended first) | B. Forces inside Gazebo |
|---|---|---|
| How | a small node: throttle % → acceleration, brake % → deceleration, steering with its speed and lag; then Gazebo's speed control as today | the motor's torque on the rear wheels, the brakes' torque, tyre grip, the mass |
| Weight matters? | through the measured g (which includes it) | directly |
| Effort | about a day | about a week, and tricky to tune |
| Good for | Nav2, the smooth stop, the actuator tests: everything we drive | slopes, skids, a heavy load |

**Recommendation:** A first, with its numbers in `vehicle.yaml` (a new `actuators:` section).
B only if A isn't close enough to the real car.

## 4. How the measurements feed the simulation

| From | Measured | Goes into | Changes in Gazebo |
|---|---|---|---|
| The sheet (`READ-ME-MEASURE-THE-CAR.md`) | wheelbase, track, wheels, body | `vehicle.yaml` → the model | how it turns; its outline for Nav2 |
| The sheet | each sensor's x, y, z and angles | `vehicle.yaml` → the sensor frames | what each camera, the radar and the lidar see |
| Scales (M7) | the weight, per wheel | `vehicle.yaml` | the model's mass (and B, later) |
| Tests 4.1, 4.4 | acceleration per throttle % | `vehicle.yaml` → the actuator model | how fast it speeds up |
| Test 4.2 | coasting | the actuator model | how it slows with no brake |
| Test 4.3 | braking g | the actuator model; the smooth stop | how fast it stops |
| Tests 3.10-3.12, 4.5 | steering: real angles, speed, centre | the actuator model | how it steers |

```text
 Friday: measure  →  vehicle.yaml  →  Gazebo behaves like the car  →  test in Gazebo  →  trust it on the car
```

## 5. The order to build it

| # | Build | Needs the car? | Size |
|---|---|---|---|
| 1 | `/system/source` + the SIMULATED banner ✅ 15 Oct | no | small |
| 2 | Per-actuator readings: `/vehicle/steering`, `/throttle`, `/brake`, `/wheels` ✅ 15 Oct | no | small |
| 3 | **The actuator model (A)**, with guessed numbers for now, in `vehicle.yaml` ✅ 15 Oct | no; the numbers later | 1 day |
| 4 | **The spine in the loop**: ego → CAN → the spine's logic → the actuator model → Gazebo | no | 1-2 days |
| 5 | The lidar into Nav2's costmap and the collision monitor ✅ 15 Oct | no | small |
| 6 | Sensor failures on purpose, and checks that the car stops ✅ 15 Oct | no | 1 day |
| 7 | The actuator test script (`READ-ME-TESTS.md` 1.10), run in Gazebo ✅ 15 Oct | no | 1 day |
| 8 | Fill in the real numbers: measurements and tests (`pixi run actuator-test`, on stands then in the lot) | **yes**: Friday, then the lot | - |
| 9 | A Gazebo copy of the test lot | the lot chosen | 1 day |
| 10 | B, forces in Gazebo, only if needed | the real numbers | a week |

Steps 1-7 can all be built before the car is measured: they start with today's guesses,
and step 8 swaps in the real numbers without changing any code.

## Sensor failures: before and after

Each fault while Nav2 drives at about 1 m/s, Gazebo's road world, 15 Oct.
Before: `pixi run sim-check --faults --no-watchdog`; after: `pixi run sim-check --faults`.
How to make one, and what the watchdog watches: [docs/simulation.md](docs/simulation.md#sensor-failures-on-purpose).

| Fault | Before: no watchdog | After: the watchdog |
|---|---|---|
| GPS lost (`gps stop`) | ❌ drove on: 10.6 m in 10 s, nothing said. The global EKF carried on from the wheels and IMU (1.1 m out) | ✅ stood still 3.8 s after it, 2.8 m on: "gps STALE" |
| GPS NaN (`gps nan`) | ❌ drove on 10.0 m, nothing said (navsat_transform drops NaN fixes: the same as lost) | ✅ 4.1 s, 2.8 m: "gps STALE (no fix)" |
| GPS jumps 20 m (`gps jump`) | ⚠️ stood still 2.2 s after it, but by accident (Nav2's plan jumped with the map position, 19.3 m out); nothing said | ✅ 1.7 s, 0.7 m: "gps JUMP 20.0 m in 0.20 s", held until a person clears it |
| IMU stopped (`imu stop`) | ❌ drove on 7.2 m, nothing said | ✅ 2.2 s, 1.1 m: "imu STALE" |
| IMU frozen (`imu freeze`) | ❌ drove on 8.4 m, nothing said | ✅ 2.8 s, 1.7 m: "imu FROZEN" |
| IMU NaN (`imu nan`) | ❌ drove on 7.7 m; the global EKF stayed 0.3 m from the truth | ✅ 1.8 s, 1.0 m: "imu NAN" |
| Wheels stopped (`odom stop`) | ❌ drove on 9.0 m, nothing said | ✅ 1.9 s, 0.9 m: "odom STALE" |
| Wheels NaN (`odom nan`) | ❌ drove on 6.3 m, nothing said | ✅ 1.7 s, 0.8 m: "odom NAN" |
| Camera frozen (`camera freeze`) | ❌ drove on 7.6 m; on the HUD a frozen picture looks live | ✅ 2.9 s, 4.5 m: "camera FROZEN" |
| Radar stopped (`radar stop`) | ✅ stood still 2.5 s after it: `collision_monitor`'s "invalid source" | ✅ the same, 2.5 s; the watchdog warns too |

"Nothing said": no warning in the log, nothing on the HUD (only the HUD's GPS line
turned STALE for a lost GPS). The after column is the last of three runs: the first
passed too; the second caught a false GPS jump (two fixes delivered at once), fixed by
timing jumps with the fixes' stamps, plus 5 m for their noise.

**What's left:** a watchdog that dies while all is well stops nothing; frozen wheel
odometry isn't caught; the EKF itself doesn't reject a GPS jump; the map window doesn't
show the verdict; and the same tests on the car, on stands.

## Faster drives in Gazebo (15 Oct)

`pixi run sim world:=test_lot sim_speed:=3`: ego and Nav2 up to 3 m/s (5 at most), in
Gazebo only. The real car keeps 1 m/s. Details: [docs/simulation.md](docs/simulation.md).
