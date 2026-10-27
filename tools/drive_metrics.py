"""
How well the car followed Nav2's path: the numbers controller_compare.py reports.

No ROS here, so the tests run anywhere (tools/tests/test_drive_metrics.py).

One leg is one Nav2 goal. It records, on Gazebo's clock:

  truth     [(t, x, y, yaw)]        where the car really was (/vehicle/gazebo/truth, map frame)
  plans     [(t, [(x, y), ...])]    each path the planner sent (/plan), as it arrived
  steering  [(t, angle)]            ego's steering command (/ego/actuator_cmd), rad
  asked     [(t, v)]                the controller's speed command (/cmd_vel_nav), m/s
  start, end                        s: the goal sent, and its result (or the time-out)
  goal      (x, y, yaw)             where it was sent, map frame, rad
  reached   bool                    Nav2 said it succeeded
  cpu       percent or None         controller_server's share of one core over the leg
  obstacle  (x, y, side) or None    a square box on the road, m
  body      (length, width, rear_overhang)   the car's outline (vehicle.yaml), m

summary() turns that into one row: see COLUMNS for what each number means. svg() draws the
drives on the map.

The A-to-B numbers at the end (stop_error ... final_metre) are tools/atob_score.py's: how
well the car sped up, held its speed and stopped on point B (docs/a-to-b.md, "Scoring a
run"). They take plain series: speeds [(t, v)] in m/s, + forward; positions [(t, x, y)]
in the map frame, m; commands [(t, v)], m/s.
"""

import bisect
import math
from xml.sax.saxutils import escape

STILL = 0.05        # m/s: slower than this is standing still
STOP_TIME = 1.0     # s: a stand-still at least this long, between moving, is a stop
SWITCH = 1.5        # m: a new plan this far from the last, on average, took another route
MOVED = 0.1         # m from where it began: the car has started
GOAL_TOLERANCE = 1.0  # m: Nav2's xy_goal_tolerance (nav2.yaml general_goal_checker)


def segment_distance(p, a, b):
    """Return the distance (m) from point p to the segment a-b."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    s = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + s * dx), py - (ay + s * dy))


def path_distance(p, path):
    """Return the distance (m) from p to a path of (x, y) points; NaN for no points."""
    if not path:
        return math.nan
    if len(path) == 1:
        return math.hypot(p[0] - path[0][0], p[1] - path[0][1])
    return min(segment_distance(p, a, b) for a, b in zip(path, path[1:]))


def footprint(x, y, yaw, body):
    """Return the car's outline at a pose: 4 corners, from body (length, width, rear_overhang)."""
    length, width, rear = body
    c, s = math.cos(yaw), math.sin(yaw)
    corners = [(length - rear, width / 2), (length - rear, -width / 2),
               (-rear, -width / 2), (-rear, width / 2)]
    return [(x + c * u - s * v, y + s * u + c * v) for u, v in corners]


