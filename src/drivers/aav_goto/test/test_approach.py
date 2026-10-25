"""The speed plan: up gently, hold, slow down by the distance left, stop at B."""

import math

from aav_goto.approach import (ACCELERATE, Approach, DECELERATE, HOLD, planned_deceleration,
                               STOPPING, stopping_distance)
import pytest


def test_the_plan_brakes_at_half_the_measured_braking():
    assert planned_deceleration(3.0) == 1.5
    assert planned_deceleration(3.0, 1.0) == 3.0
    for bad in (0.0, -1.0, math.nan):
        with pytest.raises(ValueError):
            planned_deceleration(bad)
    with pytest.raises(ValueError):
        planned_deceleration(3.0, 0.0)


def test_bad_numbers_are_refused():
    with pytest.raises(ValueError):
        Approach(cruise=0.0, accel=0.5, decel=1.5)
    with pytest.raises(ValueError):
        Approach(cruise=1.0, accel=math.nan, decel=1.5)
    with pytest.raises(ValueError):
        Approach(cruise=1.0, accel=0.5, decel=1.5, lead=-0.1)


def test_a_perfect_car_speeds_up_holds_and_stops_at_b():
    plan = Approach(cruise=1.0, accel=0.5, decel=1.5)
    dt, left, v, phases, top = 0.02, 20.0, 0.0, [], 0.0
    for _ in range(10000):
        v, phase = plan.step(v, dt, left, v)
        if not phases or phases[-1] != phase:
            phases.append(phase)
        top = max(top, v)
        left -= v * dt
        if phase == STOPPING:
            break
    assert phases == [ACCELERATE, HOLD, DECELERATE, STOPPING]
    assert top == pytest.approx(1.0)
    assert 0.0 <= left <= plan.stop_band     # stopped at B, not before or past it


def test_speeding_up_is_a_gentle_ramp():
    plan = Approach(cruise=2.0, accel=0.5, decel=1.5)
    v, _ = plan.step(0.0, 0.1, 50.0, 0.0)
    assert v == pytest.approx(0.05)


def test_slowing_down_follows_the_distance_left():
    plan = Approach(cruise=3.0, accel=0.5, decel=1.5)
    for left in (0.5, 1.0, 2.0):
        v, phase = plan.step(3.0, 0.02, left, 3.0)
        assert phase == DECELERATE
        assert v == pytest.approx(math.sqrt(2 * 1.5 * left))
    # From the speed it gives, braking at decel takes exactly the distance left.
    v, _ = plan.step(3.0, 0.02, 2.0, 3.0)
    assert stopping_distance(v, 1.5) == pytest.approx(2.0)


def test_the_lead_starts_slowing_sooner_the_faster_the_car_goes():
    plan = Approach(cruise=3.0, accel=0.5, decel=1.5, lead=0.8)
    assert plan.braking_speed(2.0, 0.0) == pytest.approx(math.sqrt(6.0))
    assert plan.braking_speed(2.0, 1.0) == pytest.approx(math.sqrt(2 * 1.5 * 1.2))
    assert plan.braking_speed(2.0, 3.0) == 0.0


def test_short_of_b_it_creeps_rather_than_stopping_early():
    plan = Approach(cruise=1.0, accel=0.5, decel=1.5, lead=0.8, creep=0.1)
    # The lead says stop, but the car is still 0.3 m short: creep on.
    v, phase = plan.step(0.4, 0.02, 0.3, 0.4)
    assert phase == DECELERATE and v == pytest.approx(0.1)


def test_at_or_past_b_it_commands_zero():
    plan = Approach(cruise=1.0, accel=0.5, decel=1.5)
    assert plan.step(1.0, 0.02, plan.stop_band, 1.0) == (0.0, STOPPING)
    assert plan.step(1.0, 0.02, -0.5, 1.0) == (0.0, STOPPING)


def test_never_far_ahead_of_the_car():
    # Held back (a stop sign, a person on the joystick): it restarts from the car's speed.
    plan = Approach(cruise=1.0, accel=0.5, decel=1.5, ahead=0.5)
    v, _ = plan.step(1.0, 0.02, 30.0, 0.0)
    assert v == pytest.approx(0.5)


def test_a_turn_caps_the_speed():
    plan = Approach(cruise=3.0, accel=0.5, decel=1.5)
    v, phase = plan.step(3.0, 0.02, 30.0, 3.0, limit=2.0)
    assert v == pytest.approx(2.0) and phase == HOLD


def test_the_ideal_time():
    plan = Approach(cruise=1.0, accel=0.5, decel=1.5)
    # 2 s up (1 m), 2/3 s down (1/3 m), the rest at 1 m/s.
    assert plan.ideal_time(10.0) == pytest.approx(2.0 + 2.0 / 3.0 + (10.0 - 1.0 - 1.0 / 3.0))
    short = plan.ideal_time(0.5)
    assert 0 < short < plan.ideal_time(10.0)
