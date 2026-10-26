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
| fit_lag | an actuator's first-order lag (the old fit: no dead time) | 4.1, 4.3 |
| delayed, fopdt_response, fit_fopdt | a dead time, then a lag (FOPDT), with its rms | 4.1, 4.3 |
| fit_speed_response | command -> dead time -> lag -> push -> speed (wheel speed) | 4.1, 4.3 |
| swing, fit_steer_lag, fit_steer | steering speed; the linkage's lag and dead time | 3.11 |
| steer_play, backlash | the steering's play (backlash) and offset | 3.11 |
| pulse_interval, fresh_period, time_resolution | what the data can resolve | all |
| fit_follower | how far one signal lags another (Gazebo's wheels behind the model's) | 52c |
| wheel_angle, fit_circle | the real wheel angle from a circle | 4.5 |
| drift | sideways drift on a straight line | 4.7 |
"""

from __future__ import annotations

import bisect
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


# --- What the data can resolve ------------------------------------------------------------
#
# A time (a lag or a dead time) can only be read off a signal that brings fresh values
# more often than that time. A wheel speed from Hall pulses brings one per pulse: 8 holes
# on a 0.30 m wheel is a pulse every 0.118 m, so every 0.24 s at 0.5 m/s. Noise blurs it
# more: it moves a crossing by noise / slope.

def pulse_spacing(wheel_diameter: float, holes: int) -> float:
    """Return the distance the car rolls between two wheel pulses (m)."""
    return math.pi * wheel_diameter / holes


def pulse_interval(speed: float, wheel_diameter: float, holes: int) -> float:
    """Return the time between two wheel pulses at a speed (s; inf standing still)."""
    if not finite(speed) or abs(speed) < 1e-9:
        return math.inf
    return pulse_spacing(wheel_diameter, holes) / abs(speed)


def sample_period(t: Sequence[float]) -> float:
    """Return the median time between samples (s; inf for under 2)."""
    gaps = sorted(b - a for a, b in zip(t, t[1:]) if b - a > 1e-9)
    return gaps[len(gaps) // 2] if gaps else math.inf


def fresh_period(t: Sequence[float], values: Sequence[float]) -> float:
    """
    Return the median time between new values of a signal (s; inf if under 3 changes).

    A message repeating the last value brings nothing new: a Hall-pulse speed sent at
    100 Hz still changes only once per pulse, and a 50 Hz log of a 10 Hz sensor only
    every fifth row.
    """
    changes = [ti for i, ti in enumerate(t)
               if i > 0 and finite(values[i], values[i - 1]) and values[i] != values[i - 1]]
    if len(changes) < 3:
        return math.inf
    return sample_period(changes)


# A time is seen only with at least two fresh values inside it (Nyquist).
SAMPLES_PER_TIME = 2.0


def time_resolution(period: float, noise: float = 0.0, slope: float = math.inf,
                    samples: int = 1) -> float:
    """
    Return the shortest time a fit can tell apart (s).

    Two fresh values inside it at least: 2 x period, the time between fresh values of the
    slower signal. noise: the rms left over
    by the fit. slope: the fastest the response moves (units/s), so noise / slope is how
    far noise moves it in time; averaged over `samples` moving samples.
    """
    blur = 0.0
    if finite(noise, slope) and slope > 0:
        blur = noise / (slope * math.sqrt(max(1, samples)))
    return SAMPLES_PER_TIME * period + blur


def unresolved(what: str, value: float, resolution: float, signal: str) -> Optional[str]:
    """Return why a fitted time can't be trusted (it's under the resolution), or None."""
    if finite(value, resolution) and value >= resolution:
        return None
    if not finite(resolution):
        return f'{what}: {signal} never changed often enough to time anything'
    return (f'{what}: {fmt_s(value)} is under the {resolution:.3f} s that {signal} can '
            'resolve (the time between its fresh values, and its noise): not measured')


def fmt_s(value: float) -> str:
    return f'{value:.3f} s' if finite(value) else 'unknown'


# --- Dead time, then a lag (FOPDT) --------------------------------------------------------

def delayed(t: Sequence[float], cmd_t: Sequence[float], command: Sequence[float],
            dead: float) -> List[float]:
    """
    Return the command as it was `dead` s before each time in t.

    The command is held between its own samples (cmd_t, sorted), as a command is. Before
    its first sample, its first value. With dead 0 and cmd_t = t, the command itself.
    """
    out = []
    j = 0
    n = len(cmd_t)
    for ti in t:
        target = ti - dead + 1e-9
        while j + 1 < n and cmd_t[j + 1] <= target:
            j += 1
        out.append(command[j])
    return out


def held(t: Sequence[float], cmd_t: Sequence[float], command: Sequence[float],
         dead: float) -> List[float]:
    """
    Return the command acting over each interval (t[i-1], t[i]]: as it was at its start.

    The input for lag_response and rate_lag_response (which take sample i over the
    interval before it) that holds a command from its own time on, `dead` s later.
    """
    d = delayed(t, cmd_t, command, dead)
    return d[:1] + d[:-1]


def fopdt_response(t: Sequence[float], command: Sequence[float], tau: float, dead: float,
                   cmd_t: Optional[Sequence[float]] = None) -> List[float]:
    """
    Return what a dead time, then a first-order lag, make of the command, at times t.

    Each command value acts from its own time (cmd_t, default t) plus `dead`, until the
    next: exact between samples, so the dead time isn't rounded to the log's ticks, and
    true message stamps are used as they are. It starts settled.
    """
    cmd_t = t if cmd_t is None else cmd_t
    m = len(cmd_t)
    starts = [c + dead for c in cmd_t]
    j = 0
    while j + 1 < m and starts[j + 1] <= t[0]:
        j += 1

    def segment(y, u, dt):
        return u if tau <= 0.0 else u + (y - u) * math.exp(-dt / tau)

    y = command[j]
    now = t[0]
    out = [y]
    for ti in t[1:]:
        while j + 1 < m and starts[j + 1] <= ti:
            if starts[j + 1] > now:
                y = segment(y, command[j], starts[j + 1] - now)
                now = starts[j + 1]
            j += 1
        y = segment(y, command[j], ti - now)
        now = ti
        out.append(y)
    return out


# A dead time counts only if it makes the fit this much better (rms) than a lag alone:
# through the car's own integration (a speed, not a level) a short lag and a dead time
# look alike, and the fit would split one delay between them at random.
BETTER = 1.1


@dataclass(frozen=True)
class LagFit:
    """
    A dead time, then a first-order lag, fitted (fit_fopdt, fit_steer, fit_speed_response).

    The old fit (a lag alone, no dead time) is kept beside it, to compare. The rms is in
    the measured signal's units. `resolution` is the shortest time this data can resolve:
    a lag under it isn't measured, and a dead time under it is taken as none.
    """

    tau: float             # s
    dead_time: float       # s
    rms: float
    lag_only: float        # s: the old fit's lag, with no dead time (NaN: not fitted)
    rms_lag_only: float
    samples: int
    resolution: float      # s
    gain: float = 1.0      # measured units per command unit (fixed at 1 unless fitted)
    offset: float = 0.0
    at_edge: bool = False  # the best was at the edge of the search: look wider
    no_dead: float = NAN   # s: this fit's own model with no dead time (NaN: lag_only)
    rms_no_dead: float = NAN

    @property
    def fallback(self) -> Tuple[float, float]:
        """Return the lag (and its rms) of the same model with no dead time."""
        if finite(self.no_dead):
            return self.no_dead, self.rms_no_dead
        return self.lag_only, self.rms_lag_only

    @property
    def dead_resolved(self) -> bool:
        """Tell whether the dead time is measured: long enough, and clearly better than none."""
        return (self.dead_time > 0 and self.dead_time >= self.resolution
                and self.tau >= self.resolution
                and not self.fallback[1] <= BETTER * self.rms)

    @property
    def best_tau(self) -> float:
        """Return the lag to use: with the dead time if resolved, else the lag alone."""
        return self.tau if self.dead_resolved else self.fallback[0]

    @property
    def best_dead(self) -> float:
        """Return the dead time to use: 0 unless it is resolved."""
        return self.dead_time if self.dead_resolved else 0.0

    @property
    def best_rms(self) -> float:
        return self.rms if self.dead_resolved else self.fallback[1]

    def lag_problem(self, what: str, signal: str) -> Optional[str]:
        """Return why the lag can't be trusted, or None."""
        if self.at_edge:
            return (f'{what}: the best fit is at the edge of the search (dead time or lag): '
                    'not measured; drive longer, or look wider')
        return unresolved(f'{what} lag', self.best_tau, self.resolution, signal)

    def problems(self, what: str, signal: str) -> List[str]:
        """Return why each part can't be trusted: the lag, the dead time, the search."""
        out = []
        why = self.lag_problem(what, signal)
        if why:
            out.append(why)
        if self.dead_time > 0 and not self.dead_resolved:
            out.append(f'{what} dead time: {self.dead_time:.3f} s + lag {self.tau:.3f} s '
                       f"can't be told from a lag alone of {fmt_s(self.fallback[0])} with "
                       f'{signal} (both need {self.resolution:.3f} s, and a fit '
                       f'{BETTER:g} x better): the lag alone is used')
        return out


