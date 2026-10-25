"""
From one run's log to a report: a table, and the vehicle.yaml lines to paste.

No ROS here. A run's log is a list of rows (dicts, the CSV's columns below), so a report
can be made again later from the CSV alone: `actuator_test --analyse <run folder>`.
Nothing here writes vehicle.yaml: it only prints the lines, for a person to check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from aav_actuator_tests import analysis as an
from aav_actuator_tests.analysis import finite, mean, NAN

# The log's columns. Units: s, m/s, rad, rad/s, m/s^2, m; throttle and brake 0..1.
COLUMNS = (
    't', 'phase',
    'cmd_speed', 'cmd_steer',             # what this test asked for (before ego)
    'speed',                              # /vehicle/odom: measured (wheel) speed
    'steer_cmd', 'steer',                 # /vehicle/steering: ego's angle, the measured one
    'throttle_cmd', 'throttle',           # /vehicle/throttle
    'brake_cmd', 'brake',                 # /vehicle/brake
    'wheel_fl', 'wheel_fr', 'wheel_rl', 'wheel_rr',   # /vehicle/wheels
    'ax', 'ay', 'gz',                     # IMU: forward and left acceleration, yaw rate
    'heading', 'distance',                # the yaw rate and the speed, added up
    'x', 'y', 'yaw',                      # /localization/odom/local
    'lat', 'lon',                         # /sensors/gps/fix
    'manual_steer',                       # an angle a person typed (stands, no sensor)
)


@dataclass(frozen=True)
class Context:
    """What the analysis needs to know about the car."""

    wheelbase: float = 1.57
    max_steering: float = 0.5
    gps_x: float = 0.0                         # m: the antenna ahead of base_link
    current: Mapping[str, float] = field(default_factory=dict)  # vehicle.yaml's values now


@dataclass(frozen=True)
class Row:
    what: str
    value: str
    unit: str = ''
    now: str = ''      # vehicle.yaml's value today, to compare
    note: str = ''


@dataclass
class Report:
    title: str
    rows: List[Row] = field(default_factory=list)
    yaml: Dict[str, Tuple[float, str]] = field(default_factory=dict)  # 'actuators.x' -> ...
    notes: List[str] = field(default_factory=list)

    def add(self, what, value, unit='', key=None, ctx=None, note='', digits=3):
        now = ''
        if key and ctx is not None and key in ctx.current:
            now = f'{ctx.current[key]:g}'
        self.rows.append(Row(what, fmt(value, digits), unit, now, note))

    def suggest(self, key: str, value: float, comment: str):
        if finite(value):
            self.yaml[key] = (value, comment)


def fmt(value, digits=3) -> str:
    if value is None:
        return '-'
    if isinstance(value, str):
        return value
    if not finite(value):
        return '-'
    return f'{value:.{digits}f}'


def col(rows: Sequence[Mapping], name: str) -> List[float]:
    out = []
    for r in rows:
        v = r.get(name, NAN)
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(NAN)
    return out


def phases(rows: Sequence[Mapping]) -> List[Tuple[str, List[Mapping]]]:
    """Return the rows cut into runs of the same phase, in order."""
    out: List[Tuple[str, List[Mapping]]] = []
    for r in rows:
        if not out or out[-1][0] != r['phase']:
            out.append((r['phase'], []))
        out[-1][1].append(r)
    return out


def tail(rows: Sequence[Mapping], seconds: float) -> List[Mapping]:
    """Return the rows in the last `seconds` of a phase."""
    if not rows:
        return []
    end = float(rows[-1]['t'])
    return [r for r in rows if float(r['t']) >= end - seconds]


def settled_angle(rows: Sequence[Mapping], seconds: float = 1.0) -> float:
    """Return the angle at the end of a phase: a person's reading, else the sensor's."""
    typed = [v for v in col(rows, 'manual_steer') if finite(v)]
    if typed:
        return typed[-1]
    return mean(col(tail(rows, seconds), 'steer'))


def accel_from_speed(rows: Sequence[Mapping]) -> List[float]:
    return an.derivative(col(rows, 't'), col(rows, 'speed'), 0.3)


def has(rows: Sequence[Mapping], name: str) -> bool:
    return any(finite(v) for v in col(rows, name))


# --- stage 3: the steering ---------------------------------------------------------------

def steer_sweep(rows, ctx: Context) -> Report:
    rep = Report('3.10 steering sweep')
    points = []
    for name, rs in phases(rows):
        if name.startswith('sweep '):
            points.append((float(rs[-1]['cmd_steer']), settled_angle(rs)))
    if not any(finite(m) for _, m in points):
        rep.notes.append('no measured angle: /vehicle/steering is silent or NaN. On the car '
                         'today (the 2025-26 ESP32), measure with a protractor: the test asks '
                         'at each step')
        return rep
    for c, m in points:
        rep.add(f'command {c:+.3f} rad', m, 'rad', note=f'{math.degrees(m):+.1f} deg'
                if finite(m) else '')
    line = an.fit_line([c for c, _ in points], [m for _, m in points])
    if line:
        rep.add('gain: measured / command', line.slope, '', note=f'r2 {line.r2:.4f}')
        rep.add('offset at command 0', line.intercept, 'rad', 'actuators.steer_offset', ctx)
        rep.suggest('actuators.steer_offset', line.intercept, "test 3.10: the sweep's line")
    # The same command, reached from both sides: the gap is the slack (deadband, backlash).
    seen: Dict[float, List[float]] = {}
    for c, m in points:
        seen.setdefault(round(c, 4), []).append(m)
    gaps = [max(v) - min(v) for v in seen.values() if len(v) > 1 and all(map(finite, v))]
    if gaps:
        rep.add('hysteresis (largest gap, same command)', max(gaps), 'rad')
    lefts = [m for c, m in points if c >= ctx.max_steering - 1e-6]
    rights = [m for c, m in points if c <= -ctx.max_steering + 1e-6]
    if lefts and rights:
        lock = min(abs(mean(lefts)), abs(mean(rights)))
        rep.add('full lock, left', mean(lefts), 'rad')
        rep.add('full lock, right', mean(rights), 'rad')
        rep.add('full lock (smaller side)', lock, 'rad', 'vehicle.max_steering_angle', ctx)
        rep.suggest('vehicle.max_steering_angle', lock, 'test 3.10: the smaller full lock')
    return rep


def steer_rate(rows, ctx: Context) -> Report:
    rep = Report('3.11 steering speed')
    parts = phases(rows)
    swings = []
    for i, (name, rs) in enumerate(parts):
        if not name.startswith('step to '):
            continue
        prev = parts[i - 1][1] if i > 0 else []
        both = list(prev) + list(rs)
        t = col(both, 't')
        cmd = col(both, 'steer_cmd')
        if not any(finite(c) for c in cmd):
            cmd = col(both, 'cmd_steer')
        sw = an.swing(t, cmd, col(both, 'steer'), float(rs[0]['t']))
        if sw is None:
            rep.notes.append(f'{name}: no clean swing in the measured angle')
            continue
        swings.append(sw)
        rep.add(f'{name}: {sw.start:+.2f} -> {sw.target:+.2f} rad', sw.time_to_95, 's',
                note=f'rate {sw.rate:.3f} rad/s')
    if not swings:
        rep.notes.append('no measured angle: time centre to full lock on a video instead')
        return rep
    full = [s.time_to_95 for s in swings if abs(s.start) < 0.05]
    if full:
        rep.add('centre to full lock (95%)', mean(full), 's')
    rate = mean([s.rate for s in swings])
    rep.add('steering speed', rate, 'rad/s', 'actuators.steer_rate', ctx)
    rep.suggest('actuators.steer_rate', rate, 'test 3.11: mean of the swings, 40-80%')
    moving = [r for name, rs in parts if name.startswith(('step to ', 'centre')) for r in rs]
    cmd = col(moving, 'steer_cmd')
    if not any(finite(c) for c in cmd):
        cmd = col(moving, 'cmd_steer')
    lag = an.fit_steer_lag(col(moving, 't'), cmd, col(moving, 'steer'), rate)
    if lag is not None:
        rep.add('linkage lag (fit)', lag, 's', 'actuators.steer_lag', ctx)
        rep.suggest('actuators.steer_lag', lag, 'test 3.11: motor speed, then this lag')
    cmd_rate = command_rate(rows)
    if finite(cmd_rate) and cmd_rate < rate * 1.15:
        rep.notes.append(f"ego's command ramped at {cmd_rate:.2f} rad/s, about the measured "
                         "speed: the measurement may be ego's limit, not the motor's")
    return rep


def command_rate(rows) -> float:
    """Return the fastest ego's steering command moved (rad/s)."""
    t, c = col(rows, 't'), col(rows, 'steer_cmd')
    rates = [abs(b - a) / (t2 - t1) for t1, t2, a, b in zip(t, t[1:], c, c[1:])
             if finite(a, b) and t2 - t1 > 1e-3]
    rates = [r for r in rates if r > 1e-3]
    if not rates:
        return NAN
    rates.sort()
    return rates[int(0.9 * (len(rates) - 1))]   # the 90th percentile: ignore one-tick jitter


