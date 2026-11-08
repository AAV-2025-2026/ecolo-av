# car-model

## Overview

The car model in Rust: the twin of `aav_description/car_model.py`, with the same maths.
For Rust nodes and simulators (an MPPI driver, our own simulator) that need to know how
the car answers a command: its lags, dead times, steering motor and the bicycle.

```
Command (pedals or a set speed, steering target) ─▶ step ─▶ next CarState
CarState + commands + dt + horizon               ─▶ predict ─▶ [CarState] (the trace)
```

The page: `docs/vehicle-model.md`, "One car model". **Every number is a guess** until car
tests 3.10-3.12 and 4.1-4.5.

## Interface

| Item | What |
|---|---|
| `ActuatorConfig` (`Default`, `from_vehicle_yaml(path)`, `from_vehicle_yaml_str`) | `vehicle.yaml`'s `actuators:`, the dead times, `max_steering` and `wheelbase` |
| `ActuatorConfig::step(&state, command, dt, speed_loop)` | one step: `Result<CarState, ModelError>` |
| `ActuatorConfig::predict(&state, &commands, dt, horizon, speed_loop)` | the states every `dt` for `horizon` s; the last command held; the loop copied |
| `Command { drive, steer }`, `Command::pedals`, `Command::speed` | one step's command |
| `Drive::Pedals { throttle, brake, reverse }`, `Drive::Speed(m/s)` | pedals as they are, or a set speed for a `SpeedLoop` |
| `CarState` | `x, y, yaw, v, steer, throttle_level, brake_level`, the steering motor's insides, and the three delay lines |
| `ModelError`, `ConfigError` | why a step or a file failed |
| `SpeedLoop`, `SpeedLoopProfile`, `SpeedLoopConfig` | re-exported from `spine-core`: the spine's own speed loop |
| `delay_steps`, `delay`, `lag` | the pieces |

## Invariants

- The same maths as `car_model.py`: `vectors.json` (from `gen_vectors.py`) checks every
  case; pedal cases within 1e-9, set-speed cases within 1e-3 (spine-core's loop is f32).
- Dead times round `dead_time / dt + 0.5` down, in both languages.
- The brake and drag never reverse the car.
- No ROS: plain `std` Rust; its own workspace.

## Side Effects

None. `from_vehicle_yaml` reads a file.

## Verification

```sh
cd ros/bringup/aav_description/car-model && cargo test     # also in tools/test.sh
python3 ros/bringup/aav_description/car-model/gen_vectors.py   # after changing car_model.py
```
