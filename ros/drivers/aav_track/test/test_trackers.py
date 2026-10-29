"""
Every tracker on the pretend car: a straight line, a curve, a step offset; within the limits.

The pretend car (sim_car.py) is ego's model then Gazebo's actuator model, as in pixi run sim.
Each tracker must converge, reach the end, never ask beyond full lock or the steering
rate, and (MPC) plan each tick well inside the 50 ms a 20 Hz tick allows.
"""

import math
import statistics

from aav_track.trackers import Limits, make, State
from aav_track.trackers.lqr import LQR
import pytest
from sim_car import arc, follow, LIMITS, MODEL, straight, tracker

TRACKERS = ['pure_pursuit', 'stanley', 'lqr', 'mpc']


def check_limits(run, period=0.05):
    steers = run.steers()
    assert max(abs(s) for s in steers) <= LIMITS.max_steer + 1e-9
    for a, b in zip([0.0] + steers, steers):
        assert abs(b - a) <= LIMITS.max_steer_rate * period + 1e-9


@pytest.mark.parametrize('name', TRACKERS)
@pytest.mark.parametrize('speed', [1.0, 3.0])
def test_a_straight_line_stays_on_it(name, speed):
    run = follow(tracker(name), straight(), (0.0, 0.0, 0.0), cruise=speed)
    assert run.reached
    assert max(run.cross()) < 0.01
    check_limits(run)


@pytest.mark.parametrize('name', TRACKERS)
@pytest.mark.parametrize('speed', [1.0, 3.0])
def test_a_step_offset_converges(name, speed):
    # Starting 1 m left of the line: back on it within 0.05 m by 20 m on, at either speed.
    run = follow(tracker(name), straight(), (0.0, 1.0, 0.0), cruise=speed)
    assert run.reached
    assert max(run.cross(beyond=20.0)) < 0.05
    # It gets there without swinging far past the line.
    assert min(r[6] for r in run.rows) > -0.3
    check_limits(run)


# The worst off-path in the bend, m. Stanley's has no feed-forward for the bend: the front
# axle sits on the path, so base_link cuts the corner (L^2 / 2R, about 0.15 m on an 8 m bend).
BEND = {'pure_pursuit': 0.25, 'stanley': 0.25, 'lqr': 0.1, 'mpc': 0.05}


@pytest.mark.parametrize('name', TRACKERS)
@pytest.mark.parametrize('speed', [1.0, 3.0])
def test_a_curve_stays_close(name, speed):
    run = follow(tracker(name), arc(radius=8.0), (0.0, 0.0, 0.0), cruise=speed)
    assert run.reached
    assert max(run.cross()) < BEND[name]
    check_limits(run)


def test_the_model_trackers_beat_pure_pursuit_on_the_bend():
    worst = {n: max(follow(tracker(n), arc(radius=6.0), (0, 0, 0), cruise=3.0).cross())
             for n in ('pure_pursuit', 'lqr', 'mpc')}
    assert worst['lqr'] < worst['pure_pursuit'] and worst['mpc'] < worst['pure_pursuit']


def test_lqr_gains_are_scheduled_by_speed():
    lqr = LQR(LIMITS, MODEL)
    slow, fast = lqr.gains(0.5), lqr.gains(5.0)
    assert slow[0] > 0 and slow[1] > 0
    assert not (slow == pytest.approx(fast))
    assert lqr.gains(0.0) == pytest.approx(slow)        # below the table: its first row
    assert lqr.gains(0.625) == pytest.approx((lqr.gains(0.5) + lqr.gains(0.75)) / 2)


def test_mpc_plans_well_inside_a_tick():
    # A step offset: the bounds bind, so the solver runs. Loose, for a busy laptop.
    run = follow(tracker('mpc'), straight(), (0.0, 1.0, 0.0), cruise=3.0)
    mean, worst = statistics.mean(run.step_ms), max(run.step_ms)
    print(f'\nmpc step: {mean:.2f} ms mean, {worst:.1f} ms worst, {len(run.step_ms)} steps')
    assert mean < 10.0 and worst < 50.0


def test_mpc_keeps_its_plan_within_the_bounds():
    mpc = tracker('mpc')
    run = follow(mpc, straight(), (0.0, 2.0, 0.3), cruise=1.0)
    assert run.reached
    plan = mpc.plan
    step = LIMITS.max_steer_rate * mpc.period
    assert max(abs(plan)) <= LIMITS.max_steer + 1e-9
    assert all(abs(b - a) <= step + 1e-9 for a, b in zip(plan, plan[1:]))


def test_bad_names_and_numbers_are_refused():
    with pytest.raises(ValueError, match='no tracker'):
        make('mppi', LIMITS)
    with pytest.raises(ValueError, match='model'):
        make('lqr', LIMITS)
    with pytest.raises(ValueError):
        Limits(wheelbase=1.5, max_steer=2.0, max_steer_rate=0.5)
    with pytest.raises(ValueError):
        tracker('pure_pursuit', lookahead_min=0.0)
    with pytest.raises(RuntimeError):
        tracker('stanley').step(State(0.0, 0.0, 0.0, 1.0), 0.05)


def test_no_steering_wanted_at_the_end_of_a_straight():
    trk = tracker('lqr')
    run = follow(trk, straight(10.0), (0.0, 0.0, 0.0))
    assert run.reached and abs(run.steers()[-1]) < 1e-6
    assert math.isfinite(run.rows[-1][4])
