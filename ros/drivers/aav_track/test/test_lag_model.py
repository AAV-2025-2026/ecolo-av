"""
The car with its lags (lag_model.py): the spec, and the same car as Gazebo's actuator model.

aav_gazebo's actuator_model is what pixi run sim drives; both step their lags exactly
(exp), so they agree closely at a small step (the speed integrates a little differently).
"""

import math
from pathlib import Path

from aav_description import vehicle
from aav_gazebo.actuator_model import (ActuatorConfig, Actuators, speed_loop_profile,
                                       SpeedLoop)
from aav_track import lag_model as lm
import numpy as np
import pytest

VEHICLE_YAML = (Path(__file__).resolve().parents[3] / 'bringup' / 'aav_description' /
                'config' / 'vehicle.yaml')


def rest(**values):
    x = np.zeros(lm.NX)
    for name, value in values.items():
        x[getattr(lm, name.upper())] = value
    return x


def test_the_numbers_come_from_vehicle_yaml():
    cfg = vehicle.load(VEHICLE_YAML)
    car = lm.CarParams.from_vehicle(cfg)
    assert car.wheelbase == cfg['vehicle']['wheelbase']
    assert car.max_steering == cfg['vehicle']['max_steering_angle']
    for key, value in cfg['actuators'].items():
        if hasattr(car, key):
            assert getattr(car, key) == value
    assert car.steer_dead_time == 0.0             # not measured yet: none
    doubled = car.lags_scaled(2.0)
    assert doubled.steer_lag == 2 * car.steer_lag and doubled.brake_lag == 2 * car.brake_lag
    assert doubled.max_accel == car.max_accel


def test_full_throttle_speeds_up_through_the_lag():
    car, loop = lm.CarParams(drag=0.0), lm.speed_loop('default')
    x = rest()
    # Set speed far above: the PI pins the throttle at 1; the throttle lags it (0.1 s).
    for _ in range(100):
        x = lm.step(car, loop, x, [0.0, 50.0], 0.0, 0.01)
    assert x[lm.THROTTLE] == pytest.approx(1.0, abs=1e-3)
    # 1 s at 1.5 m/s^2, less what the lag held back (about tau x a_max).
    assert x[lm.V] == pytest.approx(1.5 * (1.0 - 0.1), abs=0.02)


def test_the_brake_never_reverses_the_car():
    car, loop = lm.CarParams(), lm.speed_loop('default')
    x = rest(v=0.5, brake=1.0)
    for _ in range(200):
        x = lm.step(car, loop, x, [0.0, 0.0], 0.0, 0.01)
        assert x[lm.V] >= 0.0
    assert x[lm.V] == 0.0 and x[lm.BRAKE] == pytest.approx(0.3, abs=1e-3)   # held


def test_the_steering_motor_is_rate_limited_then_lagged():
    car, loop = lm.CarParams(steer_lag=0.1, steer_rate=0.8), lm.speed_loop('default')
    x = rest()
    x = lm.step(car, loop, x, [0.4, 0.0], 0.0, 0.1)
    assert x[lm.MOTOR] == pytest.approx(0.08)             # 0.8 rad/s for 0.1 s
    for _ in range(100):
        x = lm.step(car, loop, x, [0.4, 0.0], 0.0, 0.01)
    assert x[lm.MOTOR] == pytest.approx(0.4) and x[lm.WHEELS] == pytest.approx(0.4, abs=1e-3)
    # Past full lock: the target is clamped.
    for _ in range(200):
        x = lm.step(car, loop, x, [2.0, 0.0], 0.0, 0.01)
    assert x[lm.MOTOR] == pytest.approx(car.max_steering)


