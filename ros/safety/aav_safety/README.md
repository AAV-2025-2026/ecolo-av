# aav_safety

## Overview

The sensor watchdog. When a sensor Nav2, the point driver or the AI slot needs dies, lies or freezes,
it stops them, and says why loudly: in the log, on `/diagnostics` and on the HUD. People and
test scripts can still drive.

And the stop hold (`stop_hold`). Nav2's collision_monitor decides afresh on every
command, so an obstacle at its stop zone's edge flickers it between stop and go, and the
car creeps on. The hold keeps a stop until the monitor has said "go" for `clear_time` s
without a break.

```
monitor:  STOP  go  STOP  go  go  go  go ...  (1 s of go)
lock:    true  true true true true true ...   false
```

It works through a twist_mux lock (priority 30, in `aav_command_mux`). Each input's checks:

| State | Means |
|---|---|
| `NEVER` | nothing yet |
| `STALE` | nothing good for `max_age` s. A GPS fix with no fix (or NaN) isn't good: after `max_age` it reads STALE, "no fix ..." |
| `NAN` | NaN or inf in the newest message |
| `FROZEN` | the same values for `frozen_after` s (a camera only while the car moves) |
| `JUMP` | two GPS fixes too far apart for the car. Latched |
| `DISAGREE` | the wheels' speed or turn against the IMU and the GPS (`wheel_check.py`). Latched |
| `LOST` | a `latch` input (the HUD) dropped out after its start-up. Latched |

A person clears latched faults: `pixi run watchdog-clear`. More in
`docs/simulation.md` ("Sensor failures on purpose").

## Interface

### Node `sensor_watchdog`

| In / out | Topic | Type |
|---|---|---|
| in | each input's `topic` (below) | by `kind` |
| in | `/vehicle/odom` (always), `/sensors/imu/data` (for the cross check) | |
| out | `/safety/sensor_watchdog/lock`, at `rate_hz` | `std_msgs/Bool`: true while a `stop` input isn't OK; a heartbeat |
| out | `/safety/sensor_watchdog/state`, at `rate_hz` | `std_msgs/String`: `OK`, or `STOP`/`WARN` and why |
| out | `/diagnostics`, 1 Hz | `diagnostic_msgs/DiagnosticArray`: one status per input |
| serves | `/safety/sensor_watchdog/clear` | `std_srvs/Trigger`: forget latched faults |

### Node `stop_hold`

| In / out | Topic | Type |
|---|---|---|
| in | `/safety/collision_monitor/state` | `nav2_msgs/CollisionMonitorState`: on each change |
| out | `/safety/stop_hold/lock`, at `rate_hz` | `std_msgs/Bool`: twist_mux's `stop_zone` lock (priority 21) |

Parameters (`config/stop_hold.yaml`): `clear_time` (s, 1.0), `rate_hz` (10).
`aav_navigation`'s `navigation.launch.py` starts it wherever it starts collision_monitor.

### Inputs (`config/sensor_watchdog.yaml`)

| Name | Topic | Kind | max_age | Stops? |
|---|---|---|---|---|
| `odom` | `/vehicle/odom` | odom, with cross check | 0.5 s | yes |
| `imu` | `/sensors/imu/data` | imu | 0.5 s | yes |
| `gps` | `/sensors/gps/fix` | gps (jump: 15 m/s + 5 m) | 2.0 s | yes |
| `local`, `global` | `/localization/odom/local`, `/global` | odom | 0.5 s | yes |
| `camera` | `/sensors/camera/front_left/image_raw` | image | 1.0 s | yes |
| `front_left_stream`, `front_right_stream` | `/perception/detections` (by `frame_id`) | detections | 1.0 s | yes |
| `hud` | `/hud/heartbeat` | heartbeat, latched | 1.0 s | yes |
| `radar` | `/sensors/radar/points` | cloud | 1.0 s | no (collision_monitor stops Nav2 itself) |

Per input parameters: `topic`, `kind`, `max_age` (s), `stop`, `frozen_after` (s),
`max_jump_speed` (m/s), `jump_margin` (m), `frame_id`, `latch`, `latch_grace` (s);
for odom, `cross_check`, `cross_window` (s), `cross_speed_tolerance` (m/s),
`cross_yaw_tolerance` (rad/s), `cross_persist` (s), `cross_gps_window` (s),
`cross_gps_tolerance` (m/s). Global: `inputs`, `rate_hz` (10).

### Launch and modules

`launch/watchdog.launch.py inputs:=odom,imu,gps,local,global [use_sim_time:=false]`:
each profile passes the inputs it has (sim, bench, car).

| Module | No ROS? | Holds |
|---|---|---|
| `watchdog.py` | yes | `Rule`, `Watch`, `Watchdog`; the states above; `KINDS` |
| `wheel_check.py` | yes | `CrossCheck` (settings), `WheelCheck`: wheels vs IMU vs GPS |
| `sensor_watchdog.py` | no | the node |
| `hold.py` | yes | `StopHold`: locked from a stop until `clear_time` s of no stop |
| `stop_hold.py` | no | the node |

## Invariants

- `watchdog.py`, `wheel_check.py` and `hold.py` have no ROS imports, and their own tests.
- The stop hold's lock holds Nav2 (20) and the AI slot (10) only. Timeout 0: its silence
  locks nothing, and a `stop_hold` that dies while true keeps the stop.
- The stop hold times on the steady clock, so a jump in sim time can't end it early.
- The lock holds the point driver (25), Nav2 (20) and the AI slot (10), never a person or a test.
- Fail-safe: twist_mux treats 1 s without a lock message as locked, so a dead or hung
  watchdog stops them too.
- Ages are about 5 messages at the sensor's rate, never under ego's 0.5 s command timeout.
- `inputs` is set by the launch file, never in the YAML, or the file would win.
- After a stall of the watchdog itself (seen on a steady clock), it latches nothing for 3 s.
- One HUD dropout within `latch_grace` (5 s) of its first beat is forgiven.
- Each change of state is logged once.

## Side Effects

- Publishes the lock, the state and `/diagnostics`; serves `clear`.
- Logs an error when an input stops the car, a warning when it only warns.

## Verification

```sh
cd ros/safety/aav_safety && python3 -m pytest -q        # the logic, no ROS
pixi run build && colcon test --packages-select aav_safety && colcon test-result --verbose
```

`tools/test.sh` runs the first; `pixi run test` runs everything. In Gazebo:
`pixi run sim-check --faults`, or break a sensor by hand with `pixi run sim-fault gps stop`.
