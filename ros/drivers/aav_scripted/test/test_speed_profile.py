from aav_scripted.speed_profile import (
    ACCELERATE, DECELERATE, goal_problem, HOLD, SpeedProfile, stop_reason, STOPPED)
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


def test_stop_is_at_once():
    p = SpeedProfile(1.0, 1.0, 1.0, hold_time=10.0, hold_distance=0.0)
    for _ in range(100):
        p.step(0.02)
    p.stop()
    assert p.phase == STOPPED
    assert p.step(0.02) == 0.0


@pytest.mark.parametrize('goal', [
    (1.0, 0.5, 1.0, -1.0, 0.0),             # negative hold_time: it used to wedge the server
    (float('nan'), 0.5, 1.0, 1.0, 0.0),     # NaN passed the max_speed check
    (1.0, 0.5, 1.0, float('inf'), 0.0),
    (3.0, 0.5, 1.0, 1.0, 0.0),              # above max_speed
    (1.0, 0.0, 1.0, 1.0, 0.0),
    (1.0, 0.5, 1.0, 0.0, -2.0),
])
def test_goal_problem_refuses(goal):
    assert goal_problem(*goal, max_speed=2.0) is not None
    # Every goal it refuses would also have failed in SpeedProfile, or run wrongly.


@pytest.mark.parametrize('goal', [
    (1.0, 0.5, 1.0, 2.0, 0.0),
    (-0.5, 0.5, 0.5, 1.0, 0.0),
    (1.0, 0.5, 1.0, -1.0, 5.0),             # hold_time is unused with a distance
    (0.0, 0.5, 1.0, 0.0, 0.0),
])
def test_goal_problem_accepts(goal):
    assert goal_problem(*goal, max_speed=2.0) is None
    SpeedProfile(*goal)                     # and the profile takes it


def test_stop_reason():
    assert stop_reason(False, False, needs_odom=True, odom_fresh=True) is None
    assert stop_reason(False, False, needs_odom=False, odom_fresh=False) is None
    assert stop_reason(True, False, needs_odom=False, odom_fresh=True) == 'e-stop'
    taken = stop_reason(False, True, needs_odom=False, odom_fresh=True)
    assert taken == 'someone else is driving'
    stale = stop_reason(False, False, needs_odom=True, odom_fresh=False)
    assert stale == 'odometry stopped arriving'
