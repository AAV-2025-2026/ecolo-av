"""The stopping law (stop_law.py): one curve, its cap, its numbers from the car model."""

import math

from aav_description import stop_law
from aav_description.car_model import ActuatorConfig, speed_loop_profile, SpeedLoopConfig
from aav_description.stop_law import from_car_model, nav2_cap, stop_point, StopCurve
import pytest

CURVE = StopCurve(a=1.0, j=2.0, rho=0.35)
SPEEDS = [0.05 * i for i in range(1, 81)]          # up to 4 m/s
DISTANCES = [0.05 * i for i in range(1, 401)]      # up to 20 m


def test_the_design_numbers():
    # docs/designs/2026-11-05_how-the-car-stops.md, "The numbers".
    assert CURVE.tau == pytest.approx(0.6)
    for d, v in ((0.5, 0.57), (1.0, 0.94), (1.1, 1.00), (2.0, 1.49), (5.0, 2.62)):
        assert CURVE.cap(d) == pytest.approx(v, abs=0.005)
    assert CURVE.demand(1.0) == pytest.approx(0.625)


def test_the_car_models_numbers_give_the_design_curve():
    assert from_car_model(ActuatorConfig(), loop=None) == CURVE


def test_a_dead_time_or_a_slower_brake_lengthens_the_stop():
    slow = from_car_model(ActuatorConfig(brake_lag=0.4, brake_dead_time=0.1), loop=None)
    assert slow.rho == pytest.approx(0.65)
    assert all(slow.distance(v) > CURVE.distance(v) for v in SPEEDS)
    weak = from_car_model(ActuatorConfig(max_brake=1.0), loop=None)
    assert weak.a == pytest.approx(0.5)
    # Beyond 0.2 m: closer, the softer brake also eases in sooner (a/2j), and wins.
    assert all(weak.cap(d) < CURVE.cap(d) for d in DISTANCES if d >= 0.2)


def test_the_speed_loops_lag_is_in_rho():
    # The spine's default PI coasts 0.2 m/s and brakes 0.5 per m/s past it: to brake at
    # 1 m/s^2 with a 3 m/s^2 brake the car runs 0.2 + 1/1.5 m/s fast, 0.87 s behind.
    assert stop_law.loop_lag(SpeedLoopConfig(), 1.0, 3.0) == pytest.approx(0.2 + 1 / 1.5)
    assert stop_law.loop_lag(None, 1.0, 3.0) == 0.0
    curve = from_car_model(ActuatorConfig())
    assert curve.rho == pytest.approx(0.35 + 0.2 + 1 / 1.5)
    assert all(curve.distance(v) > CURVE.distance(v) for v in SPEEDS)
    # The LQI follows faster than the PI.
    lqi = from_car_model(ActuatorConfig(), loop=speed_loop_profile('lqi'))
    assert CURVE.rho < lqi.rho < curve.rho


def test_cap_and_distance_are_inverses():
    for v in SPEEDS:
        assert CURVE.cap(CURVE.distance(v)) == pytest.approx(v)


def test_demand_stays_below_a():
    assert all(0.0 < CURVE.demand(v) < CURVE.a for v in SPEEDS)


def test_the_slope_at_the_stop_is_finite():
    # d v_cap / d d at 0 is 1/tau: the speed falls smoothly into the stop.
    eps = 1e-6
    assert CURVE.cap(eps) / eps == pytest.approx(1.0 / CURVE.tau, rel=1e-3)


def test_h_is_zero_on_the_curve():
    for v in SPEEDS:
        assert CURVE.h(CURVE.distance(v) + 0.3, v, 0.3) == pytest.approx(0.0, abs=1e-9)


def test_bad_numbers_are_refused_and_bad_distances_give_zero():
    for bad in ({'a': 0.0}, {'j': -1.0}, {'rho': -0.1}, {'a': math.nan}):
        with pytest.raises(ValueError):
            StopCurve(**{'a': 1.0, 'j': 2.0, 'rho': 0.35, **bad})
    assert CURVE.cap(-1.0) == 0.0
    assert CURVE.cap(math.nan) == 0.0
    assert CURVE.cap(0.0) == 0.0


def test_nav2s_cap_is_never_between_zero_and_the_floor_or_above_the_base():
    for d in [0.0, -1.0, math.nan] + DISTANCES:
        cap = nav2_cap(d, CURVE, base=1.0)
        assert cap == 0.0 or stop_law.FLOOR <= cap <= 1.0
    assert nav2_cap(0.0, CURVE, 1.0) == stop_law.FLOOR      # at the mark: the floor, not 0
    assert nav2_cap(100.0, CURVE, 1.0) == 0.0               # far away: no limit


def test_the_stop_point_from_the_car_model():
    cfg = ActuatorConfig()
    one, t1 = stop_point(cfg, 1.0, 1.0)
    two, t2 = stop_point(cfg, 2.0, 1.0)
    # Further and longer than a perfect ramp (v^2 / 2 ramp): the lags, the speed loop.
    assert 0.5 < one < 2.0 and 2.0 < two < 5.0
    assert t1 > 1.0 and t2 > 2.0
    # A brake that answers later stops later.
    late, _ = stop_point(ActuatorConfig(brake_dead_time=0.2), 1.0, 1.0)
    assert late > one
    with pytest.raises(ValueError):
        stop_point(cfg, 0.0, 1.0)
