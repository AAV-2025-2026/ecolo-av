import math
from pathlib import Path

from aav_gazebo.actuator_model import (ActuatorConfig, Actuators, Ideal, lag, SpeedLoop,
                                       SpeedLoopConfig)
import pytest
import yaml

DT = 0.02   # gazebo_adapter's 50 Hz
VEHICLE_YAML = (Path(__file__).resolve().parents[3] / 'aav_description' / 'config'
                / 'vehicle.yaml')


def run(model, speed, steer, seconds):
    states = [model.step(speed, steer, DT) for _ in range(round(seconds / DT))]
    return states[-1], states


def test_vehicle_yaml_has_every_actuator_number():
    cfg = yaml.safe_load(VEHICLE_YAML.read_text())
    a = ActuatorConfig.from_vehicle(cfg)
    assert set(cfg['actuators']) <= set(vars(a)), 'an unknown key in actuators:'
    assert a.max_steering == cfg['vehicle']['max_steering_angle']
    # The guesses match Gazebo's old limits (READ-ME-FULL-SIMULATION.md).
    assert a.max_accel == 1.5 and a.max_brake == 3.0


def test_lag_reaches_63_percent_in_one_time_constant():
    v = 0.0
    for _ in range(50):
        v = lag(v, 1.0, 1.0, 0.02)
    assert v == pytest.approx(1.0 - math.exp(-1.0))
    assert lag(0.0, 1.0, 0.0, 0.02) == 1.0


def test_full_throttle_gives_max_accel_less_drag():
    cfg = ActuatorConfig(throttle_lag=0.0, drag=0.0)
    car = Actuators(cfg, SpeedLoopConfig(kp=100.0))   # always full throttle
    s, _ = run(car, 10.0, 0.0, 1.0)
    assert s.throttle == 1.0
    assert s.speed == pytest.approx(1.5, abs=0.01)
    assert s.accel == pytest.approx(1.5, abs=0.01)


def test_drag_balances_throttle_at_a_top_speed():
    cfg = ActuatorConfig(throttle_lag=0.0, drag=0.5)
    car = Actuators(cfg, SpeedLoopConfig(kp=100.0))
    s, _ = run(car, 100.0, 0.0, 30.0)
    assert s.speed == pytest.approx(1.5 / 0.5, rel=0.02)


def test_coasting_slows_by_drag_alone():
    car = Actuators(ActuatorConfig(drag=0.1))
    car.speed = 2.0
    # Throttle and brake at zero: drive the model directly, with a loop that never asks.
    car.loop.update = lambda target, measured, dt: type(
        'D', (), {'throttle': 0.0, 'brake': 0.0, 'reverse': False})()
    s, _ = run(car, 2.0, 0.0, 1.0)
    assert s.speed == pytest.approx(2.0 * math.exp(-0.1), rel=0.01)
    assert s.brake == 0.0 and s.throttle == 0.0


def test_full_brake_stops_at_max_brake_and_never_reverses():
    cfg = ActuatorConfig(brake_lag=0.0, drag=0.0)
    car = Actuators(cfg, SpeedLoopConfig(brake_gain=100.0, hold_brake=1.0))
    car.speed = 3.0
    s, states = run(car, 0.0, 0.0, 0.5)
    assert states[0].accel == pytest.approx(-3.0)
    s, _ = run(car, 0.0, 0.0, 2.0)
    assert s.speed == 0.0
    assert s.brake_command == 1.0


def test_the_brake_takes_time_to_bite():
    car = Actuators(ActuatorConfig(brake_lag=0.2))
    car.speed = 2.0
    first = car.step(0.0, 0.0, DT)
    assert first.brake_command > 0.3
    assert first.brake < 0.2 * first.brake_command


def test_the_speed_loop_settles_on_the_target():
    car = Actuators()
    s, states = run(car, 1.0, 0.0, 30.0)
    assert s.speed == pytest.approx(1.0, abs=0.02)
    assert max(x.speed for x in states) < 1.25        # no wild overshoot
    assert all(x.throttle == 0.0 or x.brake_command == 0.0 for x in states)


def test_below_the_throttle_deadband_the_car_doesnt_move():
    cfg = ActuatorConfig(throttle_deadband=0.5, throttle_lag=0.0)
    car = Actuators(cfg, SpeedLoopConfig(kp=0.1, ki=0.0))   # 0.1 throttle: in the deadband
    s, _ = run(car, 1.0, 0.0, 2.0)
    assert s.throttle == pytest.approx(0.1)
    assert s.speed == 0.0


def test_reverse_waits_for_a_stop_then_backs_up():
    car = Actuators()
    car.speed = 1.0
    s, states = run(car, -0.5, 0.0, 30.0)
    assert states[0].brake_command > 0.0 and states[0].throttle_command == 0.0
    assert s.speed == pytest.approx(-0.5, abs=0.1)


def test_steering_is_rate_limited_then_lags():
    cfg = ActuatorConfig(steer_rate=0.8, steer_lag=0.1, steer_deadband=0.0)
    car = Actuators(cfg)
    s, states = run(car, 0.0, 0.4, 0.3)
    assert car.motor == pytest.approx(0.24, abs=1e-6)    # 0.8 rad/s for 0.3 s
    assert s.steering < car.motor                         # the linkage is behind
    s, _ = run(car, 0.0, 0.4, 2.0)
    assert s.steering == pytest.approx(0.4, abs=1e-3)
    assert s.steer_command == 0.4


def test_steering_stops_at_full_lock():
    car = Actuators(ActuatorConfig(max_steering=0.5))
    s, _ = run(car, 0.0, 2.0, 5.0)
    assert s.steering == pytest.approx(0.5)


def test_the_centre_offset_shows_when_told_straight():
    car = Actuators(ActuatorConfig(steer_offset=0.02))
    s, _ = run(car, 0.0, 0.0, 1.0)
    assert s.steering == pytest.approx(0.02)


def test_small_steering_changes_are_lost_in_the_deadband():
    car = Actuators(ActuatorConfig(steer_deadband=0.01, steer_lag=0.0))
    s, _ = run(car, 0.0, 0.008, 1.0)
    assert s.steering == 0.0
    s, _ = run(car, 0.0, 0.02, 1.0)
    assert s.steering == pytest.approx(0.02)


def test_ideal_keeps_gazebos_old_limits_and_steers_at_once():
    ideal = Ideal(ActuatorConfig(max_steering=0.5))
    s, _ = run(ideal, 3.0, 0.3, 1.0)
    assert s.speed == pytest.approx(1.5)
    assert s.steering == 0.3
    s, _ = run(ideal, 0.0, 0.9, 0.3)
    assert s.speed == pytest.approx(1.5 - 0.9)
    assert s.steering == 0.5
    assert math.isnan(s.throttle)


def test_a_bad_time_step_is_refused():
    with pytest.raises(ValueError):
        Actuators().step(1.0, 0.0, 0.0)


def test_speed_loop_matches_the_spines_rules():
    # The same cases as spine-core's speed_loop.rs tests.
    loop = SpeedLoop()
    d = loop.update(1.0, 0.0, DT)
    assert d.throttle > 0.0 and d.brake == 0.0
    d = SpeedLoop().update(1.0, 2.0, DT)
    assert d.throttle == 0.0 and d.brake > 0.0
    d = SpeedLoop().update(0.0, 0.0, DT)
    assert d.brake == SpeedLoopConfig().hold_brake
