"""
A street route from a router, as GPS waypoints spaced for Nav2.

No ROS imports, so the tests run anywhere (docs/routes.md).

The router answers in OSRM's JSON: OSRM itself does, and Valhalla does when asked
("format": "osrm"). So one parser takes either:

    {"code": "Ok", "routes": [{"distance": m, "duration": s, "geometry": ...}]}

The geometry is a GeoJSON LineString ([lon, lat] pairs) or an encoded polyline (Google's
format, 5 or 6 decimal places). The route is then cut into waypoints for Nav2's
follow_gps_waypoints, which drives to each in turn:

1. simplify: keep the points where the street bends (aav_hud's route.py);
2. space out: no two waypoints closer than min_spacing (it slows at each one);
3. fill in: no two further apart than max_spacing, so each goal stays near the car,
   inside Nav2's costmaps;
4. a heading along the route at each one; the first point, where the car is, is dropped.

Positions are (lat, lon) in degrees; yaw is ENU (0 = east, pi/2 = north), as REP-103.
"""

import math
from typing import NamedTuple

from aav_hud import route as geo

Waypoint = geo.Waypoint
distance = geo.distance

ROUTERS = ('valhalla', 'osrm')
PRECISION = 6       # decimal places of the encoded polyline we ask for (polyline6)


class RouteError(ValueError):
    """The router found no route, or its answer isn't one."""


class StreetRoute(NamedTuple):
    points: list        # (lat, lon), start to destination, along the streets
    length: float       # m, the router's own sum
    duration: float     # s, the router's guess for a normal car: not ours


class Request(NamedTuple):
    url: str
    body: dict = None   # JSON to POST; None for a GET


def _lat_lon(p):
    lat, lon = (float(v) for v in p)
    if not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > 90 or abs(lon) > 180:
        raise ValueError(f'not on the globe: lat {lat}, lon {lon}')
    return lat, lon


def request(router, base_url, start, end, costing='auto'):
    """
    Make the request for a route from start to end, both (lat, lon).

    valhalla: POST <base>/route, OSRM's JSON back, polyline6, no turn-by-turn text.
    osrm: GET <base>/route/v1/driving/<lon,lat;lon,lat>, the whole shape as polyline6.
    """
    (lat0, lon0), (lat1, lon1) = _lat_lon(start), _lat_lon(end)
    base = base_url.rstrip('/')
    if router == 'valhalla':
        return Request(f'{base}/route', {
            'locations': [{'lat': lat0, 'lon': lon0}, {'lat': lat1, 'lon': lon1}],
            'costing': costing,
            'format': 'osrm',
            'shape_format': f'polyline{PRECISION}',
            'directions_type': 'none',
        })
    if router == 'osrm':
        return Request(f'{base}/route/v1/driving/{lon0:.7f},{lat0:.7f};{lon1:.7f},{lat1:.7f}'
                       f'?overview=full&geometries=polyline{PRECISION}&steps=false')
    raise ValueError(f'unknown router {router!r}: one of {ROUTERS}')


def decode_polyline(text, precision=PRECISION):
    """
    Decode an encoded polyline into (lat, lon) points.

    Each number is a difference from the one before, times 10^precision, zig-zag
    signed, in 5-bit chunks offset by 63 (Google's polyline algorithm).
    """
    if not isinstance(text, str):
        raise RouteError('an encoded polyline is a string')
    scale = 10.0 ** precision
    numbers, value, shift = [], 0, 0
    for char in text:
        chunk = ord(char) - 63
        if not 0 <= chunk < 64:
            raise RouteError(f'not an encoded polyline: {char!r}')
        value |= (chunk & 0x1F) << shift
        shift += 5
        if chunk < 0x20:
            numbers.append(~(value >> 1) if value & 1 else value >> 1)
            value, shift = 0, 0
    if shift or len(numbers) % 2:
        raise RouteError('the encoded polyline stops part way')
    points, lat, lon = [], 0, 0
    for dlat, dlon in zip(numbers[::2], numbers[1::2]):
        lat, lon = lat + dlat, lon + dlon
        points.append((lat / scale, lon / scale))
    return points


def _geometry(geometry, precision):
    if isinstance(geometry, str):
        return decode_polyline(geometry, precision)
    try:
        return [(c[1], c[0]) for c in geometry['coordinates']]
    except (KeyError, IndexError, TypeError):
        raise RouteError('the geometry is neither GeoJSON nor a polyline') from None


def parse_response(data, precision=PRECISION):
    """Read the router's answer (parsed JSON) as a StreetRoute; RouteError if none."""
    if not isinstance(data, dict):
        raise RouteError('not a router answer')
    code = data.get('code', 'Ok')
    if code != 'Ok':
        raise RouteError(f"{code}: {data.get('message', 'no route')}")
    try:
        best = data['routes'][0]
        points = [_lat_lon(p) for p in _geometry(best['geometry'], precision)]
        length, duration = float(best['distance']), float(best['duration'])
    except (KeyError, IndexError, TypeError):
        raise RouteError('no route in the answer') from None
    except ValueError as e:
        raise RouteError(str(e)) from None
    if len(points) < 2:
        raise RouteError('the route has fewer than two points')
    return StreetRoute(points, length, duration)


def fill_in(points, max_spacing):
    """Add points along each straight stretch longer than max_spacing metres."""
    if max_spacing <= 0 or not points:
        return list(points)
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        pieces = math.ceil(distance(a, b) / max_spacing)
        out += [(a[0] + (b[0] - a[0]) * k / pieces, a[1] + (b[1] - a[1]) * k / pieces)
                for k in range(1, pieces)]
        out.append(b)
    return out


def waypoints(points, tolerance=1.0, min_spacing=10.0, max_spacing=30.0):
    """
    Turn a route's points into Nav2 GPS waypoints, each with a heading.

    Neighbours end up between min_spacing and max_spacing metres apart, except at the
    end, where the destination takes the place of a point too close to it. The start,
    where the car is, isn't a waypoint.
    """
    if min_spacing > max_spacing > 0:
        raise ValueError('min_spacing is more than max_spacing')
    kept = fill_in(geo.space_out(geo.simplify(points, tolerance), min_spacing), max_spacing)
    out = [Waypoint(lat, lon, yaw) for (lat, lon), yaw in zip(kept, geo.headings(kept))]
    return out[1:] if len(out) > 1 else out


def summary(route, count):
    """One line for people: the length, the router's time, the waypoints."""
    minutes = route.duration / 60.0
    return (f'route: {route.length / 1000.0:.2f} km, about {minutes:.0f} min for a normal '
            f'car, {count} waypoints')
