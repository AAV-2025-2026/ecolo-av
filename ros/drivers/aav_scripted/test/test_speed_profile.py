from aav_scripted.speed_profile import ACCELERATE, DECELERATE, HOLD, SpeedProfile, STOPPED
import pytest


def run(profile, dt=0.02, speed_for_distance=True, limit=10_000):
    distance, speeds = 0.0, []
    for _ in range(limit):
        v = profile.step(dt, distance)
        speeds.append(v)
        if speed_for_distance:
            distance += abs(v) * dt
        if profile.phase == STOPPED:
            return speeds, distance
    raise AssertionError('profile never stopped')


def test_time_profile_shape():
    p = SpeedProfile(1.0, 0.5, 1.0, hold_time=2.0, hold_distance=0.0)
    speeds, distance = run(p)
    assert max(speeds) == pytest.approx(1.0)
    assert speeds[-1] == 0.0
    # 1 m speeding up + 2 m holding + 0.5 m slowing down
    assert distance == pytest.approx(3.5, abs=0.05)


def test_distance_profile_holds_for_the_distance():
    p = SpeedProfile(2.0, 1.0, 1.0, hold_time=0.0, hold_distance=10.0)
    _, distance = run(p)
    assert distance == pytest.approx(2.0 + 10.0 + 2.0, abs=0.1)


def test_reverse_profile():
    p = SpeedProfile(-0.5, 0.5, 0.5, hold_time=1.0, hold_distance=0.0)
    speeds, _ = run(p)
    assert min(speeds) == pytest.approx(-0.5)


def test_cancel_slows_down():
    p = SpeedProfile(1.0, 1.0, 2.0, hold_time=100.0, hold_distance=0.0)
    for _ in range(100):
        p.step(0.02)
    assert p.phase == HOLD
    p.cancel()
    assert p.phase == DECELERATE
    speeds, _ = run(p)
    assert speeds[-1] == 0.0


def test_phases_in_order():
    p = SpeedProfile(1.0, 1.0, 1.0, hold_time=0.1, hold_distance=0.0)
    seen = []
    while p.phase != STOPPED:
        if not seen or seen[-1] != p.phase:
            seen.append(p.phase)
        p.step(0.05)
    assert seen == [ACCELERATE, HOLD, DECELERATE]


def test_bad_goal_is_rejected():
    with pytest.raises(ValueError):
        SpeedProfile(1.0, 0.0, 1.0, 1.0, 0.0)
