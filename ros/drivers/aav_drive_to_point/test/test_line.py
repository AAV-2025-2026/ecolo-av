"""The line to B, the carrot on it, pure pursuit and the turning circles."""

import math

from aav_drive_to_point.line import (bearing_error, Line, min_radius, Pose, pursuit_curvature,
                                     reachable, to_car, turn_speed_limit, wrap)
import pytest

R = min_radius(1.57, 0.5)


def test_the_tightest_turn():
    assert R == pytest.approx(1.57 / math.tan(0.5))
    with pytest.raises(ValueError):
        min_radius(0.0, 0.5)


def test_wrap_and_the_car_frame():
    assert wrap(3 * math.pi / 2) == pytest.approx(-math.pi / 2)
    north = Pose(1.0, 1.0, math.pi / 2)
    ahead, left = to_car(north, (1.0, 3.0))
    assert (ahead, left) == pytest.approx((2.0, 0.0))
    assert bearing_error(north, (0.0, 1.0)) == pytest.approx(math.pi / 2)   # west is left


def test_progress_along_and_across_the_line():
    line = Line((0.0, 0.0), (10.0, 0.0))
    assert line.progress((4.0, 1.0)) == pytest.approx((6.0, 1.0))     # left of it
    assert line.progress((12.0, -2.0)) == pytest.approx((-2.0, -2.0))  # past B, right
    with pytest.raises(ValueError):
        Line((1.0, 1.0), (1.0, 1.0)).unit()


def test_the_carrot_is_ahead_on_the_line_and_runs_past_b():
    line = Line((0.0, 0.0), (10.0, 0.0))
    assert line.carrot((4.0, 0.0), 2.0) == pytest.approx((6.0, 0.0))
    assert line.carrot((4.0, 1.2), 2.0) == pytest.approx((5.6, 0.0))
    assert line.carrot((9.5, 0.0), 2.0) == pytest.approx((11.5, 0.0))
    assert line.carrot((4.0, 5.0), 2.0) == pytest.approx((4.0, 0.0))   # far off: the foot


def test_pure_pursuit():
    car = Pose(0.0, 0.0, 0.0)
    assert pursuit_curvature(car, (5.0, 0.0), 1.0) == 0.0
    # Through (2, 2) from the origin facing east: a quarter circle of radius 2.
    assert pursuit_curvature(car, (2.0, 2.0), 1.0) == pytest.approx(0.5)
    assert pursuit_curvature(car, (2.0, -2.0), 0.3) == pytest.approx(-0.3)   # full lock
    assert pursuit_curvature(car, (-5.0, 0.0), 0.3) == pytest.approx(0.3)    # dead behind
    assert pursuit_curvature(car, (-5.0, -1.0), 0.3) == pytest.approx(-0.3)


def test_inside_the_tightest_circle_is_unreachable():
    car = Pose(0.0, 0.0, 0.0)
    assert reachable(car, (10.0, 0.0), R)
    assert reachable(car, (-10.0, 0.0), R)          # behind, but far: turn round
    assert not reachable(car, (0.0, 2.0 * R), R)    # beside it, one turn across
    assert not reachable(car, (R, R), R)            # on the left circle
    assert reachable(car, (0.0, 10.0), R)


def test_tight_turns_go_slower():
    assert turn_speed_limit(0.0, 1.5) == math.inf
    assert turn_speed_limit(1.0 / R, 1.5) == pytest.approx(math.sqrt(1.5 * R))