def test_a_change_inside_the_deadband_does_not_move_the_motor():
    car, loop = lm.CarParams(steer_deadband=0.005), lm.speed_loop('default')
    x = rest(setpoint=0.1, motor=0.1, wheels=0.1)
    x = lm.step(car, loop, x, [0.103, 0.0], 0.0, 0.05)
    assert x[lm.MOTOR] == pytest.approx(0.1)
    x = lm.step(car, loop, x, [0.11, 0.0], 0.0, 0.05)
    assert x[lm.MOTOR] == pytest.approx(0.11)
    # Without the deadband (a plan's copy), every change moves it.
    x = lm.step(car.without_deadbands(), loop, rest(setpoint=0.1, motor=0.1), [0.103, 0.0],
                0.0, 0.05)
    assert x[lm.MOTOR] == pytest.approx(0.103)


def test_the_bicycle_in_the_paths_frame():
    car, loop = lm.CarParams(steer_rate=100.0, steer_lag=0.0, drag=0.0), lm.speed_loop('default')
    # On a 5 m left circle, at the circle's own steering: the errors stay at 0.
    kappa = 0.2
    d = math.atan(car.wheelbase * kappa)
    x = rest(v=1.0, setpoint=d, motor=d, wheels=d)
    for _ in range(100):
        x = lm.step(car, loop, x, [d, 1.0], kappa, 0.01)
    assert abs(x[lm.E_Y]) < 1e-3 and abs(x[lm.E_TH]) < 1e-3
    assert x[lm.S] == pytest.approx(1.0, abs=0.02)
    # Straight on a straight path, heading 0.1 rad left: drifts left at v sin(0.1).
    x = lm.step(car, loop, rest(v=1.0, e_th=0.1), [0.0, 1.0], 0.0, 0.01)
    assert x[lm.E_Y] == pytest.approx(0.01 * math.sin(0.1), rel=0.05)


def test_it_works_on_columns_as_on_one_state():
    car, loop = lm.CarParams(), lm.speed_loop('default')
    xs = np.stack([rest(v=v) for v in (0.0, 1.0, 2.0)], axis=1)
    us = np.array([[0.1, 0.0, -0.2], [1.0, 0.5, 3.0]])
    out = lm.step(car, loop, xs, us, 0.1, 0.05, 2)
    for i in range(3):
        one = lm.step(car, loop, xs[:, i], us[:, i], 0.1, 0.05, 2)
        assert out[:, i] == pytest.approx(one)


@pytest.mark.parametrize('profile', sorted(lm.SPEED_LOOPS))
def test_the_speed_loop_is_gazebos(profile):
    # The same set speeds and measured speeds into both: the same throttle and brake.
    rng = np.random.default_rng(3)
    ours, theirs = lm.speed_loop(profile), SpeedLoop(speed_loop_profile(profile))
    integral = 0.0
    for _ in range(500):
        target = float(rng.choice([0.0, rng.uniform(0.0, 3.0)]))
        measured = float(rng.uniform(0.0, 3.0))
        d = theirs.update(target, measured, 0.01)
        thr, brk, integral = lm.pedals(ours, np.float64(target), np.float64(measured),
                                       np.float64(integral), 0.01)
        assert float(thr) == pytest.approx(d.throttle, abs=1e-12)
        assert float(brk) == pytest.approx(d.brake, abs=1e-12)
        assert float(integral) == pytest.approx(theirs.integral, abs=1e-12)


def test_unknown_speed_loops_are_refused():
    with pytest.raises(ValueError, match='lqi'):
        lm.speed_loop('lqi')


def test_it_drives_as_gazebos_actuator_model():
    # Speed and steering commands for 6 s: the speed, and the wheels' angle, agree with
    # aav_gazebo's Actuators within a few per cent at a 2 ms step.
    dt = 0.002
    cfg = ActuatorConfig()
    gz = Actuators(cfg)
    car = lm.CarParams()
    loop = lm.speed_loop('default')
    x = rest()
    for i in range(3000):
        t = i * dt
        speed = 1.5 if t < 4.0 else 0.0
        steer = 0.3 if 1.0 < t < 3.0 else -0.1
        s = gz.step(speed, steer, dt)
        x = lm.step(car, loop, x, [steer, speed], 0.0, dt)
        assert x[lm.V] == pytest.approx(s.speed, abs=0.02)
        assert x[lm.WHEELS] + car.steer_offset == pytest.approx(s.steering, abs=0.01)