def square(x, y, side):
    """Return an axis-aligned square's 4 corners, centred on (x, y)."""
    h = side / 2
    return [(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]


def inside(p, polygon):
    """Return True if p is inside a convex polygon (corners in order, either way round)."""
    signs = set()
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if cross != 0.0:
            signs.add(cross > 0)
    return len(signs) <= 1


def polygon_distance(a, b):
    """Return the gap (m) between two convex polygons: 0 when they touch or overlap."""
    if any(inside(p, b) for p in a) or any(inside(p, a) for p in b):
        return 0.0
    # Apart: the gap is from a corner of one to an edge of the other.
    return min(min(path_distance(p, b + b[:1]) for p in a),
               min(path_distance(p, a + a[:1]) for p in b))


def angle_diff(a, b):
    """Return a - b, wrapped to -pi..pi."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


def speeds(truth):
    """Return [(t, v)]: signed speed (m/s, + forward) between truth samples, from positions."""
    out = []
    for (t0, x0, y0, _), (t1, x1, y1, yaw) in zip(truth, truth[1:]):
        dt = t1 - t0
        if dt > 0.0:
            out.append((t1, ((x1 - x0) * math.cos(yaw) + (y1 - y0) * math.sin(yaw)) / dt))
    return out


def travelled(truth):
    """Return the distance (m) the car covered."""
    return sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(truth, truth[1:]))


def path_length(path):
    """Return a path's length (m): [(x, y)]."""
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def lingered(belief, goal, end, tolerance=GOAL_TOLERANCE):
    """
    Return how long (s) the car drove on after the EKF first put it within tolerance of goal.

    Nav2's goal checker uses the same belief: 0 means it stopped as soon as it got there; a
    car that circles a goal it reached shows here (TODO 17). None if it never got there.
    """
    gx, gy = goal[:2]
    first = next((t for t, x, y, _ in belief if math.hypot(x - gx, y - gy) <= tolerance), None)
    return None if first is None else max(0.0, end - first)


def moving_after(truth, start, distance=MOVED):
    """Return how long (s) after `start` the car got `distance` m from where it began, or None."""
    if not truth:
        return None
    _, x0, y0, _ = truth[0]
    for t, x, y, _ in truth:
        if math.hypot(x - x0, y - y0) >= distance:
            return t - start
    return None


def first_command(commands, start, least=STILL):
    """Return how long (s) after `start` a speed command first reached `least` m/s, or None."""
    return next((t - start for t, v in commands if abs(v) >= least), None)


def thin(samples, every):
    """Return the samples at least `every` s apart, keeping the first and the last."""
    out = []
    for s in samples:
        if not out or s[0] - out[-1][0] >= every:
            out.append(s)
    if samples and out[-1] is not samples[-1]:
        out.append(samples[-1])
    return out


def off_path(truth, plans):
    """Return the distance (m) from each truth sample to the newest plan then; none before one."""
    out, i, current = [], 0, None
    for t, x, y, _ in truth:
        while i < len(plans) and plans[i][0] <= t:
            current = plans[i][1]
            i += 1
        if current:
            out.append(path_distance((x, y), current))
    return out


def route_switches(plans, apart=SWITCH):
    """
    Return how many times a new plan took another route: on average `apart` m off the last.

    Only the new plan's part ahead, where it overlaps the last one's ground: each of its
    points against the last plan. A plan that only grows or shrinks at its end isn't one.
    """
    switches = 0
    for (_, before), (_, after) in zip(plans, plans[1:]):
        if len(before) < 2 or len(after) < 2:
            continue
        gaps = [path_distance(p, before) for p in after[:max(2, len(after) // 2)]]
        switches += sum(gaps) / len(gaps) > apart
    return switches


def belief_errors(truth, belief):
    """
    Return (position gaps m, heading gaps rad): each belief against the truth nearest in time.

    belief is where the global EKF thought the car was, (t, x, y, yaw), as truth is: what
    Nav2 steers by. Its gap from the truth is localization's error, not the controller's.
    """
    if not truth:
        return [], []
    times = [t for t, *_ in truth]
    gaps, turns = [], []
    for t, x, y, yaw in belief:
        i = bisect.bisect_left(times, t)
        near = min((j for j in (i - 1, i) if 0 <= j < len(truth)),
                   key=lambda j: abs(times[j] - t))
        _, tx, ty, tyaw = truth[near]
        gaps.append(math.hypot(x - tx, y - ty))
        turns.append(abs(angle_diff(yaw, tyaw)))
    return gaps, turns


def rms_rate(samples):
    """Return the root mean square (per s) of how fast a value changes, from [(t, value)]."""
    rates = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(samples, samples[1:])
             if b[0] > a[0]]
    return math.sqrt(sum(r * r for r in rates) / len(rates)) if rates else 0.0


def stops(truth, still=STILL, least=STOP_TIME):
    """Count the stand-stills of at least `least` s between moving (not the start, not the end)."""
    count, since, moved = 0, None, False
    for t, v in speeds(truth):
        if abs(v) >= still:
            if moved and since is not None and t - since >= least:
                count += 1
            moved, since = True, None
        elif moved and since is None:
            since = t
    return count


def reversals(truth, moving=STILL):
    """Count the changes between driving forward and in reverse."""
    signs = [v > 0 for _, v in speeds(truth) if abs(v) >= moving]
    return sum(a != b for a, b in zip(signs, signs[1:]))


def clearance(truth, obstacle, body):
    """Return the smallest gap (m) between the car's outline and the box, or None."""
    if obstacle is None or not truth:
        return None
    box = square(*obstacle)
    return min(polygon_distance(footprint(x, y, yaw, body), box) for _, x, y, yaw in truth)


def summary(leg):
    """Return one row of numbers for a leg (see COLUMNS)."""
    truth = leg['truth']
    gaps = off_path(truth, leg['plans'])
    lost, turned = belief_errors(truth, leg.get('belief', []))
    switched = route_switches(leg['plans'])
    route = leg['plans'][0][1] if leg['plans'] else []
    driven, planned = travelled(truth), path_length(route)
    near = lingered(leg.get('belief', []), leg['goal'], leg['end'])
    row = {
        'reached': bool(leg['reached']),
        'time_s': leg['end'] - leg['start'],
        'driven_m': driven,
        'route_m': planned if route else math.nan,
        'detour': driven / planned if planned > 0.0 else math.nan,
        'lingered_s': math.nan if near is None else near,
        'asked_after_s': first_command(leg.get('asked', []), leg['start']),
        'moving_after_s': moving_after(truth, leg['start']),
        'off_path_mean_m': sum(gaps) / len(gaps) if gaps else math.nan,
        'off_path_max_m': max(gaps) if gaps else math.nan,
        'off_route_max_m': (max(path_distance((x, y), route) for _, x, y, _ in truth)
                            if route and truth else math.nan),
        'end_error_m': math.nan,
        'end_heading_deg': math.nan,
        'steering_rms': rms_rate(leg['steering']),
        'stops': stops(truth),
        'reversals': reversals(truth),
        'clearance_m': clearance(truth, leg.get('obstacle'), leg['body']),
        'cpu_percent': leg.get('cpu'),
        'route_switches': switched,
        'belief_max_m': max(lost) if lost else math.nan,
        'belief_heading_max_deg': math.degrees(max(turned)) if turned else math.nan,
    }
    if truth:
        _, x, y, yaw = truth[-1]
        gx, gy, gyaw = leg['goal']
        row['end_error_m'] = math.hypot(gx - x, gy - y)
        row['end_heading_deg'] = abs(math.degrees(angle_diff(gyaw, yaw)))
    return row


# (key, what it is, format): table()'s rows, in order. "The path" is the planner's newest
# (it replans every second, from wherever the car is); "the route" is its first, from the
# start: a car that wanders far shows there.
COLUMNS = [
    ('reached', 'Reached the goal', lambda v: 'yes' if v else '**no**'),
    ('time_s', 'Time (s)', '{:.0f}'),
    ('driven_m', 'Driven (m)', '{:.1f}'),
    ('route_m', 'The first route (m)', '{:.1f}'),
    ('detour', 'Driven / the first route', '{:.2f}'),
    ('lingered_s', 'Drove on after the EKF had it at the goal (s)', '{:.1f}'),
    ('asked_after_s', 'Controller asked to move after (s)', '{:.1f}'),
    ('moving_after_s', 'Car moving after (s)', '{:.1f}'),
    ('off_path_mean_m', 'Off the path, mean (m)', '{:.2f}'),
    ('off_path_max_m', 'Off the path, worst (m)', '{:.2f}'),
    ('off_route_max_m', 'Off the first route, worst (m)', '{:.1f}'),
    ('end_error_m', 'End: off the goal (m)', '{:.2f}'),
    ('end_heading_deg', 'End: heading off (deg)', '{:.0f}'),
    ('steering_rms', 'Steering work (rad/s RMS)', '{:.3f}'),
    ('stops', 'Stops', '{:d}'),
    ('reversals', 'Reversals', '{:d}'),
    ('clearance_m', 'Closest to the box (m)', '{:.2f}'),
    ('cpu_percent', 'controller CPU (%)', '{:.0f}'),
    ('route_switches', 'The planner changed its route (times)', '{:d}'),
    ('belief_max_m', 'Where the EKF put the car: off, worst (m)', '{:.2f}'),
    ('belief_heading_max_deg', "The EKF's heading: off, worst (deg)", '{:.0f}'),
]


def cell(value, fmt):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return '-'
    return fmt(value) if callable(fmt) else fmt.format(value)


def table(rows, first='', columns=None):
    """
    Return a Markdown table: a column for each (label, summary row), a row for each number.

    columns: [(key, name, format)], COLUMNS by default. A number nobody has is left out.
    """
    columns = COLUMNS if columns is None else columns
    keep = [c for c in columns if any(cell(r.get(c[0]), c[2]) != '-' for _, r in rows)]
    lines = ['| ' + ' | '.join([first] + [label for label, _ in rows]) + ' |',
             '|---|' + '---:|' * len(rows)]
    for key, name, fmt in keep:
        lines.append('| ' + ' | '.join([name] + [cell(r.get(key), fmt) for _, r in rows]) +
                     ' |')
    return '\n'.join(lines)


def svg(bounds, tracks, blocks=(), marks=(), scale=8.0):
    """
    Return an SVG picture of drives in the map frame (x east, y north: north is up).

    bounds  (x0, y0, x1, y1)                     m: the part of the map to show
    tracks  [(label, colour, [[(x, y)]], dashed)]  lines, one key entry each: where a car
                                                 went, the plans (one line per leg)
    blocks  [(x0, y0, x1, y1, colour)]           rectangles: walls, a building, the box
    marks   [(x, y, label)]                      dots with a name: the goals
    A key below the map names each track, beside a 10 m scale bar.
    """
    x0, y0, x1, y1 = bounds
    width, height = (x1 - x0) * scale, (y1 - y0) * scale
    key = max(24 * len(tracks) + 16, 44)     # px under the map: the key and the bar

    def at(x, y):
        return (x - x0) * scale, (y1 - y) * scale

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
           f'height="{height + key:.0f}" font-family="sans-serif" font-size="14">',
           f'<rect width="{width:.0f}" height="{height + key:.0f}" fill="white"/>']
    for bx0, by0, bx1, by1, colour in blocks:
        left, top = at(min(bx0, bx1), max(by0, by1))
        out.append(f'<rect x="{left:.1f}" y="{top:.1f}" width="{abs(bx1 - bx0) * scale:.1f}" '
                   f'height="{abs(by1 - by0) * scale:.1f}" fill="{colour}"/>')
    for _, colour, lines, dashed in tracks:
        for points in lines:
            if not points:
                continue
            line = ' '.join('{:.1f},{:.1f}'.format(*at(x, y)) for x, y in points)
            out.append(f'<polyline points="{line}" fill="none" stroke="{colour}" '
                       'stroke-width="2.5" stroke-linejoin="round"' +
                       (' stroke-dasharray="6,4"' if dashed else '') + '/>')
    for x, y, label in marks:
        cx, cy = at(x, y)
        out += [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="black"/>',
                f'<text x="{cx + 8:.1f}" y="{cy - 8:.1f}">{escape(label)}</text>']
    for i, (label, colour, _, dashed) in enumerate(tracks):
        y = height + 20 + 24 * i
        out += [f'<line x1="10" y1="{y - 5}" x2="40" y2="{y - 5}" stroke="{colour}" '
                'stroke-width="2.5"' + (' stroke-dasharray="6,4"' if dashed else '') + '/>',
                f'<text x="48" y="{y}">{escape(label)}</text>']
    bar = 10.0 * scale
    out += [f'<line x1="{width - 10 - bar:.1f}" y1="{height + 15}" x2="{width - 10:.1f}" '
            f'y2="{height + 15}" stroke="black" stroke-width="3"/>',
            f'<text x="{width - 10 - bar:.1f}" y="{height + 35}">10 m</text>', '</svg>']
    return '\n'.join(out) + '\n'


# --- A to B: how well the car sped up, held its speed and stopped on B (atob_score.py) ---

SMOOTH = 0.5        # s: the moving average's width, for deceleration and jerk
REACH = 0.9         # of the set speed: "up to speed" (the 90 % rise time)
CREEP = 0.15        # m/s: slower than this, short of the stop, the car creeps (point_driver: 0.1)
LAST_METRE = 1.0    # m: the final approach the creep is counted over


def stop_error(a, b, p):
    """
    Return (along, across) in m: where point p is from B, measured on the line from A to B.

    along   + past B, - short of B (along the direction A -> B)
    across  + left of the line, - right of it (REP-103: y left)
    A, B and p are (x, y) in the same frame (the map). A and B must differ.
    """
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length == 0.0:
        raise ValueError('A and B are the same point')
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    dx, dy = p[0] - b[0], p[1] - b[1]
    return dx * ux + dy * uy, ux * dy - uy * dx


def overshoot_past(a, b, track):
    """
    Return how far (m) the car ever got past B, along the line A -> B: 0 if it never did.

    track is [(t, x, y)], the map frame. The worst moment counts, not only the end: a car
    that rolls past B and backs up still shows it.
    """
    return max([0.0] + [stop_error(a, b, (x, y))[0] for _, x, y in track])


def reach_time(speeds, set_speed, start=None, fraction=REACH):
    """
    Return the time (s) from `start` until the speed first reached `fraction` of set_speed.

    The 90 % rise time. start is when the car was asked to go (s; the first sample if None).
    None if it never got there.
    """
    if not speeds or set_speed <= 0.0:
        return None
    start = speeds[0][0] if start is None else start
    return next((t - start for t, v in speeds if t >= start and v >= fraction * set_speed),
                None)


def hold_window(speeds, set_speed, commands=(), fraction=REACH):
    """
    Return (t0, t1) in s: the time the car held its speed; None if it never got up to it.

    t0: the speed first reached `fraction` (90 %) of set_speed. t1: the command first fell
    below 99 % of set_speed after t0 (it started slowing for B); with no commands, the last
    moment the speed was at 90 % of set_speed.
    """
    t0 = next((t for t, v in speeds if v >= fraction * set_speed), None)
    if t0 is None or set_speed <= 0.0:
        return None
    t1 = next((t for t, v in commands if t > t0 and v < 0.99 * set_speed), None)
    if t1 is None:
        t1 = max(t for t, v in speeds if v >= fraction * set_speed)
    return (t0, t1) if t1 > t0 else None


def hold_error(speeds, set_speed, window):
    """
    Return the mean speed error (m/s) while holding: measured - set, over the window.

    + faster than asked, - slower. window is hold_window()'s (t0, t1); NaN without one.
    Each sample counts the same (the recordings are at a steady rate).
    """
    if window is None:
        return math.nan
    errors = [v - set_speed for t, v in speeds if window[0] <= t <= window[1]]
    return sum(errors) / len(errors) if errors else math.nan


def overshoot_percent(speeds, set_speed):
    """Return how far (%) the top speed went over set_speed: 0 if it never did."""
    if not speeds or set_speed <= 0.0:
        return math.nan
    return max(0.0, 100.0 * (max(v for _, v in speeds) - set_speed) / set_speed)


def smooth(series, width=SMOOTH):
    """
    Return a moving average of [(t, value)], `width` s wide: [(mean t, mean value)].

    Each output is the mean of the samples within width/2 of one sample, put at their mean
    time, so a straight line stays exactly straight. Only full windows: the first and the
    last width/2 s are left out (a half window would bend the ends).
    """
    if not series:
        return []
    # 1 ns of slack, so samples at i / rate don't drop out of a window by rounding.
    first, last, half = series[0][0], series[-1][0], width / 2.0 + 1e-9
    out, lo, hi, n = [], 0, 0, len(series)
    for t, _ in series:
        if t - half < first - 2e-9 or t + half > last + 2e-9:
            continue
        while series[lo][0] < t - half:
            lo += 1
        while hi < n and series[hi][0] <= t + half:
            hi += 1
        window = series[lo:hi]
        out.append((sum(s[0] for s in window) / len(window),
                    sum(s[1] for s in window) / len(window)))
    return out


def rates(series):
    """Return [(mid t, d value / dt)]: the rate between each two samples, at their middle."""
    return [((a[0] + b[0]) / 2.0, (b[1] - a[1]) / (b[0] - a[0]))
            for a, b in zip(series, series[1:]) if b[0] > a[0]]


def accelerations(speeds, width=SMOOTH):
    """Return [(t, a)] in m/s^2: the speed smoothed (smooth(), `width` s), then differenced."""
    return rates(smooth(speeds, width))


def peak_deceleration(speeds, width=SMOOTH):
    """
    Return the hardest slowing (m/s^2, positive) anywhere in the run; 0 if it never slowed.

    The speed is smoothed by a `width` s moving average (smooth()), then differenced: a
    constant deceleration reads exactly; a bump shorter than `width` reads softer.
    NaN with too few samples.
    """
    acc = accelerations(speeds, width)
    return max(0.0, max(-a for _, a in acc)) if acc else math.nan


def peak_jerk(speeds, width=SMOOTH):
    """
    Return the largest jerk (m/s^3, either sign) anywhere in the run.

    The acceleration (accelerations(): speed smoothed by a `width` s moving average, then
    differenced) is smoothed again by the same moving average and differenced. A constant
    jerk reads exactly; a step of da in the acceleration reads as about da / width.
    NaN with too few samples.
    """
    jerk = rates(smooth(accelerations(speeds, width), width))
    return max(abs(j) for _, j in jerk) if jerk else math.nan


def stopped_at(speeds, still=STILL):
    """
    Return when (s) the car stopped for good: the first sample of its last stand-still.

    None if it never moved (no speed of `still` m/s or more) or was still moving at the end.
    """
    if not speeds or abs(speeds[-1][1]) >= still:
        return None
    moving = [i for i, (_, v) in enumerate(speeds) if abs(v) >= still]
    return speeds[moving[-1] + 1][0] if moving else None


def slowing_time(speeds, set_speed=None, still=STILL, fraction=REACH):
    """
    Return the time (s) from first slowing to stopped.

    First slowing: the last moment the speed was at `fraction` (90 %) of set_speed (of the
    top speed if None), before the stop. Stopped: stopped_at(). None if it never stopped or
    never got to that speed.
    """
    end = stopped_at(speeds, still)
    if end is None:
        return None
    top = set_speed if set_speed else max(v for _, v in speeds)
    fast = [t for t, v in speeds if t <= end and v >= fraction * top]
    return end - fast[-1] if fast else None


def distance(speeds, t0=-math.inf, t1=math.inf):
    """
    Return how far (m) the car went between t0 and t1 (s): |speed| integrated.

    The speed is taken as straight between samples (trapezoids; through zero, triangles).
    """
    total = 0.0
    for (ta, va), (tb, vb) in zip(speeds, speeds[1:]):
        lo, hi = max(ta, t0), min(tb, t1)
        if hi <= lo or tb <= ta:
            continue

        def at(t, ta=ta, va=va, tb=tb, vb=vb):
            return va + (vb - va) * (t - ta) / (tb - ta)
        a, b = at(lo), at(hi)
        if a * b >= 0.0:
            total += (abs(a) + abs(b)) / 2.0 * (hi - lo)
        else:       # through zero (a reversal): two triangles
            total += (a * a + b * b) / (2.0 * (abs(a) + abs(b))) * (hi - lo)
    return total


def coast_distance(speeds, commands, still=STILL):
    """
    Return the distance (m) the car rolled after its speed command went to zero for good.

    From the first command after which every command is under `still` m/s: the brakes'
    and the speed loop's share of the stop. NaN with no commands, or if the commands never
    went to zero.
    """
    if not commands or abs(commands[-1][1]) >= still:
        return math.nan
    asked = [i for i, (_, v) in enumerate(commands) if abs(v) >= still]
    if not asked:
        return math.nan
    return distance(speeds, commands[asked[-1] + 1][0])


def final_metre(speeds, still=STILL, creep=CREEP, metre=LAST_METRE):
    """
    Return (seconds, creep m) for the car's last `metre` (1 m) before it stopped.

    seconds   how long that last metre took (long: it crept up on B)
    creep m   how much of it the car covered slower than `creep` m/s
    Distances come from the speed (distance()). (NaN, NaN) if it never stopped, or drove
    less than `metre`.
    """
    end = stopped_at(speeds, still)
    if end is None:
        return math.nan, math.nan
    run = [s for s in speeds if s[0] <= end]
    covered, crept = 0.0, 0.0
    for (ta, va), (tb, vb) in zip(reversed(run[:-1]), reversed(run[1:])):
        step = (abs(va) + abs(vb)) / 2.0 * (tb - ta)
        part = 1.0 if covered + step <= metre else (metre - covered) / step
        if (abs(va) + abs(vb)) / 2.0 < creep:
            crept += part * step
        covered += part * step
        if part < 1.0:
            return end - (tb - part * (tb - ta)), crept
    return math.nan, math.nan
