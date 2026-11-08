# How the car stops

One stopping law for every planned stop, a behaviour planner that uses it to slow Nav2,
and a check of where the car really stops. Ben, 7 Nov: "we can use that to say if we have
turned enough or slowing down enough". The designs:
[how the car stops](designs/2026-11-05_how-the-car-stops.md),
[behaviour and speed](designs/2026-11-05_behaviour-and-speed.md).

> **Every number is a GUESS** until car tests 4.1-4.5 ([actuator tests](actuator-tests.md)).
> The locks don't use any of this: they keep their own laws.

## 1. The stopping law

```text
   S(v)  =  v·τ  +  v²/(2a)           τ = ρ + a/(2j)
            └┬─┘    └──┬──┘
       delay + easing  braking

   the cap:     v_cap(d) = a·( √(τ² + 2d/a) − τ )     the speed that stops in d metres
```

`aav_description` `stop_law.py` (no ROS): `StopCurve(a, j, rho)` with `distance(v)`,
`cap(d)`, `demand(v)`, `h(room, v, margin)`.

### Its numbers come from the car model

| Symbol | Means | From | Today |
|---|---|---|---|
| `a` | planned braking | half the softer of ego's `max_deceleration` and `max_brake` | 1.0 m/s² |
| `j` | jerk | ego's `max_jerk` | 2.0 m/s³ |
| `ρ` | every delay | input age 0.15 s + brake dead time + `brake_lag` + **the speed loop's lag** | 1.22 s |
| `τ` | delay + easing | ρ + a/(2j) | 1.47 s |

**The speed loop's lag** (new, not in the design): the spine's default PI coasts until the
car is 0.2 m/s too fast, then brakes 0.5 per m/s past that. To brake at 1 m/s² it must be
0.87 m/s too fast: 0.87 s behind. Without it, the law overran the point by 0.3-0.4 m on
the pretend car. `loop=None` gives the design's ρ 0.35.

| Distance left | 0.5 m | 1 m | 2 m | 5 m | 10 m |
|---|---|---|---|---|---|
| `v_cap` | 0.31 m/s | 0.57 m/s | 1.01 m/s | 2.02 m/s | 3.24 m/s |

### Who uses it

| User | Before | Now | Check |
|---|---|---|---|
| Trial trackers (`aav_track` `speed.py`) | `√(2·1.5·d)` | **the law** | never a higher speed, at every distance (`test_speed.py`) |
| Point driver (`aav_drive_to_point`) | `√(2a(d − 0.8v))` | the same; **`stop_law:=hybrid`** picks the law (a trial) | stops at B on the pretend car (`test_drive.py`) |
| ego's start-up log | `0.4v + v²/2a` | both lines: the hardest stop, and the planned one | the plan is never shorter (`test_dynamics.py`) |
| Behaviour planner | none | the law | below |
| The geofence's lock | RSS | **unchanged** (Simplex) | its worst case is never shorter than where the car model stops (`test_geofence.py`). Above about 0.7 m/s the law plans **more** room than the lock (1.97 against 1.40 m at 1 m/s on the spine), so the car slows before the lock closes |
| The stop sign's lock | 4.7 m | **unchanged** | |

### Point driver, pretend car (ego and Gazebo's actuator model)

| From | Law | Stop error | Peak braking | Time |
|---|---|---|---|---|
| 1 m/s, 10 m | approach | +0.06 m | 0.77 m/s² | 15.4 s |
| 1 m/s, 10 m | hybrid | +0.09 m | 0.77 m/s² | 15.3 s |
| 3 m/s, 30 m | approach | +0.04 m | 1.32 m/s² | 19.7 s |
| 3 m/s, 30 m | hybrid | +0.09 m | **0.78 m/s²** | 19.9 s |

Gentler at speed, 5 cm further past B. Not yet run in Gazebo.

## 2. The behaviour planner

`aav_behaviour` (a trial, **off by default**): `pixi run sim world:=road behaviour:=true`.
It knows why the car should slow, and sends Nav2 a speed cap. **It can't stop the car**:
a lock or Nav2's goal check makes every final stop.

```text
 DRIVE ─► APPROACH ─► STOPPED ─► WAIT ─► GO ─► DRIVE
  (no cap)  (cap falls)  (lock on,  (lock on)  (cap rises)
                         still)        │
                                       └─► ASK (a person is told)
```

| Stop for | `left` | The final stop |
|---|---|---|
| A stop sign | camera range to the sign − 4.7 m | the `stop_sign` lock |
| An obstacle in the lane | lidar: nearest point ahead − bumper − stop zone | collision_monitor, then the `stop_zone` lock |
| The fence | along the plan to where the geofence would say NEAR | the geofence's lock |
| The goal | along the plan to its end | Nav2's goal check |

### The cap

| Rule | Why |
|---|---|
| `v_cap(left)` of the lowest stop | the stopping law, above |
| 0.0, or between 0.3 m/s and Nav2's top speed | Nav2 reads 0.0 as **no limit** |
| Falls no faster than 2 m/s² | MPPI cuts its turn rate at once, its speed later |
| The sign's cap never rises in APPROACH | a new picture can't speed the car up |
| Rises at 0.5 m/s² in GO | |
| Odometry stale: the floor | |

### Topics

| Topic | Type | |
|---|---|---|
| `/drivers/nav/speed_limit` | `nav2_msgs/SpeedLimit`, 20 Hz | controller_server reads it with `behaviour:=true` |
| `/drivers/nav/behaviour/state` | `diagnostic_msgs/DiagnosticStatus`, 5 Hz | for the screens: state, reason, cap, left |
| `/perception/stop_sign/distance` | `geometry_msgs/PointStamped` | new, from the watcher: where the sign is |

### Not built yet

| Part | Why it waits |
|---|---|
| The `patient` progress checker | a stock tree edit; holds over 10 s still look stuck to Nav2 |
| ASK's reply (`/hud/ask/answer`) | the HUD has no reply path |
| The trial trackers reading the cap | they ignore `/drivers/nav/speed_limit` |
| The car | the stage gates in the design: `pi` mode first |

## 3. Where the car really stops

`pixi run sim-check --stop-point` (the empty world, the spine in the loop, about 4 minutes).

| Step | What happens |
|---|---|
| 1 | a scripted drive at 0.5, 0.75 and 1 m/s (the spine's top speed: 1 m/s) |
| 2 | steady for 1.5 s, then the e-stop: the spine brakes fully |
| 3 | the prediction: the first `/ego/stop_point` after the press (ego, the shared car model, full brake) |
| 4 | moved to the map by `/tf` at its stamp |
| 5 | scored against Gazebo's truth and the global EKF |

Pass: within 0.25 m, or 10 % of the distance if more. A drive that never reached half
its speed fails. The maths is `tools/stop_points.py`: it can score a bag from the car
later, with a tape measure for the truth.

### Numbers (8 Nov)

| From | Predicted | Truth | Localization | Stop point after the press |
|---|---|---|---|---|
| 0.54 m/s | 0.11 m | 0.12 m | 0.37 m | 3 ms |
| 0.77 m/s | 0.19 m | 0.18 m | 0.17 m | 43 ms |
| 0.98 m/s | 0.30 m | 0.24 m | 0.33 m | 83 ms |

The stopping law plans far more (0.95, 1.42 and 1.93 m): it plans a gentle stop at
1 m/s², not a full brake.
