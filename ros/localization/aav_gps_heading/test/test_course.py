import math

from aav_gps_heading.course import antenna_direction, CourseSettings, heading, wrap
import pytest

VAR = 0.05 ** 2        # (m/s)^2: a u-blox receiver's speed accuracy, 0.05 m/s


def velocity(yaw, speed, turn=0.0, antenna=(0.0, 0.0)):
    """Return the antenna's (east, north) velocity for a car at yaw, as the GPS would see it."""
    x_a, y_a = antenna
    fwd, left = speed - turn * y_a, turn * x_a        # in base_link
    c, s = math.cos(yaw), math.sin(yaw)
    return c * fwd - s * left, s * fwd + c * left


@pytest.mark.parametrize('yaw', [0.0, 0.7, -2.0, 3.1])
def test_forward_the_heading_is_the_course(yaw):
    out, _ = heading(*velocity(yaw, 0.5), VAR, VAR, 0.5, 0.0)
    assert out == pytest.approx(yaw)


@pytest.mark.parametrize('yaw', [0.0, 0.7, -2.0, 3.1])
def test_reversing_the_heading_is_the_course_turned_round(yaw):
    out, _ = heading(*velocity(yaw, -0.5), VAR, VAR, -0.5, 0.0)
    assert wrap(out - yaw) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize('speed', [1.0, -0.5])
@pytest.mark.parametrize('antenna', [(0.8, 0.0), (0.8, 0.3), (-0.4, -0.2)])
def test_an_antenna_off_the_rear_axle_swings_out_in_a_turn_and_is_taken_out(speed, antenna):
    yaw, turn = 1.2, 0.3
    east, north = velocity(yaw, speed, turn, antenna)
    assert abs(wrap(math.atan2(north, east) - yaw)) > 0.05 or speed < 0   # it does swing
    out, _ = heading(east, north, VAR, VAR, speed, turn, antenna)
    assert wrap(out - yaw) == pytest.approx(0.0, abs=1e-9)


def test_over_the_rear_axle_the_antenna_goes_where_the_car_points():
    assert antenna_direction(0.5, 0.4, (0.0, 0.0)) == 0.0
    assert antenna_direction(-0.5, 0.4, (0.0, 0.0)) == pytest.approx(math.pi)


def test_slower_than_min_speed_says_nothing():
    assert heading(*velocity(0.0, 0.25), VAR, VAR, 0.25, 0.0) is None
    assert heading(0.5, 0.0, VAR, VAR, 0.1, 0.0) is None       # the wheels say parked


def test_gps_and_wheels_that_disagree_say_nothing():
    # A spinning wheel, or a stale velocity from before the car stopped.
    assert heading(0.5, 0.0, VAR, VAR, 1.5, 0.0) is None
    assert heading(0.5, 0.0, VAR, VAR, 0.7, 0.0) is not None


def test_nan_says_nothing():
    assert heading(math.nan, 0.5, VAR, VAR, 0.5, 0.0) is None
    assert heading(0.5, 0.0, VAR, VAR, math.nan, 0.0) is None


def test_slower_is_less_sure_and_the_floor_stays():
    floor = CourseSettings().floor
    _, slow = heading(0.5, 0.0, VAR, VAR, 0.5, 0.0)
    _, fast = heading(2.0, 0.0, VAR, VAR, 2.0, 0.0)
    assert slow > fast > floor ** 2
    # 0.05 m/s across 0.5 m/s: 0.1 rad, with the 2 degree floor on top.
    assert slow == pytest.approx(0.1 ** 2 + floor ** 2)


def test_only_the_noise_across_the_travel_counts():
    # Going north, the east noise turns the course; the north noise only changes the speed.
    _, var = heading(0.0, 1.0, 0.04, 100.0, 1.0, 0.0, settings=CourseSettings(floor=0.0))
    assert var == pytest.approx(0.04)
