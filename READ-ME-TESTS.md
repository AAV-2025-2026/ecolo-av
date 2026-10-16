# Every test we've talked about

Written 15 October 2026, for Ben and the team: every test from our talks, in one place,
in the order to run them. Each one says what it proves, how to run it, and when it passes.

> **The short version**
> - **Five stages**, safest first: the simulator, the bench, the car on stands, the car in an empty lot, then the whole drive.
> - Never skip a stage: a test only runs once the stage before it passes.
> - **Status:** ✅ exists and passes; 🔧 exists, not yet run on the car; ⬜ still to build.
> - On the car, always: a safety driver, the e-stop in someone's hand, and a speed cap.

```text
 1 simulator  →  2 bench  →  3 car on stands  →  4 car, empty lot  →  5 the whole drive
 (Gazebo,        (stand-ins,   (wheels off the      (walking pace,       (A to B by GPS)
  turtle)         real CAN)     ground)              safety driver)
```

## Stage 1: the simulator (Gazebo and the turtle)

Nothing real moves. Run these on any laptop.

| # | Test | Run | Passes when | Status |
|---|---|---|---|---|
| 1.1 | The whole car graph in Gazebo | `pixi run sim-check` | all checks PASS: sensors, a 6.5 m drive, the EKF within 0.5 m of the truth | ✅ |
| 1.2 | All three cameras send pictures | part of 1.1 | front left 10 Hz; front right and rear 5 Hz or more, each in its own frame | ✅ 15 Oct |
| 1.3 | The roof lidar | `pixi run sim-check` (on by default) | 1800 × 16 rays at 10 Hz in `lidar_link` | ✅ |
| 1.4 | Stop for an obstacle | `pixi run sim-check --obstacle` | stops 0-2 m before the box; drives on when it's gone | ✅ at 272 kg; ⚠️ at 181 kg, unconfirmed (the Mac was overloaded) |
| 1.5 | Lane keeping | `pixi run sim-check --lane` | back to the lane's centre within 5 cm | ✅ 15 Oct |
| 1.6 | The HUD, with pretend data | `pixi run hud-demo` | the window opens with speed, camera, GPS, e-stop | ✅ Ben, 15 Oct |
| 1.7 | The HUD with the turtle | `pixi run turtle`, `pixi run hud`, `pixi run keyboard --local` | speed and steering move as you drive | ✅ Ben, 15 Oct |
| 1.8 | Plain-English driving | `pixi run -e llm talk`: "drive 10 m forward" | drives 10 m (±0.2 m) after you type yes | ✅ Gazebo |
| 1.9 | **"SIMULATED" on the HUD** | run Gazebo, look at the HUD | an orange SIMULATED banner; REAL / SIM tag per sensor | ⬜ |
| 1.10 | **The actuator tests (stage 3-4), in Gazebo first** | `pixi run actuator-test <test> --sim` ([docs](docs/actuator-tests.md)) | the script runs end to end and reports g and angles | ✅ 15 Oct: all 9 tests; they give back `vehicle.yaml`'s numbers |
| 1.11 | **The lidar alone stops the car** | `pixi run sim-check --lidar-obstacle` | radar off: stops 0-2 m before a person-sized post, which shows in the local costmap; drives on when it's gone | ✅ 15 Oct: 0.16-0.55 m before it |
| 1.12 | **Sensor failures on purpose** | `pixi run sim-check --faults` (`--no-watchdog`: what happens without the watchdog) | each of 13 faults (GPS lost, NaN, jump; IMU stopped, frozen, NaN; wheels stopped, frozen, NaN; camera frozen; radar stopped; the watchdog hung, killed) stops the car within 6 s (frozen wheels: 10 s from when they go wrong), and says why; normal driving never trips the wheels' cross check | ✅ 15 Oct: all 13 |
| 1.13 | **The spine in the loop** | `pixi run sim-check --spine` | in Gazebo with `spine:=true`: the normal checks pass; ego's commands stopped → the spine brakes fully within 0.28 s and latches; `/safety/estop` and the hardware e-stop → brake within 0.15 s, latched until armed again; disarmed → no motion | ✅ 15 Oct: full brake 195-209 ms, e-stops 1-12 ms |
| 1.14 | **Drive to a GPS point, smooth stop** | `pixi run sim-check --goto` ([A to B](READ-ME-A-TO-B.md)) | every stop within 2 m of B by Gazebo's truth, no overshoot, braking about half `max_brake`; a cancel, the e-stop and a GPS fault stop it | ✅ 15 Oct: all within 0.4 m |
| 1.15 | **Ghost obstacles: a pretend person only Nav2 sees** | `pixi run sim-check --ghost` ([docs](docs/ghost-obstacles.md)) | a ghost 15 m ahead (nothing in Gazebo): stops 0-2 m before it (the stop zone or the controller), the local costmap marks it; drives on once it's off | ✅ 16 Oct: 0.21 m before it, the stop zone fired (one run, radar and lidar on too) |

