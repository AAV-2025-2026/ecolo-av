# Actuator tests: measure how the car moves

One script runs the stage-3 and stage-4 tests of `READ-ME-TESTS.md`: it drives the car,
logs what happened, and prints the numbers for `vehicle.yaml`. Built and proven in Gazebo
(15 Oct); the same script runs on the car.

!!! note "The short version"
    - `pixi run actuator-test --list` shows the tests. Add `--sim` for Gazebo.
    - **On the car:** stage 3 on stands (`--stands`), stage 4 in an empty lot. It asks you
      to type the test's name first, and never goes above 1 m/s (0.3 on stands).
    - **To stop:** Ctrl-C, the e-stop, or the joystick's deadman. Any of them, any time.
    - It prints the `vehicle.yaml` lines to paste. It never writes the file itself.

## How it fits

```text
 actuator_test ──/drivers/tests/cmd_vel──► twist_mux ──► ego ──► backend ──► the car
   (priority 60)                               ▲                    (or Gazebo)
 joystick 100, keyboard 90 ────────────────────┘ always win
        │
        └── reads back: /vehicle/odom (speed), /vehicle/steering, /throttle, /brake,
            the IMU, /localization/odom/local, GPS, /safety/estop, /system/source
```

It's a driver like any other ([Build a driver](howto-driver.md)), in twist_mux's `tests`
slot: below both people, above Nav2 and every other program.

## The tests

| Test | # | Where | What it does | Gives (`vehicle.yaml`) |
|---|---|---|---|---|
| `steer-sweep` | 3.10 | stands | steps full left → centre → full right and back, 2.5 s each | angle per command; `max_steering_angle`, `steer_offset` |
| `steer-rate` | 3.11 | stands | centre → full lock → centre, each way | `steer_rate`, `steer_lag` |
| `steer-centre` | 3.12 | stands | straight, then tiny steps (0.002 rad) each way | `steer_offset`, `steer_deadband` |
| `speed-up` | 4.1 | lot | from still to the speed cap | time to 0.5, 1, 2, 3 m/s; g (wheels and IMU); `max_accel`, `throttle_lag` |
| `coast` | 4.2 | lot | to 2 m/s, then neither throttle nor brake | `drag` |
| `brake` | 4.3 | lot | to 1, 2, 3 m/s (up to the cap), then stop | stopping distance, g; `max_brake`, `brake_lag` |
| `throttle-map` | 4.4 | lot | speed-ups to ¼, ½, ¾ and all of the cap | throttle % → acceleration; `throttle_deadband` |
| `circles` | 4.5, 4.6 | lot | one full circle per angle, both ways, at 1 m/s | real wheel angle per command; tightest circle |
| `straight` | 4.7 | lot | 10 m at 0.5 m/s, steering straight | sideways drift; `steer_offset` |

The steering tests creep at 0.2 m/s: ego only turns the wheels while the car moves. On
stands the wheels spin slowly; in Gazebo the car crawls in arcs.

## In Gazebo

```bash
pixi run sim world:=empty gui:=false rviz:=false nav:=false sim_speed:=3   # terminal 1
pixi run actuator-test speed-up --sim                                      # terminal 2
```

- `sim_speed:=3` lets ego go to 3 m/s, so `speed-up` and `brake` reach 2 and 3 m/s.
- `--sim` keeps ROS on this computer and uses Gazebo's clock. The script refuses to run
  without it when Gazebo announces SIM, and with it when anything announces REAL.
- `nav:=false`: nothing else drives. The empty world has room for the circles.

## On the car

The task is **not** `--local`, so it reaches the car's computers. Run it from the laptop
on the car's network, with the car's stack running (`pixi run car ...`).

### Stage 3: on stands

```bash
pixi run actuator-test steer-sweep --stands
pixi run actuator-test steer-rate --stands
pixi run actuator-test steer-centre --stands
```

