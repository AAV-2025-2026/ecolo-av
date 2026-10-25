import math

from aav_gazebo import wheels


def test_spin_times_radius_and_nan_for_a_missing_wheel():
    got = wheels.ground_speeds(
        ['rear_left_wheel_joint', 'rear_right_wheel_joint', 'front_left_steering_joint',
         'front_left_wheel_joint'],
        [10.0, -2.0, 0.3, 4.0], 0.15)
    assert math.isclose(got['rear_left'], 1.5)
    assert math.isclose(got['rear_right'], -0.3)
    assert math.isclose(got['front_left'], 0.6)
    assert math.isnan(got['front_right'])


def test_a_message_with_no_velocities_gives_nan():
    got = wheels.ground_speeds(['rear_left_wheel_joint'], [], 0.15)
    assert all(math.isnan(v) for v in got.values())