def frange(stop: float, step: float, start: float = 0.0) -> List[float]:
    """Return start, start + step, ... up to stop (both ends included), rounded."""
    n = int(math.floor((stop - start) / step + 1e-9))
    return [round(start + i * step, 9) for i in range(n + 1)]


def search_two(error, max_dead: float, max_tau: float, step: float,
               fine: float) -> Tuple[float, float, float, bool]:
    """
    Return (dead, tau, error, at_edge): the least error, on a coarse grid then a fine one.

    error(dead, tau) must be cheap to call twice with the same dead (cache inside it).
    """
    best = min(((error(d, k), d, k) for d in frange(max_dead, step)
                for k in frange(max_tau, step)))
    _, d0, k0 = best
    deads = frange(min(max_dead, d0 + step), fine, max(0.0, d0 - step))
    taus = frange(min(max_tau, k0 + step), fine, max(0.0, k0 - step))
    err, dead, tau = min((error(d, k), d, k) for d in deads for k in taus)
    edge = (dead >= max_dead - fine / 2 and max_dead > 0) or tau >= max_tau - fine / 2
    return dead, tau, err, edge


def moving_samples(t: Sequence[float], y: Sequence[float]) -> Tuple[float, int]:
    """Return the fastest slope of y (units/s) and how many samples move at 10% of it."""
    slopes = [abs(b - a) / (t2 - t1) for t1, t2, a, b in zip(t, t[1:], y, y[1:])
              if t2 - t1 > 1e-9]
    top = max(slopes, default=0.0)
    return top, sum(1 for s in slopes if s > 0.1 * top) if top > 0 else 0


