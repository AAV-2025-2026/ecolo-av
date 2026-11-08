"""The shared car model: dead times, the bicycle, predict, and the vectors the Rust twin reads."""

import importlib.util
import json
import math
from pathlib import Path

from aav_description.car_model import (ActuatorConfig, Actuators, CarState, Command, delay,
                                       delay_steps, Demand, predict, speed_loop_profile,
                                       SpeedLoop, step)
import pytest

HERE = Path(__file__).resolve().parent
CRATE = HERE.parent / 'car-model'
VEHICLE_YAML = HERE.parent / 'config' / 'vehicle.yaml'
DT = 0.02


def drive(cfg, command, seconds, state=CarState(), dt=DT, loop=None):
    states = []
    for _ in range(round(seconds / dt)):
        state = step(cfg, state, command, dt, loop)
        states.append(state)
    return states


def test_from_vehicle_yaml_reads_the_wheelbase_and_the_steering_limit():
    cfg = ActuatorConfig.from_vehicle_yaml(VEHICLE_YAML)
    assert cfg.wheelbase == 1.561
    assert cfg.max_steering == 0.5
    assert cfg.throttle_dead_time == 0.0   # commented out in vehicle.yaml: not measured


def test_delay_line_gives_the_value_from_n_steps_ago():
    line, outs = (), []
    for value in (1.0, 2.0, 3.0, 4.0):
        out, line = delay(line, value, 2, rest=0.0)
        outs.append(out)
    assert outs == [0.0, 0.0, 1.0, 2.0]
    assert delay((), 5.0, 0, rest=0.0) == (5.0, ())
    # dt grew: a shorter line, the oldest values dropped.
    assert delay((1.0, 2.0, 3.0), 4.0, 1, rest=0.0) == (3.0, (4.0,))


def test_delay_steps_round_half_up_as_rust_does():
    assert delay_steps(0.05, 0.02) == 3      # 2.5: Python's round() would give 2
    assert delay_steps(0.0, 0.02) == 0
    assert delay_steps(0.1, 0.02) == 5


def test_a_throttle_dead_time_holds_the_car_for_that_long():
    cfg = ActuatorConfig(throttle_dead_time=0.1)
    states = drive(cfg, Command(throttle=1.0), 0.2)
    assert all(s.throttle_level == 0.0 for s in states[:5])
    assert states[5].throttle_level > 0.0


def test_a_steering_dead_time_holds_the_motor():
    cfg = ActuatorConfig(steer_dead_time=0.06)
    states = drive(cfg, Command(steer=0.3), 0.1)
    assert all(s.steer_motor == 0.0 for s in states[:3])
    assert states[3].steer_motor == pytest.approx(0.8 * DT)


def test_no_dead_time_is_the_gazebo_actuators_step_for_step():
    cfg = ActuatorConfig()
    car = Actuators(cfg)
    state = CarState()
    for i in range(200):
        d = Demand(throttle=0.5 if i < 100 else 0.0, brake=0.0 if i < 100 else 0.6,
                   reverse=False)
        s = car.drive(d, 0.3, DT)
        state = step(cfg, state, Command(steer=0.3, throttle=d.throttle, brake=d.brake), DT)
        assert (s.speed, s.steering, s.throttle, s.brake) == (
            state.v, state.steer, state.throttle_level, state.brake_level)


def test_the_bicycle_drives_a_circle_of_the_turning_radius():
    cfg = ActuatorConfig(steer_lag=0.0, steer_rate=100.0, drag=0.0, throttle_lag=0.0)
    start = CarState(v=1.0, steer=0.3, steer_motor=0.3, steer_setpoint=0.3, steer_linkage=0.3)
    radius = cfg.wheelbase / math.tan(0.3)
    # Just enough throttle to hold 1 m/s against no drag: none.
    states = drive(cfg, Command(steer=0.3), 2.0, start, dt=0.001)
    for s in states:
        assert math.hypot(s.x, s.y - radius) == pytest.approx(radius, rel=1e-4)
    assert states[-1].yaw == pytest.approx(2.0 / radius, rel=1e-6)


def test_braking_never_reverses_the_car():
    states = drive(ActuatorConfig(), Command(brake=1.0), 2.0, CarState(v=0.5))
    assert states[-1].v == 0.0
    assert min(s.v for s in states) == 0.0


def test_predict_holds_the_last_command_and_leaves_the_loop_alone():
    cfg = ActuatorConfig()
    loop = SpeedLoop(speed_loop_profile('default'))
    trace = predict(cfg, CarState(), Command(speed=1.0, steer=0.2), DT, 2.0, loop)
    assert len(trace) == 100
    assert trace[-1].v > 0.5 and trace[-1].y > 0.0        # forward, turning left
    assert loop.integral == 0.0                            # the caller's loop: untouched
    two = predict(cfg, CarState(), [Command(throttle=1.0), Command(brake=1.0)], DT, 0.1)
    assert two[0].throttle_level > 0.0 and two[-1].brake_level > two[1].brake_level


def test_bad_calls_say_why():
    with pytest.raises(ValueError, match='dt'):
        step(ActuatorConfig(), CarState(), Command(), 0.0)
    with pytest.raises(ValueError, match='speed loop'):
        step(ActuatorConfig(), CarState(), Command(speed=1.0), DT)
    with pytest.raises(ValueError, match='command'):
        predict(ActuatorConfig(), CarState(), [], DT, 1.0)


def test_the_shared_vectors_are_up_to_date():
    """vectors.json is what car_model.py gives now: else run car-model/gen_vectors.py."""
    spec = importlib.util.spec_from_file_location('car_model_gen_vectors',
                                                  CRATE / 'gen_vectors.py')
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    saved = json.loads((CRATE / 'vectors.json').read_text())
    for case in saved['cases']:
        cfg = ActuatorConfig(**case['config'])
        got = gen.run(cfg, case['speed_loop'], case['dt'], case['commands'])
        assert got == case['states'], f"{case['name']}: run car-model/gen_vectors.py"
