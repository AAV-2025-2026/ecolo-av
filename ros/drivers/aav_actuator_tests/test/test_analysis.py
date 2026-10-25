"""The actuator tests' maths, on numbers worked out by hand."""

import math

from aav_actuator_tests import analysis as an
import pytest


def ramp(rate, dt=0.02, n=200, start=0.0):
    t = [i * dt for i in range(n)]
    return t, [start + rate * x for x in t]


def test_g():
    assert an.to_g(an.G) == pytest.approx(1.0)
    assert an.to_g(-1.5) == pytest.approx(-0.153, abs=1e-3)


def test_fit_line_exact_and_degenerate():
    line = an.fit_line([0, 1, 2, 3], [1, 3, 5, 7])
    assert line.slope == pytest.approx(2.0)
    assert line.intercept == pytest.approx(1.0)
    assert line.r2 == pytest.approx(1.0)
    assert an.fit_line([1, 1, 1], [1, 2, 3]) is None      # no spread in x
    assert an.fit_line([1], [1]) is None
    assert an.fit_line([0, 1, float('nan'), 2], [0, 1, 5, 2]).slope == pytest.approx(1.0)


def test_derivative_of_a_ramp():
    t, v = ramp(1.5)
    a = an.derivative(t, v, 0.3)
    assert all(x == pytest.approx(1.5) for x in a)


def test_least_squares_three_terms():
    # a = 1.5 throttle - 0.1 v - 0.02
    rows, ys = [], []
    for th in (0.1, 0.3, 0.5, 0.7):
        for v in (0.0, 1.0, 2.0):
            rows.append((th, -v, 1.0))
            ys.append(1.5 * th - 0.1 * v - 0.02)
    c = an.least_squares(rows, ys)
    assert c == pytest.approx([1.5, 0.1, -0.02])
    assert an.least_squares([(1.0, 2.0), (2.0, 4.0)], [1.0, 2.0]) is None   # collinear


def test_time_to_speeds_interpolates():
    t, v = ramp(1.0, dt=0.1, n=40)               # 1 m/s^2 from t = 0
    got = an.time_to_speeds(t, v, [1.0, 2.0, 9.0], start=0.0)
    assert got[1.0] == pytest.approx(1.0)
    assert got[2.0] == pytest.approx(2.0)
    assert got[9.0] is None


def test_stopping_constant_deceleration():
    # From 2 m/s at 1 m/s^2: 2 s and 2 m, mean deceleration 1 m/s^2.
    t = [i * 0.01 for i in range(300)]
    v = [max(0.0, 2.0 - x) for x in t]
    s = an.stopping(t, v, 0.0)
    assert s.start_speed == pytest.approx(2.0)
    assert s.time == pytest.approx(2.0, abs=0.06)
    assert s.distance == pytest.approx(2.0, abs=0.05)
    assert s.mean_decel == pytest.approx(1.0, abs=0.03)
    assert an.stopping(t, [1.0] * len(t), 0.0) is None    # never stops


def test_fit_throttle_with_a_deadband():
    # a = 1.5 th above a 0.1 deadband, nothing below, less 0.1 v.
    th = [i / 100 for i in range(60)]
    v = [0.5 + (i % 7) * 0.2 for i in range(60)]
    a = [(1.5 * t if t > 0.1 else 0.0) - 0.1 * s for t, s in zip(th, v)]
    fit = an.fit_throttle(th, v, a, drag=0.1, deadband=0.1)
    assert fit.gain == pytest.approx(1.5)
    assert an.fit_throttle([0.01] * 30, v[:30], a[:30], drag=0.1) is None   # never pushed


def test_start_throttle_is_where_it_moved():
    th = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25]
    v = [0.0, 0.0, 0.001, 0.01, 0.03, 0.06]
    assert an.start_throttle(th, v) == 0.1
    assert an.start_throttle(th, [1.0] * 6) is None     # already rolling: no answer


def test_fit_lag_finds_the_time_constant():
    t = [i * 0.02 for i in range(200)]
    cmd = [0.0 if x < 0.5 else 1.0 for x in t]
    measured = an.lag_response(t, cmd, 0.2)
    assert an.fit_lag(t, cmd, measured) == pytest.approx(0.2)
    assert an.fit_lag(t, [float('nan')] * 200, measured) is None    # the spine's NaN command


