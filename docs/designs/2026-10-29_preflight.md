# The preflight: one run on stands, before the ground

* **Author:** Ben (the ask), written up 29 Oct 2026
* **Status:** Tentative: built on `actuator-test`; untested on the car

Ben, 29 Oct: "Then we need maybe a test that speeds up, maintains and slows down and tests
all the sensors before we put it on the ground."

## The idea in one line

`pixi run preflight`: **one scripted run** with the wheels off the ground (speed up, hold,
slow down, brake; steer left, right, centre) while **every sensor is checked at the same
time**, then one PASS / FAIL line per check, as `car-day-check` prints.

## The script

The same twist_mux slot as `actuator-test` (`/drivers/tests/cmd_vel`, priority 60): the
joystick and the keyboard always win, `/safety/estop` locks it out.

| # | Step | Command | Ends when |
|---|---|---|---|
| 1 | still | 0 | standing still 1 s |
| 2 | speed up | the cap (0.3 m/s) | 95% of it for 1 s (or 10 s) |
| 3 | hold | the cap | 5 s |
| 4 | slow down | half the cap | 3 s |
| 5 | brake | 0 | still for 1 s (or 10 s) |
| 6 | steer left | creep 0.2 m/s, full lock left | 3 s |
| 7 | steer right | creep, full lock right | 3 s |
| 8 | centre | creep, straight | 3 s |
| 9 | stop | 0 | still 1 s |

Steering creeps because ego holds the wheels below 0.05 m/s (as `steer-sweep` does).
About 40 s in all.

## The checks

| Check | Topic | PASS when |
|---|---|---|
| wheel speed | `/vehicle/odom` | ≥ 10 Hz; finite |
| each wheel | `/vehicle/wheels` | ≥ 10 Hz; the measured wheels finite |
| steering | `/vehicle/steering` | ≥ 5 Hz; within 1.2 × full lock |
| raw IMU | `/sensors/imu/data_raw` | ≥ 20 Hz; still: \|a\| = 9.8 ± 1.5 m/s², \|gyro\| < 0.1 rad/s; not frozen |
| filtered IMU | `/sensors/imu/data` | ≥ 20 Hz |
| GPS | `/sensors/gps/fix` | ≥ 0.5 Hz; a fix; lat, lon finite |
| lidar | `/sensors/lidar/points` | ≥ 5 Hz; some points |
| radar | `/sensors/radar/points` | ≥ 5 Hz (an empty cloud is fine) |
| front camera | `/sensors/camera/front_left/image_raw` | ≥ 5 Hz; width and height > 0 |
| battery | `/vehicle/battery` | ≥ 0.2 Hz; a voltage > 0 |
| speeds up | the wheels | reaches 80% of the cap |
| holds | the wheels | mean within 25% of the cap in the hold |
| slows down | the wheels | the slow step's mean below the hold's |
| brakes | the wheels | still within 5 s |
| steers | `/vehicle/steering` | left > 0, right < 0, centre near 0; **no sensor:** the person says y/n after the run |
| **stands** | wheels vs IMU and GPS | see below |

A sensor that is meant to be off (session 9 runs `gps:=false lidar:=false`) is named with
`--skip gps lidar`: SKIP, not FAIL. Nothing is skipped by itself.

## Stands: disagreeing on purpose

From [learn-speed.md §9](../learn-speed.md#9-on-stands-disagreeing-on-purpose): the
wheels spin, the car doesn't move.

| Where | Expect | PASS when |
|---|---|---|
| the car, on stands | IMU and GPS say **still** | the IMU's speed change in steps 2-5 (its forward acceleration, less the still bias, added up) < 0.3 × the wheels'; the GPS moved < 2.5 m while the wheels turned ≥ 2 m |
| Gazebo, bench | the car is **on the ground**: the opposite | the IMU's speed change ≥ 0.5 × the wheels'; the GPS moved ≥ 0.5 × the wheels' distance |

In Gazebo and on the bench each line says "(sim: on the ground, so the opposite check)":
the same maths runs both ways, so the stand-ins test it.

After a run on stands the watchdog has latched **DISAGREE** (wheels against the GPS):
the preflight says so, and `pixi run watchdog-clear` clears it.

## Safety

| What | How |
|---|---|
| Who must be there | the safety driver (joystick, its deadman outranks the test), the e-stop person on the Kar-Tech, the laptop person |
| The word to type | **`preflight`**, after the stands checklist is read out loud. No keyboard: refused |
| Caps | 0.3 m/s (`STANDS_CAP`); `--max-speed` can lower it only. On the car it is always a stands run: there is no ground mode |
| What stops it | Ctrl-C, `/safety/estop`, the joystick or keyboard taking over, twist_mux silent 2 s, `/vehicle/odom` stale 0.5 s, the speed above 0.46 m/s, the time or distance envelope: zero commands until still |
| No wheel speed | refused before anything moves: the speed cap can't be checked (the spine's test mode's rule: no throttle without a wheel speed) |
| ego must answer | on the car, refused without ego's limits |
| Where it runs | `--sim`: Gazebo, `tools/ros.sh --local`; `--bench`: bench mode, `--local`; neither: the car (not local), and `/system/source` must say REAL |

The spine's hardware test mode (Arsh, #15) is not used yet: no frame carries a test
request to the spine. The preflight drives the normal way, through twist_mux and ego.

## The code

| Part | Where |
|---|---|
| the steps, the checks, the verdict (no ROS) | `ros/drivers/aav_actuator_tests/aav_actuator_tests/preflight.py`, tests in `test/test_preflight.py` |
| the node: `actuator_test`'s `Run`, plus a counter per sensor | `aav_actuator_tests/preflight_node.py`, executable `preflight` |
| the task | `pixi run preflight` → `tools/preflight.sh` |
| the runbook | car-day session 9 (before 3.10); `docs/actuator-tests.md` |

Each run saves `~/aav-tests/<time>-preflight/`: `log.csv`, `summary.txt` (the lines),
`meta.yaml`.