def fit_fopdt(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
              cmd_t: Optional[Sequence[float]] = None, free_gain: bool = False,
              max_dead: float = 0.5, max_tau: float = 1.0, step: float = 0.04,
              fine: float = 0.005) -> Optional[LagFit]:
    """
    Fit a dead time, then a first-order lag, that best turn the command into the measured.

    The model is fopdt_response: each command acts from its own time stamp.

    measured is sampled at t; the command at cmd_t (default t: the same rows). With
    free_gain, measured ~ offset + gain x response (for a command and a measurement in
    different units: a brake command against the IMU's deceleration). Otherwise gain 1.
    None if under 10 samples, or the command never changes. The old fit (the lag alone,
    fit_lag) is kept in lag_only.
    """
    cmd_t = t if cmd_t is None else cmd_t
    cmd = [(a, b) for a, b in zip(cmd_t, command) if finite(a, b)]
    pts = [(a, b) for a, b in zip(t, measured) if finite(a, b)]
    if len(pts) < 10 or len(cmd) < 2:
        return None
    ct, cs = [c[0] for c in cmd], [c[1] for c in cmd]
    if max(cs) - min(cs) < 1e-3:
        return None
    ts, ms = [p[0] for p in pts], [p[1] for p in pts]

    def response(dead, tau):
        return fopdt_response(ts, cs, tau, dead, ct)

    def scaled(resp):
        if not free_gain:
            return 1.0, 0.0
        c = least_squares([(r, 1.0) for r in resp], ms)
        return (c[0], c[1]) if c else (NAN, NAN)

    def error(dead, tau):
        resp = response(dead, tau)
        g, o = scaled(resp)
        if not finite(g, o):
            return math.inf
        return sum((o + g * r - m) ** 2 for r, m in zip(resp, ms))

    dead, tau, err, edge = search_two(error, max_dead, max_tau, step, fine)
    if not finite(err):
        return None
    resp = response(dead, tau)
    gain, offset = scaled(resp)
    rms = math.sqrt(err / len(ts))
    # The old fit: a lag alone, no dead time (fit_lag's model, held exactly).
    lag_only = min(frange(max_tau, fine), key=lambda k: error(0.0, k))
    rms_lag_only = math.sqrt(error(0.0, lag_only) / len(ts))
    slope, moving = moving_samples(ts, [offset + gain * r for r in resp])
    period = max(fresh_period(ts, ms), sample_period(ct))
    res = time_resolution(period, rms, slope, moving)
    return LagFit(tau, dead, rms, lag_only, rms_lag_only, len(ts), res, gain, offset, edge)