def test_swing_and_steer_lag():
    # A motor at 0.8 rad/s, then a 0.1 s lag, told to go from 0 to 0.5 rad at t = 1 s.
    t = [i * 0.02 for i in range(150)]
    cmd = [0.0 if x < 1.0 else 0.5 for x in t]
    measured = an.rate_lag_response(t, cmd, 0.8, 0.1, 0.0)
    sw = an.swing(t, cmd, measured, 1.0)
    assert sw.rate == pytest.approx(0.8, rel=0.03)
    assert sw.time_to_95 == pytest.approx(0.5 / 0.8 + 0.1, abs=0.06)
    assert an.fit_steer_lag(t, cmd, measured, 0.8) == pytest.approx(0.1, abs=0.006)


def test_fit_follower_finds_a_lag_between_differently_sampled_signals():
    # The leader at 50 Hz (the adapter), the follower at 1 kHz (Gazebo's joints), 30 ms
    # behind it: the fit reads the leader between its samples.
    t_lead = [i * 0.02 for i in range(150)]
    lead = [0.0 if x < 1.0 else min(0.5, 0.8 * (x - 1.0)) for x in t_lead]
    t_fol = [i * 0.001 for i in range(2980)]
    fine = [an.interpolate(t_lead, lead, x) for x in t_fol]
    fol = an.lag_response(t_fol, fine, 0.03)
    got = an.fit_follower(list(zip(t_lead, lead)), list(zip(t_fol, fol)))
    assert got.lag == pytest.approx(0.03, abs=0.001)
    assert got.rms_lagged < 1e-4 < got.rms_none
    assert an.fit_follower([(0.0, 0.0), (1.0, 0.0)], [(0.5, 0.0)]) is None


def test_interpolate_and_rms():
    assert an.interpolate([0.0, 1.0], [0.0, 2.0], 0.25) == 0.5
    assert an.interpolate([0.0, 1.0], [0.0, 2.0], 1.0) == 2.0
    assert math.isnan(an.interpolate([0.0, 1.0], [0.0, 2.0], 1.5))
    assert an.rms_error([1.0, 2.0, float('nan')], [0.0, 2.0, 1.0]) == pytest.approx(0.5 ** 0.5)


def test_wheel_angle_from_yaw_rate():
    # Bicycle model: yaw rate = v tan(d) / L.
    d, v, wb = 0.3, 1.2, 1.57
    r = v * math.tan(d) / wb
    assert an.wheel_angle(r, v, wb) == pytest.approx(d)
    assert math.isnan(an.wheel_angle(r, 0.0, wb))           # standing still: no answer
    assert an.angle_for_radius(wb / math.tan(d), wb) == pytest.approx(d)


def test_fit_circle():
    pts = [(3.0 + 5.0 * math.cos(a / 20), -2.0 + 5.0 * math.sin(a / 20)) for a in range(60)]
    c = an.fit_circle([p[0] for p in pts], [p[1] for p in pts])
    assert (c.cx, c.cy, c.radius) == pytest.approx((3.0, -2.0, 5.0))
    assert c.rms == pytest.approx(0.0, abs=1e-9)
    assert an.fit_circle([0, 1, 2], [0, 1, 2]) is None       # a straight line


def test_drift_in_the_start_frame():
    # Start at (1, 1) facing north; end 10 m north and 0.3 m west (= left).
    d = an.drift([1.0, 0.7], [1.0, 11.0], [math.pi / 2, math.pi / 2 + 0.05])
    assert d.along == pytest.approx(10.0)
    assert d.across == pytest.approx(0.3)
    assert d.heading == pytest.approx(0.05)


def test_gps_to_xy():
    x, y = an.gps_to_xy(45.0 + 1e-5, -75.0 + 1e-5, 45.0, -75.0)
    assert y == pytest.approx(1.112, abs=0.01)
    assert x == pytest.approx(0.786, abs=0.01)


def test_unwrap():
    assert an.unwrap([3.0, -3.0]) == pytest.approx([3.0, 2 * math.pi - 3.0])
