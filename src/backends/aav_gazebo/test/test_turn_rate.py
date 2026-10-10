import math

import pytest

pytest.importorskip('rclpy')   # the module imports ROS messages; runs under colcon test

from aav_gazebo.gazebo_adapter import turn_rate  # noqa: E402


def test_straight_and_stopped():
    assert turn_rate(1.0, 0.0, 1.57) == 0.0
    assert turn_rate(0.0, 0.4, 1.57) == 0.0


def test_matches_bicycle_model_both_ways():
    w = turn_rate(2.0, 0.3, 1.57)
    assert math.isclose(w, 2.0 * math.tan(0.3) / 1.57)
    assert math.isclose(turn_rate(-2.0, 0.3, 1.57), -w)   # reversing turns the other way