def steer_centre(rows, ctx: Context) -> Report:
    rep = Report('3.12 centre and deadband')
    parts = phases(rows)
    centre = [rs for name, rs in parts if name == 'centre']
    if not centre:
        rep.notes.append('the centre phase never ran')
        return rep
    offset = settled_angle(centre[0], 2.0)
    if not finite(offset):
        rep.notes.append('no measured angle: measure with a protractor (the test asks)')
        return rep
    rep.add('angle when told straight', offset, 'rad', 'actuators.steer_offset', ctx,
            note=f'{math.degrees(offset):+.2f} deg; passes under 1 deg'
            if abs(math.degrees(offset)) < 1 else f'{math.degrees(offset):+.2f} deg: write '
                                                  'it down')
    rep.suggest('actuators.steer_offset', offset, 'test 3.12')
    estimates = []
    for side in ('left', 'right'):
        base = offset
        prev = 0.0
        found = None
        for name, rs in parts:
            if name == f'centre after {"left" if side == "right" else "none"}':
                base = settled_angle(rs, 1.0)
            if not name.startswith(f'deadband {side} '):
                continue
            c = float(rs[-1]['cmd_steer'])
            m = settled_angle(rs, 0.5)
            if finite(m) and abs(m - base) > 0.5 * abs(c):
                found = (abs(prev), abs(c))
                break
            prev = c
        if found:
            est = 0.5 * (found[0] + found[1])
            estimates.append(est)
            rep.add(f'deadband, {side}', est, 'rad',
                    note=f'moved at {found[1]:.3f}, not at {found[0]:.3f}')
        else:
            rep.notes.append(f'deadband, {side}: the wheels never moved by half a step up to '
                             '0.02 rad')
    if estimates:
        rep.add('deadband', mean(estimates), 'rad', 'actuators.steer_deadband', ctx)
        rep.suggest('actuators.steer_deadband', mean(estimates), 'test 3.12: tiny steps')
    return rep


