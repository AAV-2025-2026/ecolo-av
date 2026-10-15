import math

from aav_language.drive_maths import (haversine, min_turn_radius, plan_arc, plan_distance,
                                      ramp_distance)
from aav_scripted.speed_profile import SpeedProfile, STOPPED
import pytest


def run_profile(goal, dt=0.02):
    """Metres covered when scripted_driver drives this goal, with the car keeping up."""
    p = SpeedProfile(goal.target_speed, goal.acceleration, goal.deceleration,
                     goal.hold_time, goal.hold_distance)
    distance = 0.0
    for _ in range(1_000_000):
        v = p.step(dt, distance)
        distance += abs(v) * dt
        if p.phase == STOPPED:
            return distance
    raise AssertionError('the profile never stopped')


def test_ramps_are_v_squared_over_2a():
    assert ramp_distance(1.0, 0.5) == pytest.approx(1.0)
    assert ramp_distance(2.0, 1.0) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        ramp_distance(1.0, 0.0)


def test_long_drive_holds_for_the_rest():
    g = plan_distance(100.0, 1.0, 0.5, 0.5)
    # 1 m speeding up + 1 m slowing down: 98 m at 1 m/s
    assert g.target_speed == 1.0
    assert g.hold_distance == pytest.approx(98.0)
    assert g.hold_time == 0.0
    assert g.expected_duration == pytest.approx(2 + 2 + 98)


def test_short_drive_lowers_the_speed_so_both_ramps_fit():
    g = plan_distance(0.5, 1.0, 0.5, 0.5)
    assert g.hold_distance == 0.0
    # v^2/2a + v^2/2b = d
    v = g.target_speed
    assert ramp_distance(v, 0.5) + ramp_distance(v, 0.5) == pytest.approx(0.5)
    assert v < 1.0


def test_unequal_ramps():
    g = plan_distance(3.0, 2.0, 1.0, 2.0)
    v = g.target_speed
    assert ramp_distance(v, 1.0) + ramp_distance(v, 2.0) == pytest.approx(3.0)


def test_reverse_is_a_negative_speed():
    g = plan_distance(5.0, 0.5, 0.5, 0.5, reverse=True)
    assert g.target_speed == -0.5
    assert g.hold_distance == pytest.approx(4.5)


@pytest.mark.parametrize('distance,speed', [(10.0, 0.5), (100.0, 1.0), (0.4, 1.0),
                                            (2.0, 1.0), (5.0, 0.3)])
def test_the_real_speed_profile_covers_the_whole_distance(distance, speed):
    # aav_scripted's own SpeedProfile, stepped the way scripted_driver steps it.
    g = plan_distance(distance, speed, 0.5, 0.5)
    assert run_profile(g) == pytest.approx(distance, abs=0.03)


@pytest.mark.parametrize('bad', [0.0, -1.0, math.inf, math.nan])
def test_bad_numbers_are_refused(bad):
    with pytest.raises(ValueError):
        plan_distance(bad, 0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        plan_distance(5.0, bad, 0.5, 0.5)


def test_arc_length_and_curvature():
    a = plan_arc(90.0, 5.0)
    assert a.length == pytest.approx(5.0 * math.pi / 2)
    assert a.curvature == pytest.approx(0.2)
    right = plan_arc(-45.0, 8.0)
    assert right.curvature == pytest.approx(-0.125)
    assert right.length == pytest.approx(8.0 * math.pi / 4)
    with pytest.raises(ValueError):
        plan_arc(0.0, 5.0)
    with pytest.raises(ValueError):
        plan_arc(90.0, 0.0)


def test_min_turn_radius_is_the_bicycle_model():
    # vehicle.yaml today: wheelbase 1.57 m, 0.5 rad
    assert min_turn_radius(1.57, 0.5) == pytest.approx(1.57 / math.tan(0.5))
    with pytest.raises(ValueError):
        min_turn_radius(1.57, math.pi / 2)


def test_haversine():
    # one thousandth of a degree of latitude is about 111 m
    assert haversine(45.0, -75.0, 45.001, -75.0) == pytest.approx(111.2, abs=0.2)
    assert haversine(45.3861, -75.6959, 45.3861, -75.6959) == 0.0
