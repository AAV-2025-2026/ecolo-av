"""
The route from the HUD's map, turned into GPS waypoints for Nav2.

No ROS imports, so the tests run anywhere.

The app sends the OSRM route it drew: a list of {'lat': .., 'lon': ..}, often hundreds of
points a few metres apart. Nav2's follow_gps_waypoints drives to each waypoint in turn
and slows down at each one, so the route is cut down first:

1. simplify: keep only the points where the route bends (Douglas-Peucker);
2. space out: no two waypoints closer than min_spacing;
3. give each waypoint a heading along the route;
4. drop the first point: it is where the car already is.

Positions are (lat, lon) in degrees. Headings are yaw in the map frame (REP-103, ENU):
0 = east, pi/2 = north. Distances are metres on a sphere: close enough over a few km.
"""

import math
from typing import NamedTuple

EARTH_RADIUS = 6371008.8   # m: the mean radius


class Waypoint(NamedTuple):
    lat: float   # degrees
    lon: float   # degrees
    yaw: float   # rad, the direction to face: 0 = east, pi/2 = north


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'not a number: {value!r}')
    if not math.isfinite(value):
        raise ValueError(f'not a finite number: {value!r}')
    return float(value)


def _point(lat, lon):
    lat, lon = _number(lat), _number(lon)
    if abs(lat) > 90.0 or abs(lon) > 180.0:
        raise ValueError(f'not on the globe: lat {lat}, lon {lon}')
    return lat, lon


def parse_route(data):
    """
    Read a route as a list of (lat, lon). Raise ValueError if it isn't one.

    Takes what the app sends, [{'lat': .., 'lon': ..}, ...], or a whole OSRM response,
    {'routes': [{'geometry': {'coordinates': [[lon, lat], ...]}}]} (GeoJSON order).
    """
    if isinstance(data, dict):
        try:
            coords = data['routes'][0]['geometry']['coordinates']
            points = [_point(c[1], c[0]) for c in coords]
        except (KeyError, IndexError, TypeError):
            raise ValueError('not an OSRM route: needs routes[0].geometry.coordinates '
                             '(overview=full&geometries=geojson)') from None
    elif isinstance(data, list):
        try:
            points = [_point(p['lat'], p['lon']) for p in data]
        except (KeyError, TypeError):
            raise ValueError("each point needs 'lat' and 'lon'") from None
    else:
        raise ValueError('a route is a list of points, or an OSRM response')
    if not points:
        raise ValueError('the route has no points')
    return points


def distance(a, b):
    """Metres between two (lat, lon) points (haversine)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(min(1.0, h)))


def _east_north(origin, p):
    """Metres east and north of origin: a flat map, fine over a few km."""
    dlon = (p[1] - origin[1] + 540.0) % 360.0 - 180.0
    mean_lat = math.radians((p[0] + origin[0]) / 2)
    return (EARTH_RADIUS * math.radians(dlon) * math.cos(mean_lat),
            EARTH_RADIUS * math.radians(p[0] - origin[0]))


def bearing(a, b):
    """Yaw (ENU) of the direction from a to b."""
    east, north = _east_north(a, b)
    return math.atan2(north, east)


def _off_segment(p, a, b):
    """Metres from p to the segment a-b, all (east, north)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0
    if length2 > 0:
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def simplify(points, tolerance):
    """Keep the points where the route bends by more than tolerance metres."""
    if len(points) < 3 or tolerance <= 0:
        return list(points)
    xy = [_east_north(points[0], p) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    spans = [(0, len(points) - 1)]
    while spans:
        first, last = spans.pop()
        worst, index = 0.0, None
        for k in range(first + 1, last):
            off = _off_segment(xy[k], xy[first], xy[last])
            if off > worst:
                worst, index = off, k
        if index is not None and worst > tolerance:
            keep[index] = True
            spans += [(first, index), (index, last)]
    return [p for p, kept in zip(points, keep) if kept]


def space_out(points, min_spacing):
    """
    Drop points closer than min_spacing metres to the last point kept.

    The first and the last point always stay: the start and the destination.
    """
    if len(points) < 2:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        gap = distance(kept[-1], p)
        if gap >= min_spacing and gap > 0:
            kept.append(p)
    end = points[-1]
    if len(kept) > 1 and distance(kept[-1], end) < min_spacing:
        kept[-1] = end   # the destination replaces the point just before it
    elif distance(kept[-1], end) > 0 or len(kept) == 1:
        kept.append(end)
    return kept


def headings(points):
    """
    Give the yaw to face at each point: the average of the directions in and out.

    The first point faces out, the last one faces in. At a U-turn the two directions
    cancel, so that point faces out. A single point faces east (0).
    """
    yaws = []
    for i, p in enumerate(points):
        out = bearing(p, points[i + 1]) if i + 1 < len(points) else None
        into = bearing(points[i - 1], p) if i > 0 else None
        if out is None or into is None:
            yaws.append(out if out is not None else (into if into is not None else 0.0))
            continue
        x, y = math.cos(out) + math.cos(into), math.sin(out) + math.sin(into)
        yaws.append(math.atan2(y, x) if math.hypot(x, y) > 1e-6 else out)
    return yaws


def to_waypoints(points, tolerance=1.0, min_spacing=5.0):
    """
    Turn a route into GPS waypoints: simplified, spaced out, with headings.

    The route's first point is dropped: it is where the car is now. A route of one
    point is just its destination.
    """
    points = space_out(simplify(points, tolerance), min_spacing)
    waypoints = [Waypoint(lat, lon, yaw) for (lat, lon), yaw in zip(points, headings(points))]
    return waypoints[1:] if len(waypoints) > 1 else waypoints


def remaining(waypoints, index, position=None):
    """
    Metres left to drive: from the car to waypoint `index`, then along the rest.

    Without the car's position, only the part from waypoint `index` on.
    """
    if index >= len(waypoints):
        return 0.0
    total = sum(distance(waypoints[i][:2], waypoints[i + 1][:2])
                for i in range(index, len(waypoints) - 1))
    if position is not None:
        total += distance(position, waypoints[index][:2])
    return total


def quaternion(yaw):
    """(x, y, z, w) of a turn by yaw about z."""
    return 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)