1. The script prints the checklist from `READ-ME-TESTS.md` stage 3. Check it out loud.
2. Type the test's name to start. Anything else cancels; nothing moves.
3. **No steering sensor yet?** (The 2025-26 ESP32 reports none: TEAM-TODO B6.) At each
   measuring point the car stops and asks for the angle in degrees: read it with a
   protractor or a phone app on the wheel. `steer-rate` then needs a video instead.

### Stage 4: in an empty lot

```bash
pixi run actuator-test speed-up
pixi run actuator-test coast
pixi run actuator-test brake --speeds 0.5 1.0
pixi run actuator-test circles --angles 0.25 0.5
pixi run actuator-test straight
```

Run `coast` first: the throttle fit uses `vehicle.yaml`'s `drag`. Then paste the drag in,
then run the rest. Start at walking pace: `--max-speed 0.5`.

### The safety layers

| Layer | What it does |
|---|---|
| **Typing the test's name** | on the real car (or when nobody announces `/system/source`), nothing moves until you type it. No keyboard (a script, a pipe): refused |
| **Speed cap** | 1 m/s on the car, 0.3 m/s on stands; `--max-speed` can lower it, never raise it there |
| **Stage check** | on the car, stage-3 tests need `--stands`, stage-4 tests refuse it |
| **Envelope** | each test has a speed, distance and time limit (printed at the start): crossing one stops the car |
| **Ctrl-C, errors** | zero commands until the car stands still, then it exits. A second Ctrl-C can't cut that short |
| **`/safety/estop`** | stops the test at once (twist_mux's lock and the backend brake too) |
| **Someone takes over** | the joystick or keyboard outranks the test in twist_mux; the script sees it and stops |
| **Stale speed** | no `/vehicle/odom` for 0.5 s: stop |
| **Nothing through twist_mux** | 2 s with no `/control/cmd_vel`: stop (a lock, or a mux without the `tests` slot) |
| **A cut-short run** | still saves its log and table, but prints no `vehicle.yaml` lines |

!!! warning "ego's steering rate"
    `steer-rate` lifts ego's `max_steering_rate` (0.6 rad/s) to 3 rad/s while it runs, so it
    times the motor, not ego, and puts it back after. ego allows a live change to that one
    limit only. If the script is killed (not Ctrl-C), restart ego to be sure.

### What the car can measure today

The 2025-26 ESP32 drives the car until the spine replaces it (`legacy_uart_bridge`).

| Measurement | Today (ESP32) | With the spine |
|---|---|---|
| Speed | ✅ the wheel encoder, `/vehicle/odom` | ✅ |
| IMU g, yaw rate | ✅ once the IMU runs | ✅ |
| Pose (circles, straight) | ✅ the local EKF; GPS logged too | ✅ |
| Steering angle | ❌ no sensor: type it in on stands | ✅ `/vehicle/steering` |
| Throttle and brake levels | ❌ not reported: no `max_accel` or `max_brake` fit, only the g figures. A speed command **is** the throttle there: speed ÷ `full_throttle_speed` (`legacy_protocol.py`) | ✅ `/vehicle/throttle`, `/vehicle/brake` |
| Coasting | ❌ a low speed command still pushes, and 0 brakes | ✅ inside the speed loop's coast band |
| A fixed brake % (4.3 as written) | ❌ no brake command exists: the tests brake with a normal stop | ❌ the same |

## What it saves

Each run gets a folder, `~/aav-tests/<date>-<time>-<test>[-sim]/` (`--out` or
`$AAV_TESTS_DIR` moves it):

| File | Holds |
|---|---|
| `log.csv` | 50 rows a second: commands, speed, steering, throttle, brake, wheels, IMU, pose, GPS |
| `summary.txt` | the table and the `vehicle.yaml` lines, as printed |
| `meta.yaml` | the test, the source, the cap and envelope, ego's limits, `vehicle.yaml` then, the steps |
| `bag/` | with `--bag`: a rosbag of every topic it reads and sends |

`pixi run actuator-test --analyse <folder>` prints the report again from `log.csv`.

## Proven in Gazebo (15 Oct)

`world:=empty`, `sim_speed:=3`, `vehicle.yaml`'s guessed numbers in the actuator model.
The script should give them back:

| Number | `vehicle.yaml` | Measured | Test |
|---|---|---|---|
| `max_accel` | 1.5 m/s² | 1.496 | `speed-up`; 1.495 in `throttle-map` |
| `throttle_lag` | 0.1 s | 0.100 | `speed-up` |
| `throttle_deadband` | 0 | 0.113 ⚠️ | `throttle-map`: Gazebo's car starts rolling about 0.3 s after the model does |
| `drag` | 0.1 /s | 0.100 | `coast` |
| `max_brake` | 3.0 m/s² | 3.045 | `brake` |
| `brake_lag` | 0.2 s | 0.200 | `brake` |
| `steer_rate` | 0.8 rad/s | 0.817 | `steer-rate` |
| `steer_lag` | 0.1 s | 0.105 | `steer-rate` |
| `steer_offset` | 0 | 0.000 | `steer-centre`, `steer-sweep`, `straight` |
| `steer_deadband` | 0.005 rad | 0.005 | `steer-centre` |
| `max_steering_angle` | 0.5 rad | 0.495 | `steer-sweep` (the deadband leaves 0.005 short) |
| real angle, full-lock circle | 0.5 rad | 0.433 ⚠️ | `circles`: Gazebo turns wider than told (below) |
| real angle at 0.2 / 0.35 rad | 0.2 / 0.35 | 0.194 / 0.339 | `circles`: yaw rate, odometry circle and GPS circle agree within 1% |

Other figures from the same runs: 0 → 3 m/s in 6.2 s; IMU and wheel-speed g agree
(0.054 vs 0.056 g mean); stopping from 1.1 / 2.2 / 3.1 m/s took 1.05 / 2.57 / 4.46 m;
drift over 10 m was 0.06 m; the full-lock circle was 6.8 m across, not 5.75.

!!! warning "Found: Gazebo's car can't reach full lock"
    The steering sensor says 0.5 rad, but the car turns as if 0.433. Gazebo's Ackermann
    system applies `steering_limit` (`max_steering_angle`) to the **inner** wheel, so
    the virtual centre wheel stops near 0.45 rad; tyre slip takes the rest. Not fixed
    yet: the fix (an inner-wheel limit in `aav.gazebo.xacro`) changes every Gazebo drive,
    and needs its own `sim-check`. On the car, `circles` measures the real thing.

!!! note "Gazebo's IMU"
    Gazebo's own IMU never felt the car speed up or brake (0.00 m/s² while speeding up at
    0.6). `gazebo_adapter` now gives it the model's acceleration ([Simulation](simulation.md)).