# The fewest fresh wheel speeds a speed fit takes: 8 holes on a 0.30 m wheel is about
# 2.4 m of driving.
MIN_FRESH = 20


def fit_speed_response(cmd_t: Sequence[float], command: Sequence[float],
                       t: Sequence[float], speed: Sequence[float], drag: float,
                       deadband: float = 0.0, sign: float = 1.0, average: bool = True,
                       max_dead: float = 0.5, max_tau: float = 1.5, step: float = 0.04,
                       fine: float = 0.005) -> Optional[LagFit]:
    """
    Fit command -> dead time -> lag -> push -> speed against a measured (wheel) speed.

    The model is the actuator model's: u_a = lag(command, dead time later); pushing = u_a
    above the deadband; dv/dt = sign x gain x pushing - drag x v. For a given dead time
    and lag the speed is linear in the start speed and the gain, so those two are solved
    exactly; the dead time and the lag are searched.

    With `average`, each fresh speed value is compared with the model's mean speed since
    the previous fresh value: what a Hall-pulse speed (distance between pulses / time
    between them) really is. Fit only while the car moves one way (the brake can't
    reverse it). gain is in m/s^2 at full command (max_accel, max_brake); offset holds the
    fitted start speed. None if too little data (under MIN_FRESH fresh speeds).
    """
    cmd = [(a, b) for a, b in zip(cmd_t, command) if finite(a, b)]
    if len(cmd) < 10:
        return None
    grid, cs = [c[0] for c in cmd], [c[1] for c in cmd]
    if max(cs) - min(cs) < 1e-3:
        return None
    # The fresh speed values inside the command's time span. With `average`, the first
    # after a standstill is left out: it spans time since a pulse the log never saw.
    fresh: List[Tuple[float, float]] = []
    last = NAN
    for ti, vi in zip(t, speed):
        if not finite(ti, vi) or ti <= grid[0] or ti > grid[-1] or vi == last:
            continue
        if not (average and last == 0.0 and vi != 0.0):
            fresh.append((ti, vi))
        last = vi
    if len(fresh) < MIN_FRESH:
        return None
    # Where each one falls on the grid, for interpolation: computed once.
    place = []
    for ti, _ in fresh:
        j = max(1, bisect.bisect_left(grid, ti))
        w = (ti - grid[j - 1]) / (grid[j] - grid[j - 1]) if grid[j] > grid[j - 1] else 1.0
        place.append((j, w))
    vs = [v for _, v in fresh]
    d = max(drag, 0.0)

    def at(series, k):
        j, w = place[k]
        return series[j - 1] + w * (series[j] - series[j - 1])

    def features(dead, tau):
        u = [a if a > deadband else 0.0 for a in fopdt_response(grid, cs, tau, dead)]
        x, free = [0.0], [1.0]
        big_x, big_f = [0.0], [0.0]
        for i in range(1, len(grid)):
            dt = grid[i] - grid[i - 1]
            push = sign * 0.5 * (u[i] + u[i - 1])
            e = math.exp(-d * dt)
            x.append(x[-1] * e + push * ((1.0 - e) / d if d > 0 else dt))
            free.append(free[-1] * e)
            big_x.append(big_x[-1] + 0.5 * (x[-1] + x[-2]) * dt)
            big_f.append(big_f[-1] + 0.5 * (free[-1] + free[-2]) * dt)
        rows = []
        for k in range(len(fresh)):
            if average and k > 0 and vs[k] != 0.0 and vs[k - 1] != 0.0:
                span = fresh[k][0] - fresh[k - 1][0]
                rows.append(((at(big_f, k) - at(big_f, k - 1)) / span,
                             (at(big_x, k) - at(big_x, k - 1)) / span))
            else:
                rows.append((at(free, k), at(x, k)))
        return rows

    def solve(dead, tau):
        rows = features(dead, tau)
        c = least_squares(rows, vs)
        if c is None:
            return math.inf, rows, (NAN, NAN)
        err = sum((c[0] * a + c[1] * b - v) ** 2 for (a, b), v in zip(rows, vs))
        return err, rows, c

    memo: Dict[Tuple[float, float], float] = {}

    def error(dead, tau):
        if (dead, tau) not in memo:
            memo[(dead, tau)] = solve(dead, tau)[0]
        return memo[(dead, tau)]

    dead, tau, err, edge = search_two(error, max_dead, max_tau, step, fine)
    if not finite(err):
        return None
    _, rows, (v0, gain) = solve(dead, tau)
    lag_only = min(frange(max_tau, fine), key=lambda k: error(0.0, k))
    n = len(vs)
    model = [v0 * a + gain * b for a, b in rows]
    fresh_t = [f[0] for f in fresh]
    slope, moving = moving_samples(fresh_t, model)
    # Every fresh value is a change already: their median spacing is the signal's period.
    period = max(sample_period(fresh_t), sample_period(grid))
    res = time_resolution(period, math.sqrt(err / n), slope, moving)
    return LagFit(tau, dead, math.sqrt(err / n), lag_only, math.sqrt(error(0.0, lag_only) / n),
                  n, res, gain, v0, edge)


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


