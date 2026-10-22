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
"""

import bisect
import math
from xml.sax.saxutils import escape

STILL = 0.05        # m/s: slower than this is standing still
STOP_TIME = 1.0     # s: a stand-still at least this long, between moving, is a stop
MOVED = 0.1         # m from where it began: the car has started


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
    route = leg['plans'][0][1] if leg['plans'] else []
    row = {
        'reached': bool(leg['reached']),
        'time_s': leg['end'] - leg['start'],
        'driven_m': travelled(truth),
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
    ('belief_max_m', 'Where the EKF put the car: off, worst (m)', '{:.2f}'),
    ('belief_heading_max_deg', "The EKF's heading: off, worst (deg)", '{:.0f}'),
]


def cell(value, fmt):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return '-'
    return fmt(value) if callable(fmt) else fmt.format(value)


def table(rows, first=''):
    """
    Return a Markdown table: a column for each (label, summary row), a row for each number.

    A number nobody has is left out.
    """
    keep = [c for c in COLUMNS if any(cell(r[c[0]], c[2]) != '-' for _, r in rows)]
    lines = ['| ' + ' | '.join([first] + [label for label, _ in rows]) + ' |',
             '|---|' + '---:|' * len(rows)]
    for key, name, fmt in keep:
        lines.append('| ' + ' | '.join([name] + [cell(r[key], fmt) for _, r in rows]) + ' |')
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