### Checked in Gazebo and against a pretend real car (15 Oct)

| What was done | What happened |
|---|---|
| Ctrl-C during `speed-up`, at about 1.5 m/s | "STOPPING: Ctrl-C"; stood still, exited in 3.2 s |
| `/safety/estop` true during `speed-up` | "STOPPING: /safety/estop is true"; stood still |
| The keyboard slot sends zeros during `straight` | "someone else is driving"; stood still |
| Gazebo, without `--sim` | refused: add `--sim` |
| A pretend REAL announcer, no keyboard attached | checklist printed, then refused |
| ... a stage-3 test without `--stands` | refused |
| ... `--sim`; `--max-speed 1.5` | refused; refused |
| ... typed "yes" | "Cancelled: nothing moved" |
| ... typed "speed-up", but no car | refused: no `/vehicle/odom` |

## The code

| File | What |
|---|---|
| `src/drivers/aav_actuator_tests/aav_actuator_tests/actuator_test.py` | the ROS node and the command line |
| `procedures.py` | each test's steps |
| `safety.py` | the rules: REAL or SIM, caps, envelope, confirmation |
| `analysis.py`, `reports.py` | the maths and the report: no ROS, unit-tested |
| `test/fake_car.py` | ego's model + Gazebo's actuator model: the tests check each test gets the numbers back |
| `tools/actuator_test.sh` | the pixi task: `--local` only with `--sim` |