## Stage 2: the bench

The car's software path with stand-ins for the hardware, and the real CAN frames.

| # | Test | Run | Passes when | Status |
|---|---|---|---|---|
| 2.1 | The whole car graph, e-stops included | `pixi run bench-check` | 7 of 7 | ✅ |
| 2.2 | The test suite | `pixi run test` | all green | ✅ |
| 2.3 | **Replay a real drive** through our EKFs | `ros2 bag play` a recording from the car | the EKFs' path matches the GPS track | ⬜ needs a recording from stage 3 or 4 |

## Stage 3: the car on stands (wheels off the ground)

**Before:** all four wheels off the ground; the e-stop in someone's hand; the 2025-26 drive
software stopped; speed capped (`max_speed:=0.3`).

### 3a. Does it obey? (READ-ME-FRIDAY.md part 5)

| # | Test | Expect | Status |
|---|---|---|---|
| 3.1 | Nothing pressed | wheels still; the HUD shows 0 | 🔧 |
| 3.2 | Forward, gently | the drive wheels turn **forward**, slowly | 🔧 |
| 3.3 | Left | the front wheels turn **left** | 🔧 |
| 3.4 | Let go of the key | slows to 0 within 0.3 s; brake frames sent | 🔧 |
| 3.5 | The HUD's e-stop button | brakes at once; nothing moves until `pixi run estop-clear` | 🔧 |
| 3.6 | Stop the keyboard program | the bridge brakes: its commands go stale | 🔧 |
| 3.7 | Ctrl-C the Motor-Pi bridge | it sends a last stop frame | 🔧 |
| 3.8 | The Kar-Tech e-stop | everything stops | 🔧 |
| 3.9 | ⚠️ **Unplug the Motor-Pi's serial cable while driving** | the car brakes within 200 ms | ⬜ fails today: the ESP32 has no timeout (TEAM-TODO B2) |

### 3b. Steering, on stands

| # | Test | Measure | Passes when | Status |
|---|---|---|---|---|
| 3.10 | **Steering sweep**: full left, centre, full right, slowly | the wheel angle at each command (protractor or phone app on the wheel). `pixi run actuator-test steer-sweep --stands`: it asks for each angle | a table: command → real angle, each way | 🔧 |
| 3.11 | **Steering speed**: centre to full lock | seconds, from a video (or `actuator-test steer-rate --stands`, once a steering sensor reports) | written in `vehicle.yaml` | 🔧 |
| 3.12 | **Centre**: command straight | the wheels' angle; `actuator-test steer-centre --stands` | under 1°, or the offset written down | 🔧 |
| 3.13 | Wheel speed on stands | `/vehicle/status` speed vs a phone tachometer app | within 10% | ⬜ |

## Stage 4: the car in an empty lot

**Before:** stage 3 passed; the timeout fix (3.9) in; a safety driver; walking pace first.
The test script (`pixi run actuator-test <test>`, [docs](docs/actuator-tests.md)) logs the IMU (g),
the wheel speed, the pose and the GPS for every test.

### 4a. Speed up, coast, brake

| # | Test | How | Measure | Status |
|---|---|---|---|---|
| 4.1 | **Speed up** | from still, a fixed throttle (25%, 50%, full), 10 m. `actuator-test speed-up`: a speed command, so the speed loop picks the throttle | acceleration in **g** (IMU), and the time to 1, 2, 3 m/s | 🔧 |
| 4.2 | **Coast** | at 2 m/s, let go: no throttle, no brake. `actuator-test coast` (with the spine; not the ESP32) | how fast it slows: rolling resistance and drag | 🔧 |
| 4.3 | **Brake** | at 1, 2, 3 m/s, a fixed brake (50%, full). `actuator-test brake`: a normal stop, as no brake command exists | stopping distance and deceleration in **g** | 🔧 |
| 4.4 | **Throttle map** | repeat 4.1 at several throttles; `actuator-test throttle-map` | a table: throttle % → acceleration; and the deadband (the throttle where it starts to move) | 🔧 |

### 4b. Steering on the ground

| # | Test | How | Measure | Status |
|---|---|---|---|---|
| 4.5 | **Circles** | a fixed steering command at 1 m/s, a full circle each, both ways, several angles; `actuator-test circles` | the circle's size (GPS, or a tape), and yaw rate ÷ speed (IMU): the **real wheel angle** for each command | 🔧 |
| 4.6 | **Tightest turn** | full lock, both ways (the last pair of `actuator-test circles`) | the turning circle: checks `max_steering_angle` | 🔧 |
| 4.7 | **Straight line** | steering straight, 10 m at 0.5 m/s; `actuator-test straight` | sideways drift: under 0.5 m over 10 m | 🔧 |

### 4c. The car's weight (audit M7)

