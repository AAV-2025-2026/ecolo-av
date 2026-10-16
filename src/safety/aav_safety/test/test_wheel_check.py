import math
import random

from aav_safety.watchdog import DISAGREE, OK, Rule, Watchdog
from aav_safety.wheel_check import CrossCheck, trapezoid, WheelCheck
import pytest

RATE = 50.0     # Hz, the wheels and the IMU both
GPS_RATE = 5.0  # Hz, as Gazebo's
HERE = (45.3860, -75.6960)
METRES_PER_DEGREE = math.radians(1.0) * 6371000.0


def drive(check, speed, turn=lambda t: 0.0, start=0.0, end=10.0, frozen_at=None, slope=0.0,
          noise=0.0, rng=None, gps_noise=None, jump_at=None):
    """
    Feed check a car whose speed is speed(t); return when it first latched, or None.

    frozen_at: from then on the wheels repeat their speed and turn rate. slope: m/s^2 of
    gravity the IMU's forward reading adds. gps_noise: m, 1 sigma, of GPS fixes at
    GPS_RATE (None: no GPS). jump_at: from then on the fixes are 20 m further north.
    """
    dt, t, held = 1.0 / RATE, start, None
    x = y = h = 0.0
    if rng is None:
        # A real IMU's noise never repeats: a noiseless one would count as frozen.
        rng, noise = random.Random(0), 0.01
    next_fix = start
    while t <= end:
        accel = (speed(t + 1e-3) - speed(t - 1e-3)) / 2e-3
        if frozen_at is not None and t >= frozen_at and held is None:
            held = (speed(t), turn(t))
        v, w = held if held is not None else (speed(t), turn(t))
        check.wheels(t, v, w)
        a = accel + slope + rng.gauss(0.0, noise)
        check.imu(t, a, turn(t) + rng.gauss(0.0, noise / 10))
        h += turn(t) * dt
        x, y = x + speed(t) * math.cos(h) * dt, y + speed(t) * math.sin(h) * dt
        if gps_noise is not None and t >= next_fix:
            north = y + rng.gauss(0.0, gps_noise) + (20.0 if jump_at and t >= jump_at else 0)
            east = x + rng.gauss(0.0, gps_noise)
            lat = HERE[0] + north / METRES_PER_DEGREE
            lon = HERE[1] + east / (METRES_PER_DEGREE * math.cos(math.radians(HERE[0])))
            check.gps(t, lat, lon)
            next_fix += 1.0 / GPS_RATE
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


def test_normal_driving_with_a_noisy_gps_never_latches():
    for seed in range(5):
        rng = random.Random(seed)
        check = WheelCheck()
        assert drive(check, lambda t: ramp(t, top=0.8), turn=lambda t: 0.3 * math.sin(t / 3),
                     end=60.0, noise=0.2, rng=rng, gps_noise=0.5) is None, seed
        assert check.worst[2] < 0.25, seed


def test_wheels_frozen_at_the_wrong_speed_latch_from_the_gps():
    # Frozen at 0.5 m/s while the car speeds up gently to 1: too gently for the IMU's
    # window, which sees only 0.15 m/s of change.
    def speed(t):
        return 0.5 if t < 10.0 else min(1.0, 0.5 + (t - 10.0) * 0.1)
    for seed in range(5):
        rng = random.Random(seed)
        check = WheelCheck()
        t = drive(check, speed, frozen_at=9.0, end=40.0, rng=rng, gps_noise=0.5)
        assert t is not None and t < 22.0, seed
        assert 'GPS' in check.update(t)


def test_a_frozen_imu_or_gps_is_not_blamed_on_the_wheels():
    check = WheelCheck()
    for i in range(200):                        # 4 s: the IMU frozen, the car speeding up
        t = i / RATE
        check.wheels(t, 0.5 * t, 0.0)
        check.imu(t, 0.0, 0.0)
        check.gps(t, *HERE)
        assert check.update(t) is None
    assert check.gaps is None


def test_a_gps_jump_is_the_gps_watchs_business_not_the_wheels():
    rng = random.Random(4)
    check = WheelCheck()
    assert drive(check, lambda t: ramp(t, top=0.8), end=30.0, rng=rng, gps_noise=0.5,
                 jump_at=15.0) is None


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
        jitter = 1e-3 * math.sin(50.0 * t)             # a real IMU's noise
        dog.imu(t, (0.5 if 1.0 <= t < 3.0 else 0.0) + jitter, jitter)
        dog.states(t)                          # the node's tick looks each time
        t += dt
    states = {n: s for n, s, _, _ in dog.states(t)}
    assert states['odom'] == DISAGREE and dog.locked(t)
    assert 'clear it' in dog.summary(t)
    dog.clear()
    odom.arrived(t, (0.75, 0.0, 0.0, 0.0, 0.0))
    assert {n: s for n, s, _, _ in dog.states(t)}['odom'] == OK


def test_a_hole_in_the_wheels_or_the_imu_is_not_added_up_across():
    # The wheels go quiet for 2 s while the car keeps driving (odom STALE: the watchdog's
    # own business), then come back: no gap may come of the hole.
    rng = random.Random(5)
    check, x, dt = WheelCheck(), 0.0, 1.0 / RATE
    for i in range(int(20 * RATE)):
        t = i * dt
        x += 1.0 * dt
        if not 5.0 <= t < 7.0:
            check.wheels(t, 1.0, 0.0)
        if not 12.0 <= t < 13.0:
            check.imu(t, rng.gauss(0.0, 0.05), rng.gauss(0.0, 0.005))
        if i % int(RATE / GPS_RATE) == 0:
            east = x + rng.gauss(0.0, 0.5)
            check.gps(t, HERE[0] + rng.gauss(0.0, 0.5) / METRES_PER_DEGREE,
                      HERE[1] + east / (METRES_PER_DEGREE * math.cos(math.radians(HERE[0]))))
        assert check.update(t) is None, t