def backlash(values: Sequence[float], width: float, start: float = 0.0) -> List[float]:
    """Return what a linkage with `width` (rad) of play passes on: it moves only when pushed."""
    out, y = [], start
    half = width / 2.0
    for x in values:
        if x - y > half:
            y = x - half
        elif y - x > half:
            y = x + half
        out.append(y)
    return out


@dataclass(frozen=True)
class Play:
    """The steering's play and offset, from where it settles after moves each way."""

    width: float     # rad: settled from above less settled from below (backlash)
    offset: float    # rad: the mean of the two (the wheels' angle when told straight)
    holds: int


def steer_play(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
               settle: float = 0.5, min_hold: float = 1.0, still: float = 0.02
               ) -> Optional[Play]:
    """
    Return the steering's play: how far it stops short after moves up, and after moves down.

    For each hold of the command at least `min_hold` s long, the measured angle less the
    command over its last `settle` s, if it moved under `still` rad/s there. Moving up,
    play leaves the wheels half its width short (below); moving down, half above. None
    unless both ways were seen.
    """
    holds: List[Tuple[float, float, float]] = []   # (start, end, command)
    for ti, ci in zip(t, command):
        if not finite(ti, ci):
            continue
        if holds and abs(ci - holds[-1][2]) < 1e-9:
            holds[-1] = (holds[-1][0], ti, ci)
        else:
            holds.append((ti, ti, ci))
    up, down = [], []
    for prev, (start, end, c) in zip(holds, holds[1:]):
        if end - start < min_hold or abs(c - prev[2]) < 1e-6:
            continue
        window = [(ti, m) for ti, m in zip(t, measured) if end - settle <= ti <= end]
        line = fit_line([w[0] for w in window], [w[1] for w in window])
        if line is None or abs(line.slope) > still:      # still moving: not settled
            continue
        resid = mean([m - c for _, m in window])
        if finite(resid):
            (up if c > prev[2] else down).append(resid)
    if not up or not down:
        return None
    return Play(mean(down) - mean(up), 0.5 * (mean(down) + mean(up)), len(up) + len(down))