| # | Test | How | Gives | Status |
|---|---|---|---|---|
| 4.8 | **Scales** | 4 bathroom scales, one under each wheel, add them up | the mass, ±2%: the best way | ⬜ Friday |
| 4.9 | **Speed up twice** | test 4.1 at full throttle, alone, then with a person of known weight (say 80 kg) | mass = 80 × a2 ÷ (a1 − a2), ±10-15%; and the **motor's force** | ⬜ |
| 4.10 | **Brake twice** | test 4.3 at full brake, alone, then with the same person | the mass again; and the **braking force** | ⬜ |

For 4.9 and 4.10: the same battery charge, the same spot and direction, three runs each,
and the coast-down (4.2) subtracted, so drag doesn't count as motor or brake.

### 4d. Sensors on the ground

| # | Test | Passes when | Status |
|---|---|---|---|
| 4.11 | GPS | `/sensors/gps/fix` at 5-10 Hz, a 3D (or RTK) fix on the HUD | ⬜ |
| 4.12 | IMU direction | turning left shows +z rotation; braking shows −x acceleration | ⬜ |
| 4.13 | Local EKF | drive 10 m straight: the EKF says 10 m (±0.3 m) | ⬜ |
| 4.14 | Global EKF + GPS | drive a loop: the EKF's track stays within 2 m of the GPS track | ⬜ |
| 4.15 | Cameras: the freeze | 1 hour with no freeze, power and heat logged (`FRIDAY-TODO.md` part 5) | ⬜ |
| 4.16 | Radar | `/perception/radar/clusters` shows a person walking in front | ⬜ |
| 4.17 | Lidar (once it has a driver) | `car.launch.py lidar:=true`: an obstacle shows in RViz's local costmap (`lidar_layer`), and a person in front stops Nav2 | ⬜ no driver yet; ✅ in Gazebo (1.11) |
| 4.18 | **Sensor failures on the car** | pull the GPS's, the IMU's, the wheel encoder's cable while Nav2 drives at walking pace: the HUD's red banner names it, and the car stops | ⬜ |

## Stage 5: the whole drive

| # | Test | How | Passes when | Status |
|---|---|---|---|---|
| 5.1 | **Scripted drive** | 10 m at 0.5 m/s (`READ-ME-A-TO-B.md`, test 5) | stops 10 m on (±0.5 m), straight | 🔧 in Gazebo, `sim-check`'s 6.5 m plan passes; not yet on the car |
| 5.2 | **Smooth stop at a GPS point** | `pixi run goto --lat .. --lon ..`: speed up, hold, slow down at **half the measured brake g** (`vehicle.yaml` `max_brake`, from 4.3), stop at B ([A to B](READ-ME-A-TO-B.md)) | stops within 1 m of B (2 m without RTK) | 🔧 in Gazebo 15 Oct (`sim-check --goto`): 10-60 m, any angle, 1 and 3 m/s, every stop within 0.4 m of B, braking 1.4-1.6 m/s² for a plan of 1.5. 🔧 the car: needs 4.3 |
| 5.3 | Nav2 to a GPS point | the GPS goal, empty lot | reaches B, stops | 🔧 in Gazebo, goals of 8 m and 9.5 m; not yet on the car |
| 5.4 | **Ghost obstacles** | the real car with a **simulated** person in Nav2's costmap | slows and stops for it, with nothing real to hit | ⬜ |
| 5.5 | Plain-English driving on the car | `talk --car`: "drive 10 m forward" | the same as 5.1, after you type yes | ⬜ last |

## Friday's checks (not driving)

| # | Check | Run | Status |
|---|---|---|---|
| F.1 | Every machine on the network, with its ROS domain | `pixi run net-map` | ✅ at home |
| F.2 | The Mac can join ROS | `pixi run doctor` | ✅ at home |
| F.3 | Every machine surveyed: what runs, what's plugged in, what exists only there | `pixi run survey ~/aav-audit/hosts.txt` | ✅ Linux CI; 🔧 the car |
| F.4 | Multicast between the car's machines, wired and WiFi | `ros2 multicast send` / `receive` | 🔧 |
| F.5 | Clocks within a second | `date` on each | 🔧 |
| F.6 | The camera freeze: the 10-minute watch | `FRIDAY-TODO.md` part 5 | 🔧 |

## What the tests give back

```text
 4.1 speed up  ─┐
 4.3 brake     ─┼─► vehicle.yaml: acceleration, braking g, steering map, mass
 4.5 circles   ─┤        │
 4.8 scales    ─┘        ├─► Gazebo behaves like the real car (tests 1.x mean more)
                         └─► the smooth stop (5.2): it knows how hard it can brake
```

## Still to build for these tests

| What | For | Size |
|---|---|---|
| The SIMULATED banner and REAL / SIM tags | 1.9 | small |
| Ghost obstacles on the real car | 5.4 | 1 day |
| The ESP32 timeout | 3.9, and everything after | TEAM-TODO B2 |
| A driver for the roof lidar (probably a Velodyne) | 4.17 | small, once the model is known |
