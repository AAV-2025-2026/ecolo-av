# One car model

How the car answers a command: one model, in Python and Rust, for ego, the simulators
and the drivers. Ben, 7 Nov: "we really want the ego to have a mathematical model for
steering, braking and acceleration ... have the algorithms know about lag".

> **Every number is a GUESS** until car tests 3.10-3.12 and 4.1-4.5
> ([actuator tests](actuator-tests.md)). The dead times are 0 until measured.

## Where it lives

| What | Where |
|---|---|
| Python | `ros/bringup/aav_description/aav_description/car_model.py` |
| Rust twin | `ros/bringup/aav_description/car-model/` (crate `car-model`) |
| Shared test vectors | `car-model/vectors.json`, written by `car-model/gen_vectors.py` |
| Numbers | `vehicle.yaml`: `actuators:`, `wheelbase`, `max_steering_angle` |
| Old import path | `aav_gazebo.actuator_model` still works: the same objects |

Why `aav_description`: it already holds `vehicle.yaml` and `vehicle.py`, and ego and
Gazebo both depend on it. The model is part of "what the car is".

## The picture

```
 command ──▶ dead time ──▶ lag ──▶ speed ──────────────┐
 (pedals or                                            ├──▶ bicycle ──▶ x, y, yaw
  a set speed)                                         │
 steering ─▶ dead time ─▶ deadband ─▶ motor rate ─▶ linkage lag ─▶ + offset ─┘
```

A set speed goes through the spine's speed loop first (Python: the port; Rust:
`spine-core`'s own).

## One step of dt

| # | Part | Maths |
|---|---|---|
| 1 | Dead time | each input waits `floor(dead_time / dt + 0.5)` steps |
| 2 | Throttle, brake | `level' = (u - level) / lag`, stepped exactly: `level += (u - level)(1 - e^(-dt/lag))` |
| 3 | Speed | `v += max_accel · throttle · dt` (0 below the deadband), then brake and drag take `(max_brake · brake + drag · abs(v)) · dt` off, never past 0 |
| 4 | Steering | setpoint moves only past `steer_deadband`; motor at most `steer_rate · dt`; linkage lags `steer_lag`; plus `steer_offset`; within `±max_steering` |
| 5 | Bicycle | `yaw += v tan(steer) / wheelbase · dt`; `x += v cos(yaw_mid) dt`, `y += v sin(yaw_mid) dt` |

`v` and `steer` in step 5 are the step's new ones; `yaw_mid` is halfway between the old
and new yaw.

## The API

| Python (`aav_description.car_model`) | Rust (`car_model`) |
|---|---|
| `ActuatorConfig.from_vehicle_yaml(path)` | `ActuatorConfig::from_vehicle_yaml(path)?` |
| `Command(steer, throttle, brake, reverse)` | `Command::pedals(throttle, brake, steer)` |
| `Command(steer, speed=v)` | `Command::speed(v, steer)` |
| `step(cfg, state, command, dt, loop)` | `cfg.step(&state, command, dt, Some(&mut loop))?` |
| `predict(cfg, state, commands, dt, horizon, loop)` | `cfg.predict(&state, &commands, dt, horizon, Some(&loop))?` |
| `CarState` | `CarState` |

`predict` gives a state every `dt` for `horizon` s, the first one `dt` ahead. The last
command is held. The speed loop is copied, never advanced.

## Checks

| Test | Checks |
|---|---|
| `aav_description/test/test_car_model.py` | dead times, the circle, braking, predict; the vectors are up to date |
| `car-model/tests/vectors.rs` | the Rust gives the Python's states (1e-9; 1e-3 with a speed loop, which is f32 in Rust) |
| `aav_gazebo/test/test_actuator_model.py` | Gazebo's car is unchanged |

After changing either side:

```bash
python3 ros/bringup/aav_description/car-model/gen_vectors.py
tools/test.sh
```
