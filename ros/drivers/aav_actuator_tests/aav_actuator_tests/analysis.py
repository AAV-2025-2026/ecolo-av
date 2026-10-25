"""
The actuator tests' maths: from logged samples to the numbers for vehicle.yaml.

No ROS here, and no numpy: the tests run with plain Python anywhere. Units are SI
(m, s, rad, m/s, m/s^2); g is only for printing. Positive steering turns left.

| Function | Gives | Used by test |
|---|---|---|
| derivative, moving_average | acceleration from speed; a smoothed IMU | 4.1-4.4 |
| first_crossing, time_to_speeds | when a speed is first reached | 4.1 |
| stopping | stopping distance, time and mean deceleration | 4.3 |
| fit_line, least_squares, fit_throttle | throttle and brake maps, drag | 4.2-4.4, 3.10 |
| fit_lag | an actuator's first-order lag | 4.1, 4.3 |
| swing, fit_steer_lag | steering speed from a step; the linkage's lag | 3.11 |
| wheel_angle, fit_circle | the real wheel angle from a circle | 4.5 |
| drift | sideways drift on a straight line | 4.7 |
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple

G = 9.80665          # m/s^2 in one g
STOPPED = 0.05       # m/s: slower counts as stopped (the spine's own threshold)
NAN = float('nan')


def to_g(accel: float) -> float:
    """Return an acceleration in g."""
    return accel / G


def finite(*values: float) -> bool:
    return all(v is not None and math.isfinite(v) for v in values)


def mean(values: Sequence[float]) -> float:
    """Return the mean of the finite values, or NaN if there are none."""
    vals = [v for v in values if finite(v)]
    return sum(vals) / len(vals) if vals else NAN


def window_indices(t: Sequence[float], i: int, half: float) -> Tuple[int, int]:
    """Return the first and last index within `half` seconds of sample i (t sorted)."""
    lo = i
    while lo > 0 and t[i] - t[lo - 1] <= half:
        lo -= 1
    hi = i
    while hi < len(t) - 1 and t[hi + 1] - t[i] <= half:
        hi += 1
    return lo, hi


def moving_average(t: Sequence[float], y: Sequence[float], window: float) -> List[float]:
    """Smooth y with a centred moving average `window` seconds wide."""
    out = []
    for i in range(len(t)):
        lo, hi = window_indices(t, i, window / 2.0)
        out.append(mean(y[lo:hi + 1]))
    return out


@dataclass(frozen=True)
class Line:
    """y = slope * x + intercept, and how well it fits (r2: 1 is perfect)."""

    slope: float
    intercept: float
    r2: float
    n: int

    def at(self, x: float) -> float:
        return self.slope * x + self.intercept


def fit_line(x: Sequence[float], y: Sequence[float]) -> Optional[Line]:
    """Least-squares straight line through the finite (x, y) pairs; None if under 2 or flat."""
    pairs = [(a, b) for a, b in zip(x, y) if finite(a, b)]
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    sxx = sum((a - mx) ** 2 for a, _ in pairs)
    if sxx <= 1e-12:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in pairs)
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((b - my) ** 2 for _, b in pairs)
    resid = sum((b - (slope * a + intercept)) ** 2 for a, b in pairs)
    r2 = 1.0 - resid / syy if syy > 1e-12 else 1.0
    return Line(slope, intercept, r2, n)


def derivative(t: Sequence[float], y: Sequence[float], window: float) -> List[float]:
    """dy/dt at each sample: the slope of a line fitted over a centred window."""
    out = []
    for i in range(len(t)):
        lo, hi = window_indices(t, i, window / 2.0)
        line = fit_line(t[lo:hi + 1], y[lo:hi + 1])
        out.append(line.slope if line else NAN)
    return out


def least_squares(rows: Sequence[Sequence[float]], ys: Sequence[float]) -> Optional[List[float]]:
    """
    Solve rows @ c ~= ys for c in the least-squares sense (normal equations).

    Returns None when the columns don't vary independently (a singular system).
    """
    data = [(r, y) for r, y in zip(rows, ys) if finite(y, *r)]
    if not data:
        return None
    k = len(data[0][0])
    if len(data) < k:
        return None
    a = [[sum(r[i] * r[j] for r, _ in data) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * y for r, y in data) for i in range(k)]
    # Gaussian elimination with partial pivoting.
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(a[r][col]))
        scale = max(abs(a[i][i]) for i in range(k)) or 1.0
        if abs(a[pivot][col]) < 1e-12 * scale:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        b[col], b[pivot] = b[pivot], b[col]
        for r in range(col + 1, k):
            f = a[r][col] / a[col][col]
            a[r] = [x - f * p for x, p in zip(a[r], a[col])]
            b[r] -= f * b[col]
    c = [0.0] * k
    for i in reversed(range(k)):
        c[i] = (b[i] - sum(a[i][j] * c[j] for j in range(i + 1, k))) / a[i][i]
    return c


@dataclass(frozen=True)
class Throttle:
    """
    The throttle's map, as the actuator model has it.

    a = gain x throttle above the deadband, nothing below it, less drag x speed.
    """

    gain: float      # m/s^2 at full throttle (vehicle.yaml max_accel)
    deadband: float  # throttle level below which it doesn't push
    drag: float      # 1/s
    n: int           # samples used


def fit_throttle(throttle: Sequence[float], speed: Sequence[float], accel: Sequence[float],
                 drag: float, deadband: float = 0.0) -> Optional[Throttle]:
    """
    Fit the throttle's gain to samples taken with the brake off.

    The drag (1/s) and the deadband (see start_throttle) are given. Below the deadband the
    car only coasts.
    """
    pts = [(t, v, a) for t, v, a in zip(throttle, speed, accel) if finite(t, v, a) and t >= 0]
    if len(pts) < 20 or max(p[0] for p in pts) < 0.05:
        return None
    push = [p[0] if p[0] > deadband else 0.0 for p in pts]
    c = least_squares([(u,) for u in push], [p[2] + drag * p[1] for p in pts])
    if c is None or c[0] <= 0:
        return None
    return Throttle(c[0], deadband, drag, len(pts))


def start_throttle(throttle: Sequence[float], speed: Sequence[float],
                   moving: float = 0.02, still: float = 0.002) -> Optional[float]:
    """
    Return the throttle level where a car that stood still started to move.

    That's the level at the last moment it stood still (under `still` m/s) before it drove
    off (past `moving` m/s): the deadband, as docs/tests.md 4.4 puts it, "the throttle
    where it starts to move". None if it never started from still.
    """
    last_still = None
    for t, v in zip(throttle, speed):
        if not finite(t, v):
            continue
        if abs(v) < still:
            last_still = t
        elif abs(v) > moving and last_still is not None:
            return last_still
    return None


def first_crossing(t: Sequence[float], y: Sequence[float], level: float,
                   start: float = -math.inf) -> Optional[float]:
    """Return the first time at or after `start` that y rises to `level`, or None."""
    prev = None
    for ti, yi in zip(t, y):
        if ti < start or not finite(yi):
            continue
        if yi >= level:
            if prev is None or prev[1] >= level:
                return ti
            (t0, y0) = prev
            return t0 + (ti - t0) * (level - y0) / (yi - y0)
        prev = (ti, yi)
    return None


def time_to_speeds(t: Sequence[float], speed: Sequence[float], targets: Sequence[float],
                   start: float) -> Dict[float, Optional[float]]:
    """Seconds from `start` until each target speed is first reached (None: never)."""
    out = {}
    for target in targets:
        hit = first_crossing(t, speed, target, start)
        out[target] = None if hit is None else hit - start
    return out


@dataclass(frozen=True)
class Stop:
    """A stop: from the moment it was asked for, until the car stood still."""

    start_speed: float   # m/s when the stop was asked for
    distance: float      # m travelled meanwhile
    time: float          # s
    mean_decel: float    # m/s^2: start_speed^2 / (2 distance), positive


def stopping(t: Sequence[float], speed: Sequence[float], start: float) -> Optional[Stop]:
    """Integrate the speed from `start` until it falls below STOPPED; None if it never does."""
    idx = [i for i, ti in enumerate(t) if ti >= start and finite(speed[i])]
    if not idx:
        return None
    v0 = abs(speed[idx[0]])
    distance = 0.0
    for a, b in zip(idx, idx[1:]):
        distance += 0.5 * (abs(speed[a]) + abs(speed[b])) * (t[b] - t[a])
        if abs(speed[b]) < STOPPED:
            decel = v0 * v0 / (2.0 * distance) if distance > 1e-6 else NAN
            return Stop(v0, distance, t[b] - start, decel)
    return None


def lag_response(t: Sequence[float], command: Sequence[float], tau: float) -> List[float]:
    """Return what a first-order lag (time constant tau) makes of the command."""
    out = []
    value = None
    prev_t = None
    for ti, ci in zip(t, command):
        if value is None:
            value = ci
        elif tau <= 0.0:
            value = ci
        else:
            value += (ci - value) * (1.0 - math.exp(-(ti - prev_t) / tau))
        out.append(value)
        prev_t = ti
    return out


def fit_lag(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
            taus: Sequence[float] = tuple(i * 0.01 for i in range(101))) -> Optional[float]:
    """
    Return the time constant (s) whose first-order lag best turns command into measured.

    None if the command is unknown (NaN, as for the spine's throttle) or never changes.
    """
    pairs = [(a, b, c) for a, b, c in zip(t, command, measured) if finite(b, c)]
    if len(pairs) < 10:
        return None
    ts, cs, ms = zip(*pairs)
    if max(cs) - min(cs) < 1e-3:
        return None

    def error(tau):
        return sum((r - m) ** 2 for r, m in zip(lag_response(ts, cs, tau), ms))
    return min(taus, key=error)


@dataclass(frozen=True)
class Swing:
    """One steering step: from where it was to where it was told, as measured."""

    start: float         # rad, before the step
    target: float        # rad, the command
    time_to_95: float    # s from the command to 95% of the way
    rate: float          # rad/s: the slope between 40% and 80% of the way


def swing(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
          t_command: float) -> Optional[Swing]:
    """
    Measure one steering step that was commanded at t_command.

    `command` is what the actuator was told (ego's angle, which ego ramps), `measured` its
    angle. The rate is the motor's top speed (fit_steer_lag finds the linkage's lag).
    """
    before = [m for ti, m in zip(t, measured) if ti <= t_command and finite(m)]
    after = [(ti, c, m) for ti, c, m in zip(t, command, measured)
             if ti >= t_command and finite(c, m)]
    if not before or len(after) < 5:
        return None
    start = mean(before[-5:])
    target = after[-1][1]
    span = target - start
    if abs(span) < 0.02:
        return None
    sign = 1.0 if span > 0 else -1.0
    ts = [a[0] for a in after]
    progress = [sign * (a[2] - start) / abs(span) for a in after]
    # From 40%: by then the linkage's lag has caught up with the motor's steady speed.
    t40 = first_crossing(ts, progress, 0.4)
    t80 = first_crossing(ts, progress, 0.8)
    t95 = first_crossing(ts, progress, 0.95)
    if None in (t40, t80, t95) or t80 <= t40:
        return None
    rate = 0.4 * abs(span) / (t80 - t40)
    return Swing(start, target, t95 - t_command, rate)


def rate_lag_response(t: Sequence[float], command: Sequence[float], rate: float,
                      tau: float, start: float) -> List[float]:
    """Return what a motor with a top speed (rad/s), then a first-order lag, makes of command."""
    motor = out = start
    prev = None
    result = []
    for ti, ci in zip(t, command):
        dt = 0.0 if prev is None else ti - prev
        prev = ti
        step = rate * dt
        motor += max(-step, min(step, ci - motor))
        out = motor if tau <= 0.0 else out + (motor - out) * (1.0 - math.exp(-dt / tau))
        result.append(out)
    return result


def fit_steer_lag(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
                  rate: float,
                  taus: Sequence[float] = tuple(i * 0.005 for i in range(101))) -> Optional[float]:
    """
    Return the linkage's lag (s).

    That's the tau for which a motor at `rate`, then that lag, best turns the command into
    the measured angle. Better than reading it off one swing, whose middle a sampled log
    can only place to within a tick.
    """
    pts = [(a, b, c) for a, b, c in zip(t, command, measured) if finite(a, b, c)]
    if len(pts) < 10 or not (finite(rate) and rate > 0):
        return None
    ts, cs, ms = zip(*pts)
    if max(cs) - min(cs) < 1e-3:
        return None

    def error(tau):
        sim = rate_lag_response(ts, cs, rate, tau, ms[0])
        return sum((a - b) ** 2 for a, b in zip(sim, ms))
    return min(taus, key=error)


def wheel_angle(yaw_rate: float, speed: float, wheelbase: float) -> float:
    """Return the bicycle model's wheel angle for a yaw rate at a speed (NaN if still)."""
    if not finite(yaw_rate, speed) or abs(speed) < 0.1:
        return NAN
    return math.atan(wheelbase * yaw_rate / speed)


def angle_for_radius(radius: float, wheelbase: float) -> float:
    """Return the wheel angle that drives base_link round a circle of this radius."""
    return math.atan(wheelbase / radius) if radius > 0 else NAN


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    radius: float
    rms: float   # m: how far the points sit from the circle


def fit_circle(xs: Sequence[float], ys: Sequence[float]) -> Optional[Circle]:
    """Least-squares circle through points (the Kasa fit); None for under 3 or a line."""
    pts = [(x, y) for x, y in zip(xs, ys) if finite(x, y)]
    if len(pts) < 3:
        return None
    # Centre the points first: it keeps the normal equations well conditioned.
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    rows = [(x - mx, y - my, 1.0) for x, y in pts]
    rhs = [-((x - mx) ** 2 + (y - my) ** 2) for x, y in pts]
    c = least_squares(rows, rhs)
    if c is None:
        return None
    d, e, f = c
    cx, cy = -d / 2.0, -e / 2.0
    r2 = cx * cx + cy * cy - f
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    rms = math.sqrt(sum((math.hypot(x - mx - cx, y - my - cy) - r) ** 2 for x, y in pts)
                    / len(pts))
    return Circle(cx + mx, cy + my, r, rms)


@dataclass(frozen=True)
class Drift:
    along: float    # m travelled along the start heading
    across: float   # m to the left (+) of the start heading
    heading: float  # rad turned, + left


def drift(xs: Sequence[float], ys: Sequence[float], yaws: Sequence[float]) -> Optional[Drift]:
    """Where the end point lies in the frame of the start pose."""
    pts = [(x, y, w) for x, y, w in zip(xs, ys, yaws) if finite(x, y, w)]
    if len(pts) < 2:
        return None
    (x0, y0, w0), (x1, y1, w1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    c, s = math.cos(w0), math.sin(w0)
    turned = math.atan2(math.sin(w1 - w0), math.cos(w1 - w0))
    return Drift(c * dx + s * dy, -s * dx + c * dy, turned)


def gps_to_xy(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Metres east and north of (lat0, lon0): flat-earth, fine over a parking lot."""
    r = 6371000.0
    x = math.radians(lon - lon0) * r * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * r
    return x, y


def unwrap(angles: Sequence[float]) -> List[float]:
    """Remove the 2 pi jumps from a sequence of angles."""
    out: List[float] = []
    for a in angles:
        if not out or not finite(a):
            out.append(a)
            continue
        prev = out[-1] if finite(out[-1]) else a
        out.append(prev + math.atan2(math.sin(a - prev), math.cos(a - prev)))
    return out