# --- stage 4: on the ground ---------------------------------------------------------------

def push_fit(rows, ctx: Context) -> Optional[an.Throttle]:
    """
    Return the throttle's map from speed-ups; None without a throttle level.

    The deadband is the median throttle at which each run first moved. The drag is
    vehicle.yaml's: in a speed-up the drag and the throttle rise together, so one fit
    can't tell them apart. Run coast (4.2) first and paste its drag.
    """
    starts = []
    for _, rs in phases(rows):
        s = an.start_throttle(col(rs, 'throttle'), col(rs, 'speed'))
        if s is not None:
            starts.append(s)
    deadband = sorted(starts)[len(starts) // 2] if starts else 0.0
    a = accel_from_speed(rows)
    th, br, v = col(rows, 'throttle'), col(rows, 'brake'), col(rows, 'speed')
    use = [i for i in range(len(rows))
           if finite(th[i], v[i], a[i]) and not (finite(br[i]) and br[i] > 0.01)]
    return an.fit_throttle([th[i] for i in use], [v[i] for i in use], [a[i] for i in use],
                           drag=ctx.current.get('actuators.drag', 0.0), deadband=deadband)


def speed_up_runs(rows):
    return [(name, rs) for name, rs in phases(rows) if name.startswith('speed up to ')]


def accel_figures(rs) -> Dict[str, float]:
    """Peak and mean acceleration of one speed-up, from the wheel speed and from the IMU."""
    t, v = col(rs, 't'), col(rs, 'speed')
    t0 = t[0]
    target = float(rs[0]['cmd_speed'])
    t90 = an.first_crossing(t, v, 0.9 * target, t0)
    a_wheel = an.moving_average(t, accel_from_speed(rs), 0.5)
    a_imu = an.moving_average(t, col(rs, 'ax'), 0.5)
    end = t90 if t90 is not None else t[-1]
    within = [i for i, ti in enumerate(t) if ti <= end]
    v0 = v[0] if finite(v[0]) else 0.0
    return {
        'target': target,
        't90': (t90 - t0) if t90 is not None else NAN,
        'wheel_peak': max((a_wheel[i] for i in within if finite(a_wheel[i])), default=NAN),
        'wheel_mean': (0.9 * target - v0) / (t90 - t0) if t90 and t90 > t0 else NAN,
        'imu_peak': max((a_imu[i] for i in within if finite(a_imu[i])), default=NAN),
        'imu_mean': mean([col(rs, 'ax')[i] for i in within]),
    }


def add_throttle_fit(rep: Report, rows, ctx: Context, test: str):
    fit = push_fit(rows, ctx)
    if fit is None:
        rep.notes.append('no measured throttle level (/vehicle/throttle silent or NaN): '
                         'max_accel can only be read from the g figures above, at the '
                         'throttle the backend chose. On the 2025-26 ESP32 the speed command '
                         'is the throttle: speed / full_throttle_speed (legacy_protocol.py)')
        return
    gain, deadband = fit.gain, fit.deadband
    rep.add('full-throttle acceleration (fit)', gain, 'm/s^2', 'actuators.max_accel', ctx,
            note=f"{an.to_g(gain):.3f} g; vehicle.yaml's drag {fit.drag:g} /s; "
                 f'{fit.n} samples')
    rep.add('throttle deadband (where it first moved)', deadband, '',
            'actuators.throttle_deadband', ctx)
    rep.suggest('actuators.max_accel', gain, f'test {test}: throttle level vs acceleration')
    rep.suggest('actuators.throttle_deadband', deadband, f'test {test}')
    lag = an.fit_lag(col(rows, 't'), col(rows, 'throttle_cmd'), col(rows, 'throttle'))
    if lag is not None:
        rep.add('throttle lag (fit)', lag, 's', 'actuators.throttle_lag', ctx)
        rep.suggest('actuators.throttle_lag', lag, f'test {test}: command vs measured level')


def speed_up(rows, ctx: Context) -> Report:
    rep = Report('4.1 speed up')
    runs = speed_up_runs(rows)
    if not runs:
        rep.notes.append('the speed-up never ran')
        return rep
    name, rs = runs[-1]
    t, v = col(rs, 't'), col(rs, 'speed')
    target = float(rs[0]['cmd_speed'])
    for s, sec in an.time_to_speeds(t, v, [x for x in (0.5, 1.0, 2.0, 3.0) if x <= target + 1e-6],
                                    t[0]).items():
        rep.add(f'time to {s:g} m/s', sec, 's', note='' if sec is not None else 'not reached')
    f = accel_figures(rs)
    rep.add('acceleration, wheel speed: mean to 90%', an.to_g(f['wheel_mean']), 'g',
            note=f"{f['wheel_mean']:.3f} m/s^2" if finite(f['wheel_mean']) else '')
    rep.add('acceleration, wheel speed: peak (0.5 s)', an.to_g(f['wheel_peak']), 'g',
            note=f"{f['wheel_peak']:.3f} m/s^2" if finite(f['wheel_peak']) else '')
    rep.add('acceleration, IMU: mean to 90%', an.to_g(f['imu_mean']), 'g')
    rep.add('acceleration, IMU: peak (0.5 s)', an.to_g(f['imu_peak']), 'g')
    add_throttle_fit(rep, [r for _, rs in runs for r in rs], ctx, '4.1')
    return rep


def coast(rows, ctx: Context) -> Report:
    rep = Report('4.2 coast')
    runs = [rs for name, rs in phases(rows) if name.startswith('coast from ')]
    if not runs:
        rep.notes.append('the coast never ran')
        return rep
    rs = runs[-1]
    a = an.moving_average(col(rs, 't'), accel_from_speed(rs), 0.5)
    th, br, v = col(rs, 'throttle'), col(rs, 'brake'), col(rs, 'speed')
    free = [i for i in range(len(rs)) if not (finite(th[i]) and th[i] > 0.01)
            and not (finite(br[i]) and br[i] > 0.01) and finite(a[i], v[i])]
    # Skip the first half second: the throttle is still letting go.
    t = col(rs, 't')
    free = [i for i in free if t[i] - t[0] > 0.5]
    line = an.fit_line([v[i] for i in free], [a[i] for i in free])
    rep.add('coasting from', v[0], 'm/s')
    rep.add('time coasted', t[-1] - t[0], 's')
    if line is None or len(free) < 20:
        rep.notes.append('too few coasting samples (throttle or brake on throughout?)')
        return rep
    rep.add('deceleration at the start', an.to_g(-line.at(v[0])), 'g')
    rep.add('drag: m/s lost per s per m/s', -line.slope, '1/s', 'actuators.drag', ctx,
            note=f'r2 {line.r2:.3f}')
    rep.add('rolling resistance (constant part)', -line.intercept, 'm/s^2',
            note='the model has none: it should be near 0')
    rep.suggest('actuators.drag', -line.slope, 'test 4.2: deceleration vs speed, coasting')
    return rep


def brake(rows, ctx: Context) -> Report:
    rep = Report('4.3 brake')
    pts = []
    brake_rows = []
    for name, rs in phases(rows):
        if not name.startswith('brake from '):
            continue
        brake_rows += rs
        t = col(rs, 't')
        stop = an.stopping(t, col(rs, 'speed'), t[0])
        a_imu = an.moving_average(t, col(rs, 'ax'), 0.5)
        peak = -min((x for x in a_imu if finite(x)), default=NAN)
        if stop is None:
            rep.notes.append(f'{name}: never stopped')
            continue
        rep.add(f'from {stop.start_speed:.2f} m/s: distance', stop.distance, 'm',
                note=f'{stop.time:.2f} s; mean {an.to_g(stop.mean_decel):.3f} g, '
                     f'IMU peak {an.to_g(peak):.3f} g')
        pts.append(stop)
    if not pts:
        return rep
    a = accel_from_speed(brake_rows)
    br, th, v = col(brake_rows, 'brake'), col(brake_rows, 'throttle'), col(brake_rows, 'speed')
    use = [i for i in range(len(brake_rows)) if finite(br[i], a[i], v[i]) and br[i] > 0.02
           and v[i] > 0.1 and not (finite(th[i]) and th[i] > 0.01)]
    if len(use) >= 20:
        drag = ctx.current.get('actuators.drag', 0.0)
        line = an.fit_line([br[i] for i in use], [-a[i] - drag * v[i] for i in use])
        if line and line.slope > 0:
            rep.add('full-brake deceleration (fit)', line.slope, 'm/s^2',
                    'actuators.max_brake', ctx,
                    note=f'{an.to_g(line.slope):.3f} g; r2 {line.r2:.3f}; '
                         f'brake level up to {max(br[i] for i in use):.2f}')
            rep.suggest('actuators.max_brake', line.slope, 'test 4.3: brake level vs '
                                                           'deceleration')
        lag = an.fit_lag(col(brake_rows, 't'), col(brake_rows, 'brake_cmd'), br)
        if lag is not None:
            rep.add('brake lag (fit)', lag, 's', 'actuators.brake_lag', ctx)
            rep.suggest('actuators.brake_lag', lag, 'test 4.3: command vs measured level')
    else:
        rep.notes.append('no measured brake level: max_brake only from the g figures above. '
                         'These are normal stops (ego ramps them), not full brake: a fixed '
                         'brake % needs a brake command, which the stack has none of')
    return rep


def throttle_map(rows, ctx: Context) -> Report:
    rep = Report('4.4 throttle map')
    runs = speed_up_runs(rows)
    for name, rs in runs:
        f = accel_figures(rs)
        rep.add(f"to {f['target']:g} m/s: peak acceleration", an.to_g(f['wheel_peak']), 'g',
                note=f"IMU {an.to_g(f['imu_peak']):.3f} g; 90% in {fmt(f['t90'], 2)} s")
    every = [r for _, rs in runs for r in rs]
    if has(every, 'throttle'):
        a = accel_from_speed(every)
        th, v = col(every, 'throttle'), col(every, 'speed')
        drag = ctx.current.get('actuators.drag', 0.0)
        bins: Dict[int, List[float]] = {}
        for i in range(len(every)):
            if finite(th[i], a[i], v[i]) and th[i] > 0.0:
                bins.setdefault(min(9, int(th[i] * 10)), []).append(a[i] + drag * v[i])
        for b in sorted(bins):
            if len(bins[b]) >= 5:
                rep.add(f'throttle {b * 10}-{b * 10 + 10}%', mean(bins[b]), 'm/s^2',
                        note=f'{an.to_g(mean(bins[b])):.3f} g, drag added back; '
                             f'{len(bins[b])} samples')
    add_throttle_fit(rep, every, ctx, '4.4')
    return rep


def circles(rows, ctx: Context) -> Report:
    rep = Report('4.5 circles')
    pts = []
    for name, rs in phases(rows):
        if not name.startswith('circle '):
            continue
        c = float(rs[-1]['cmd_steer'])
        v, gz = mean(col(rs, 'speed')), mean(col(rs, 'gz'))
        from_yaw = an.wheel_angle(gz, v, ctx.wheelbase)
        circle = an.fit_circle(col(rs, 'x'), col(rs, 'y'))
        from_circle = an.angle_for_radius(circle.radius, ctx.wheelbase) if circle else NAN
        gps = gps_radius(rs, ctx)
        measured = mean(col(rs, 'steer'))
        diameter = 2 * circle.radius if circle else NAN
        rep.add(f'command {c:+.3f} rad: from yaw rate', from_yaw, 'rad',
                note=f'circle {fmt(from_circle)} rad (diameter {fmt(diameter, 2)} m'
                     + (f', GPS {gps * 2:.2f} m' if finite(gps) else '')
                     + f'); sensor {fmt(measured)}; {v:.2f} m/s')
        pts.append((c, from_yaw, from_circle))
    if not pts:
        rep.notes.append('no circle finished')
        return rep
    line = an.fit_line([p[0] for p in pts], [p[1] for p in pts])
    if line:
        rep.add('gain: real angle / command', line.slope, '', note=f'r2 {line.r2:.4f}')
        rep.add('real angle at command 0', line.intercept, 'rad', 'actuators.steer_offset', ctx)
    full = [abs(p[1]) for p in pts if abs(p[0]) >= ctx.max_steering - 1e-6 and finite(p[1])]
    if full:
        lock = min(full)
        rep.add('full lock, real (smaller side)', lock, 'rad', 'vehicle.max_steering_angle', ctx,
                note=f'tightest circle: {2 * ctx.wheelbase / math.tan(lock):.2f} m across '
                     '(rear axle)')
        rep.suggest('vehicle.max_steering_angle', lock, 'test 4.5: the full-lock circles')
    return rep


def gps_radius(rs, ctx: Context) -> float:
    """Return the circle's radius from GPS, moved from the antenna to the rear axle (m)."""
    lat, lon = col(rs, 'lat'), col(rs, 'lon')
    pairs = [(a, b) for a, b in zip(lat, lon) if finite(a, b)]
    if len(pairs) < 10:
        return NAN
    lat0, lon0 = pairs[0]
    xy = [an.gps_to_xy(a, b, lat0, lon0) for a, b in pairs]
    circle = an.fit_circle([p[0] for p in xy], [p[1] for p in xy])
    if circle is None or circle.radius <= abs(ctx.gps_x):
        return NAN
    return math.sqrt(circle.radius ** 2 - ctx.gps_x ** 2)


def straight(rows, ctx: Context) -> Report:
    rep = Report('4.7 straight line')
    runs = [rs for name, rs in phases(rows) if name == 'straight']
    if not runs:
        rep.notes.append('the straight never ran')
        return rep
    rs = runs[-1]
    d = an.drift(col(rs, 'x'), col(rs, 'y'), col(rs, 'yaw'))
    if d is None:
        rep.notes.append('no pose from /localization/odom/local')
        return rep
    rep.add('driven along the start heading', d.along, 'm')
    rep.add('sideways drift (+ left)', d.across, 'm',
            note='passes: under 0.5 m over 10 m' if abs(d.across) < 0.5 * d.along / 10.0
            else 'FAILS: 0.5 m over 10 m')
    rep.add('heading change', math.degrees(d.heading), 'deg')
    angle = an.wheel_angle(mean(col(rs, 'gz')), mean(col(rs, 'speed')), ctx.wheelbase)
    rep.add('real wheel angle (yaw rate / speed)', angle, 'rad', 'actuators.steer_offset', ctx)
    rep.suggest('actuators.steer_offset', angle, 'test 4.7: yaw rate on a straight')
    return rep


ANALYSES = {
    'steer-sweep': steer_sweep, 'steer-rate': steer_rate, 'steer-centre': steer_centre,
    'speed-up': speed_up, 'coast': coast, 'brake': brake, 'throttle-map': throttle_map,
    'circles': circles, 'straight': straight,
}


def analyse(test: str, rows: Sequence[Mapping], ctx: Context) -> Report:
    return ANALYSES[test](rows, ctx)


def table(rep: Report) -> str:
    """Return the report as a plain-text table."""
    head = ('What', 'Measured', 'Unit', 'vehicle.yaml now', 'Note')
    body = [(r.what, r.value, r.unit, r.now, r.note) for r in rep.rows]
    widths = [max(len(str(x)) for x in column) for column in zip(head, *body)] if body else []
    lines = [rep.title, '=' * len(rep.title)]
    if body:
        lines.append('  '.join(h.ljust(w) for h, w in zip(head, widths)).rstrip())
        lines.append('  '.join('-' * w for w in widths))
        lines += ['  '.join(str(x).ljust(w) for x, w in zip(row, widths)).rstrip()
                  for row in body]
    lines += [f'NOTE: {n}' for n in rep.notes]
    return '\n'.join(lines)


def yaml_lines(rep: Report) -> str:
    """Return the vehicle.yaml lines to paste, by section. This tool never writes them."""
    if not rep.yaml:
        return ''
    out = ['# Paste into ros/bringup/aav_description/config/vehicle.yaml (check them first):']
    for section in ('vehicle', 'actuators'):
        keys = sorted(k for k in rep.yaml if k.startswith(section + '.'))
        if not keys:
            continue
        out.append(f'{section}:')
        for k in keys:
            value, comment = rep.yaml[k]
            out.append(f'  {k.split(".", 1)[1]}: {value:.4g}'.ljust(34) + f'# measured: {comment}')
    return '\n'.join(out)


def current_values(cfg: Mapping) -> Dict[str, float]:
    """vehicle.yaml's numbers as 'section.key' -> value, to compare against."""
    out = {}
    for section in ('vehicle', 'actuators'):
        for k, v in (cfg.get(section) or {}).items():
            if isinstance(v, (int, float)):
                out[f'{section}.{k}'] = float(v)
    return out


def context(cfg: Mapping) -> Context:
    v = cfg.get('vehicle', {})
    gps = ((cfg.get('sensors') or {}).get('gps_link') or {}).get('xyz', [0.0])
    return Context(wheelbase=float(v.get('wheelbase', 1.57)),
                   max_steering=float(v.get('max_steering_angle', 0.5)),
                   gps_x=float(gps[0]), current=current_values(cfg))


def parse_rows(records: Sequence[Mapping[str, str]]) -> List[Dict]:
    """CSV records (all strings) back to rows: numbers as floats, the phase as text."""
    out = []
    for rec in records:
        row: Dict = {}
        for k in COLUMNS:
            v = rec.get(k, '')
            if k == 'phase':
                row[k] = v
            else:
                try:
                    row[k] = float(v) if v != '' else NAN
                except ValueError:
                    row[k] = NAN
        out.append(row)
    return out


def number(value: Optional[float]) -> str:
    """Return a CSV cell: blank for unknown."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ''
    return f'{value:.6g}'