def fit_steer(t: Sequence[float], command: Sequence[float], measured: Sequence[float],
              rate: float, cmd_t: Optional[Sequence[float]] = None, max_dead: float = 0.3,
              max_tau: float = 0.5, step: float = 0.02, fine: float = 0.0025,
              play: float = 0.0, offset: float = 0.0) -> Optional[LagFit]:
    """
    Fit the steering's dead time and linkage lag, the motor's top speed (`rate`) given.

    The command (ego's angle, sampled at cmd_t, default t) goes through the dead time,
    a motor at `rate`, the play (`play` rad wide, from steer_play), then the lag, plus the
    offset. fit_steer_lag's answer (no dead time, no play) is kept in lag_only. Play left
    out shows up as a longer lag: measure it first.
    """
    cmd_t = t if cmd_t is None else cmd_t
    cmd = [(a, b) for a, b in zip(cmd_t, command) if finite(a, b)]
    pts = [(a, b) for a, b in zip(t, measured) if finite(a, b)]
    if len(pts) < 10 or len(cmd) < 2 or not (finite(rate) and rate > 0):
        return None
    ct, cs = [c[0] for c in cmd], [c[1] for c in cmd]
    if max(cs) - min(cs) < 1e-3:
        return None
    ts, ms = [p[0] for p in pts], [p[1] for p in pts]
    cache: Dict[float, List[float]] = {}

    start = ms[0] - offset

    def response(dead, tau):
        if dead not in cache:
            motor = rate_lag_response(ts, held(ts, ct, cs, dead), rate, 0.0, start)
            cache[dead] = backlash(motor, play, start) if play > 0 else motor
        return [offset + y for y in lag_response(ts, cache[dead], tau)]

    def error(dead, tau):
        return sum((a - b) ** 2 for a, b in zip(response(dead, tau), ms))

    dead, tau, err, edge = search_two(error, max_dead, max_tau, step, fine)
    n = len(ts)
    best = response(dead, tau)
    # The old fit: fit_steer_lag's model (no dead time, no play), held the same way.
    lag_only = min(frange(max_tau, fine), key=lambda k: rms_error(
        rate_lag_response(ts, held(ts, ct, cs, 0.0), rate, k, ms[0]), ms))
    rms_old = rms_error(rate_lag_response(ts, held(ts, ct, cs, 0.0), rate, lag_only, ms[0]), ms)
    slope, moving = moving_samples(ts, best)
    period = max(fresh_period(ts, ms), sample_period(ct))
    res = time_resolution(period, math.sqrt(err / n), slope, moving)
    no_dead = min(frange(max_tau, fine), key=lambda k: error(0.0, k))
    return LagFit(tau, dead, math.sqrt(err / n), lag_only, rms_old, n, res, 1.0, offset, edge,
                  no_dead, math.sqrt(error(0.0, no_dead) / n))


def interpolate(ts: Sequence[float], values: Sequence[float], t: float) -> float:
    """Return values at time t, linearly between samples (NaN outside them); ts sorted."""
    i = bisect.bisect_left(ts, t)
    if i < len(ts) and ts[i] == t:
        return values[i]
    if i == 0 or i >= len(ts):
        return NAN
    w = (t - ts[i - 1]) / (ts[i] - ts[i - 1])
    return values[i - 1] + w * (values[i] - values[i - 1])


def rms_error(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the root mean square of a - b over the finite pairs (NaN if none)."""
    d = [(x - y) ** 2 for x, y in zip(a, b) if finite(x, y)]
    return math.sqrt(sum(d) / len(d)) if d else NAN


@dataclass(frozen=True)
class Follower:
    """How a signal follows a leader, as a first-order lag (fit_follower)."""

    lag: float           # s
    rms_lagged: float    # rms off with that lag
    rms_none: float      # rms off with none
    samples: int


def fit_follower(leader: Sequence[Tuple[float, float]], follower: Sequence[Tuple[float, float]],
                 taus: Sequence[float] = tuple(i * 0.001 for i in range(301))
                 ) -> Optional[Follower]:
    """
    Fit the first-order lag that best turns the leader into the follower.

    Both are [(t, value)], sampled at any times: the leader is read between its samples
    linearly at each of the follower's. None if fewer than 10 overlap, or the leader
    never moves. For Gazebo's wheels against the actuator model's angle (TODO 52c).
    """
    lead = sorted(leader)
    lt, lv = [t for t, _ in lead], [v for _, v in lead]
    pts = [(t, interpolate(lt, lv, t), v) for t, v in sorted(follower)]
    pts = [p for p in pts if finite(p[1], p[2])]
    if len(pts) < 10:
        return None
    ts, cmd, got = zip(*pts)
    lag = fit_lag(ts, cmd, got, taus)
    if lag is None:
        return None
    return Follower(lag, rms_error(lag_response(ts, cmd, lag), got), rms_error(cmd, got),
                    len(pts))


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
