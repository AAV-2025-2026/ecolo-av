# The full simulation: the whole car in Gazebo

Written 15 October 2026, for Ben. The goal (Ben, 15 Oct): "fully simulate the car inside
Gazebo with all the sensors, and build the full pipeline." This page says what we have,
what's missing, and how the car's measurements feed in.

> **The short version**
> - **Most of it exists.** Gazebo already plays the car: IMU, GPS, wheel speed, three cameras, the radar, the lidar. The same EKFs, Nav2, perception and HUD run on it.
> - **The big gap is the actuators.** Gazebo's car sets its speed directly, with made-up limits. It ignores the weight, the motor and the brakes. So it doesn't yet speed up, brake or steer like the real car.
> - **The fix:** an **actuator model** between our commands and Gazebo, filled with the numbers from the tests (`READ-ME-TESTS.md`, stage 4). Then the real firmware logic **in the loop**, as the bench already does.
> - **Measurements come first:** the sheet (`READ-ME-MEASURE-THE-CAR.md`) for where everything is, the tests for how it moves.

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
| Lidar (roof) | ✅ a generic 16-beam one, `lidar:=true` | its real model (probably a Velodyne); **nothing reads it yet**: it should feed Nav2's costmap and the collision monitor |
| **Throttle and brake** | ❌ Gazebo sets the speed itself | **an actuator model**: throttle % → acceleration, brake % → deceleration, from tests 4.1-4.4 |
| **Steering** | ❌ an instant, perfect steer | **its speed, lag, centre offset and real angles**, from tests 3.10-3.12 and 4.5 |
| Weight | in the model, but hardly matters (see the box below) | the real weight (scales, M7) |
| The firmware's safety logic | ❌ skipped in Gazebo (the bench has it) | **the spine in the loop**: CAN frames, timeouts, e-stops, as on the bench |
| What's real and what's fake | ❌ looks the same as the car | **`/system/source` and a SIMULATED banner** on the HUD |
| Per-actuator readings | bundled in `/vehicle/status` | `/vehicle/steering`, `/vehicle/throttle`, `/vehicle/brake`, `/vehicle/wheels` |
| The world | a test road, an empty lot | **a copy of the real test lot** |
| Sensor failures | ❌ | make a sensor fail on purpose (a frozen camera, a lost GPS), and check the car stops, loudly |

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
| 1 | `/system/source` + the SIMULATED banner | no | small |
| 2 | Per-actuator readings: `/vehicle/steering`, `/throttle`, `/brake`, `/wheels` | no | small |
| 3 | **The actuator model (A)**, with guessed numbers for now, in `vehicle.yaml` | no; the numbers later | 1 day |
| 4 | **The spine in the loop**: ego → CAN → the spine's logic → the actuator model → Gazebo | no | 1-2 days |
| 5 | The lidar into Nav2's costmap and the collision monitor | no | small |
| 6 | Sensor failures on purpose, and checks that the car stops | no | 1 day |
| 7 | The actuator test script (`READ-ME-TESTS.md` 1.10), run in Gazebo | no | 1 day |
| 8 | Fill in the real numbers: measurements and tests | **yes**: Friday, then the lot | - |
| 9 | A Gazebo copy of the test lot | the lot chosen | 1 day |
| 10 | B, forces in Gazebo, only if needed | the real numbers | a week |

Steps 1-7 can all be built before the car is measured: they start with today's guesses,
and step 8 swaps in the real numbers without changing any code.
