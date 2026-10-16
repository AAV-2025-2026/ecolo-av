import math
import random

from aav_safety.watchdog import DISAGREE, OK, Rule, Watchdog
from aav_safety.wheel_check import CrossCheck, trapezoid, WheelCheck
import pytest

RATE = 50.0     # Hz, the wheels and the IMU both


def drive(check, speed, turn=lambda t: 0.0, start=0.0, end=10.0, frozen_at=None, slope=0.0,
          noise=0.0, rng=None):
    """
    Feed check a car whose speed is speed(t); return when it first latched, or None.

    frozen_at: from then on the wheels repeat their speed and turn rate. slope: m/s^2 of
    gravity the IMU's forward reading adds.
    """
    dt, t, held = 1.0 / RATE, start, None
    while t <= end:
        accel = (speed(t + 1e-3) - speed(t - 1e-3)) / 2e-3
        if frozen_at is not None and t >= frozen_at and held is None:
            held = (speed(t), turn(t))
        v, w = held if held is not None else (speed(t), turn(t))
        check.wheels(t, v, w)
        a = accel + slope + (rng.gauss(0.0, noise) if rng else 0.0)
        check.imu(t, a, turn(t) + (rng.gauss(0.0, noise / 10) if rng else 0.0))
        if check.update(t) is not None:
            return t
        t += dt
    return None


def ramp(t, t0=1.0, accel=0.5, top=1.0):
    return min(top, max(0.0, (t - t0) * accel))


def test_the_trapezoid_adds_up_a_ramp():
    samples = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
    assert trapezoid(samples, 0.0, 2.0) == pytest.approx(2.0)
    assert trapezoid(samples, 0.5, 1.5) == pytest.approx(1.0)


def test_normal_driving_never_latches():
    rng = random.Random(1)
    check = WheelCheck()
    assert drive(check, ramp, turn=lambda t: 0.2 * math.sin(t), end=30.0,
                 noise=0.2, rng=rng) is None
    assert check.worst[0] < 0.15 and check.worst[1] < 0.05


def test_wheels_frozen_while_speeding_up_latch_within_two_seconds():
    check = WheelCheck()
    t = drive(check, ramp, frozen_at=1.5)
    assert t is not None and t - 1.5 < 2.5
    assert 'disagree' in check.update(t + 5.0)        # latched
    check.clear()
    assert check.update(t + 5.0) is None


def test_wheels_frozen_at_a_speed_the_car_keeps_say_nothing_until_it_changes():
    def speed(t):
        return 1.0 if t < 8.0 else max(0.0, 1.0 - (t - 8.0) * 1.0)    # brakes at 8 s
    check = WheelCheck()
    t = drive(check, speed, frozen_at=3.0, end=12.0)
    assert t is not None and 8.0 < t < 10.5


def test_wheels_frozen_in_a_turn_latch_from_the_gyro():
    check = WheelCheck()
    t = drive(check, lambda t: 1.0, turn=lambda t: 0.0 if t < 4.0 else 0.4, frozen_at=2.0)
    assert t is not None and 4.0 < t < 6.0


def test_a_slope_is_learnt_standing_still():
    # 0.5 m/s^2 of gravity in the forward reading: a 3 degree hill, or a tilted IMU.
    check = WheelCheck()
    assert drive(check, ramp, end=20.0, slope=0.5) is None
    assert check.bias == pytest.approx(0.5, abs=0.05)


def test_too_few_samples_say_nothing():
    check = WheelCheck()
    check.wheels(0.0, 1.0, 0.0)
    assert check.measure(0.0) is None and check.update(0.0) is None


def test_bad_tolerances_are_refused():
    with pytest.raises(ValueError):
        CrossCheck(window=0.0)
    with pytest.raises(ValueError):
        CrossCheck(persist=-1.0)
    with pytest.raises(ValueError, match='only an odom'):
        Rule('imu', '/sensors/imu/data', 'imu', max_age=0.5, cross_check=CrossCheck())


def test_the_watchdog_stops_for_it_and_a_person_clears_it():
    rule = Rule('odom', '/vehicle/odom', 'odom', max_age=0.5, cross_check=CrossCheck())
    dog = Watchdog([rule])
    odom = dog.watches['odom']
    t, dt = 0.0, 1.0 / RATE
    while t < 6.0:
        v = ramp(min(t, 1.5))                  # the wheels freeze at 1.5 s
        odom.arrived(t, (v, 0.0, 0.0, 0.0, 0.0), digest=None)
        dog.imu(t, 0.5 if 1.0 <= t < 3.0 else 0.0, 0.0)
        dog.states(t)                          # the node's tick looks each time
        t += dt
    states = {n: s for n, s, _, _ in dog.states(t)}
    assert states['odom'] == DISAGREE and dog.locked(t)
    assert 'clear it' in dog.summary(t)
    dog.clear()
    odom.arrived(t, (0.75, 0.0, 0.0, 0.0, 0.0))
    assert {n: s for n, s, _, _ in dog.states(t)}['odom'] == OK
