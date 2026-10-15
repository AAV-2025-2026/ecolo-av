import math

from aav_gazebo.imu import body_acceleration
import pytest


def test_straight_line_is_the_speed_change():
    assert body_acceleration(1.2, 3.0, 0.0) == (1.2, 0.0)
    assert body_acceleration(-2.5, 3.0, 0.0, x=0.5) == (-2.5, 0.0)


def test_a_steady_left_turn_pulls_left():
    # 1 m/s round a 2.87 m circle (full lock on a 1.57 m wheelbase): r = 0.348 rad/s.
    r = 1.0 / 2.87
    fwd, left = body_acceleration(0.0, 1.0, r)
    assert left == pytest.approx(1.0 / 2.87)          # v^2 / R
    assert fwd == 0.0
    # Ahead of the axle, the point also swings round: a small pull back toward the centre.
    fwd, left = body_acceleration(0.0, 1.0, r, x=0.5)
    assert fwd == pytest.approx(-0.5 * r * r)
    assert math.hypot(fwd, left) == pytest.approx(r * r * math.hypot(2.87, 0.5))


def test_right_turn_and_a_growing_yaw_rate():
    assert body_acceleration(0.0, 2.0, -0.1)[1] == pytest.approx(-0.2)
    assert body_acceleration(0.0, 0.0, 0.0, yaw_accel=0.4, x=0.5)[1] == pytest.approx(0.2)
