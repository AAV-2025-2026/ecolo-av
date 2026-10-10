import math

from aav_ego.ackermann import EgoModel, Limits, slew_speed, steering_angle, turn_rate
import pytest

LIM = Limits(wheelbase=1.57, max_steering_angle=0.5, max_speed=2.0, max_reverse_speed=1.0,
             max_acceleration=1.0, max_deceleration=2.0, max_steering_rate=10.0)


def test_straight_is_zero_steering():
    assert steering_angle(1.0, 0.0, LIM, hold=0.3) == 0.0


def test_left_turn_is_positive():
    d = steering_angle(1.0, 0.2, LIM, hold=0.0)
    assert d == pytest.approx(math.atan(1.57 * 0.2))
    assert d > 0


def test_steering_is_clamped():
    assert steering_angle(0.5, 2.0, LIM, hold=0.0) == LIM.max_steering_angle
    assert steering_angle(0.5, -2.0, LIM, hold=0.0) == -LIM.max_steering_angle


def test_reverse_uses_the_bicycle_model():
    # Reversing with the wheels turned right swings the car counter-clockwise.
    d = steering_angle(-1.0, 0.2, LIM, hold=0.0)
    assert d < 0
    assert turn_rate(-1.0, d, LIM.wheelbase) == pytest.approx(0.2)


@pytest.mark.parametrize('v,w', [(1.0, 0.1), (0.3, -0.1), (-0.5, 0.05), (2.0, 0.4)])
def test_round_trip_for_feasible_turns(v, w):
    d = steering_angle(v, w, LIM, hold=0.0)
    assert turn_rate(v, d, LIM.wheelbase) == pytest.approx(w)


def test_standstill_holds_the_wheels():
    assert steering_angle(0.0, 0.5, LIM, hold=0.2) == 0.2


def test_speed_ramps_at_the_limits():
    assert slew_speed(0.0, 2.0, LIM, 0.1)[0] == pytest.approx(0.1)   # accelerate 1 m/s^2
    assert slew_speed(1.0, 0.0, LIM, 0.1)[0] == pytest.approx(0.8)   # decelerate 2 m/s^2


def test_direction_change_goes_through_zero():
    speed, _ = slew_speed(0.1, -1.0, LIM, 0.1)
    assert speed == pytest.approx(0.0)


def test_speed_is_capped_but_curvature_kept():
    m = EgoModel(LIM)
    for _ in range(100):
        speed, steering, _ = m.step((5.0, 0.5), 0.1)
    assert speed == pytest.approx(LIM.max_speed)
    assert steering == pytest.approx(min(math.atan(1.57 * 0.5 / 5.0), 0.5))


def test_stale_command_stops_the_car():
    m = EgoModel(LIM)
    for _ in range(30):
        m.step((1.0, 0.0), 0.1)
    for _ in range(30):
        speed, _, _ = m.step(None, 0.1)
    assert speed == 0.0


def test_steering_rate_is_limited():
    slow = Limits(max_steering_rate=0.5)
    m = EgoModel(slow)
    _, d, _ = m.step((1.0, 1.0), 0.1)
    assert d == pytest.approx(0.05)
