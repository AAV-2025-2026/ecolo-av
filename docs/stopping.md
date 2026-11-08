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
| The geofence's lock | RSS | **unchanged** (Simplex) | the lock always counts on more room than the law, every backend, every speed (`test_geofence.py`) |
| The stop sign's lock | 4.7 m | **unchanged** | |

### Point driver, pretend car (ego and Gazebo's actuator model)

| From | Law | Stop error | Peak braking | Time |
|---|---|---|---|---|
| 1 m/s, 10 m | approach | +0.06 m | 0.77 m/s² | 15.4 s |
| 1 m/s, 10 m | hybrid | +0.09 m | 0.77 m/s² | 15.3 s |
| 3 m/s, 30 m | approach | +0.04 m | 1.32 m/s² | 19.7 s |
| 3 m/s, 30 m | hybrid | +0.09 m | **0.78 m/s²** | 19.9 s |

Gentler at speed, 5 cm further past B. Not yet run in Gazebo.
