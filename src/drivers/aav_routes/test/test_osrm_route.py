"""
Tests for osrm_route.py: a router's answer to Nav2 GPS waypoints.

The fixtures are real answers for one route, Carleton (45.3876, -75.6960) to Lansdowne
(45.3983, -75.6838), recorded on 16 Oct 2026:
- valhalla_*.json: our router, Valhalla 3.9.1 (pixi run -e routes router), on BBBike's
  Ottawa extract of 10 Oct 2026; polyline6 and GeoJSON;
- osrm_carleton_lansdowne.json: OSRM's public demo server, asked once by hand, to check
  that the parser reads OSRM itself (never used by the code);
- valhalla_too_far.json: Valhalla's answer for a destination in another continent.
Route data © OpenStreetMap contributors, ODbL.
"""

import json
import math
from pathlib import Path

from aav_routes import osrm_route
import pytest

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
CARLETON = (45.3876, -75.6960)
LANSDOWNE = (45.3983, -75.6838)


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def moved(p, east, north):
    """Return the point `east` and `north` metres from p."""
    r = osrm_route.geo.EARTH_RADIUS
    return (p[0] + math.degrees(north / r),
            p[1] + math.degrees(east / (r * math.cos(math.radians(p[0])))))


def along(points):
    return sum(osrm_route.distance(a, b) for a, b in zip(points, points[1:]))


# --- the request ---

def test_valhalla_request_asks_for_osrms_json():
    r = osrm_route.request('valhalla', 'http://127.0.0.1:8002/', CARLETON, LANSDOWNE)
    assert r.url == 'http://127.0.0.1:8002/route'
    assert r.body['format'] == 'osrm'
    assert r.body['shape_format'] == 'polyline6'
    assert r.body['costing'] == 'auto'
    assert r.body['locations'] == [{'lat': 45.3876, 'lon': -75.696},
                                   {'lat': 45.3983, 'lon': -75.6838}]


def test_osrm_request_is_lon_lat():
    r = osrm_route.request('osrm', 'http://127.0.0.1:5000', CARLETON, LANSDOWNE)
    assert r.body is None
    assert r.url.startswith('http://127.0.0.1:5000/route/v1/driving/'
                            '-75.6960000,45.3876000;-75.6838000,45.3983000?')
    assert 'geometries=polyline6' in r.url and 'overview=full' in r.url


@pytest.mark.parametrize('router, start', [
    ('google', CARLETON), ('osrm', (91.0, 0.0)), ('valhalla', (math.nan, 0.0))])
def test_bad_requests_raise(router, start):
    with pytest.raises(ValueError):
        osrm_route.request(router, 'http://x', start, LANSDOWNE)


# --- the polyline ---

def test_decode_googles_example():
    # Google's own example, at 5 decimal places.
    points = osrm_route.decode_polyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@', 5)
    assert points == pytest.approx([(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)])


@pytest.mark.parametrize('bad', ['_p~iF~ps|', '_p~iF', '_p~iF~ps|U ', 42])
def test_bad_polylines_raise(bad):
    with pytest.raises(osrm_route.RouteError):
        osrm_route.decode_polyline(bad, 5)


# --- the answer ---

def test_parse_valhallas_answer():
    route = osrm_route.parse_response(fixture('valhalla_carleton_lansdowne.json'))
    assert route.length == pytest.approx(1986.949)
    assert route.duration == pytest.approx(241.981)
    # It starts and ends on the street nearest each place (the snapped "waypoints").
    assert route.points[0] == pytest.approx((45.387641, -75.695661))
    assert route.points[-1] == pytest.approx((45.397983, -75.684669))
    # The shape's own length is the router's.
    assert along(route.points) == pytest.approx(route.length, rel=0.01)


def test_geojson_and_polyline_agree():
    a = osrm_route.parse_response(fixture('valhalla_carleton_lansdowne.json'))
    b = osrm_route.parse_response(fixture('valhalla_carleton_lansdowne_geojson.json'))
    assert len(a.points) == len(b.points)
    assert a.points == pytest.approx(b.points, abs=1e-6)


def test_osrm_itself_gives_the_same_route():
    osrm = osrm_route.parse_response(fixture('osrm_carleton_lansdowne.json'))
    valhalla = osrm_route.parse_response(fixture('valhalla_carleton_lansdowne.json'))
    assert osrm.length == pytest.approx(valhalla.length, abs=5.0)
    assert osrm.points[-1] == pytest.approx(valhalla.points[-1], abs=1e-5)


def test_no_route_says_why():
    with pytest.raises(osrm_route.RouteError, match='DistanceExceeded'):
        osrm_route.parse_response(fixture('valhalla_too_far.json'))


@pytest.mark.parametrize('bad', [
    None, [], {'routes': []}, {'code': 'NoRoute'},
    {'routes': [{'distance': 1, 'duration': 1, 'geometry': {'type': 'LineString'}}]},
    {'routes': [{'distance': 1, 'duration': 1,
                 'geometry': {'coordinates': [[-75.0, 45.0]]}}]},
    {'routes': [{'distance': 1, 'duration': 1,
                 'geometry': {'coordinates': [[-75.0, 95.0], [-75.0, 45.0]]}}]},
    {'routes': [{'geometry': {'coordinates': [[-75.0, 45.0], [-75.0, 45.1]]}}]},
])
def test_bad_answers_raise(bad):
    with pytest.raises(osrm_route.RouteError):
        osrm_route.parse_response(bad)


# --- the waypoints ---

def test_fill_in_splits_long_stretches():
    a, b = CARLETON, moved(CARLETON, 100, 0)
    points = osrm_route.fill_in([a, b], 30.0)
    assert len(points) == 5              # 4 pieces of 25 m
    gaps = [osrm_route.distance(p, q) for p, q in zip(points, points[1:])]
    assert gaps == pytest.approx([25.0] * 4, abs=0.01)
    assert osrm_route.fill_in([a, b], 0) == [a, b]


def test_waypoints_are_spaced_for_nav2():
    route = osrm_route.parse_response(fixture('valhalla_carleton_lansdowne.json'))
    wps = osrm_route.waypoints(route.points, tolerance=1.0, min_spacing=10.0,
                               max_spacing=30.0)
    points = [route.points[0]] + [(w.lat, w.lon) for w in wps]
    gaps = [osrm_route.distance(p, q) for p, q in zip(points, points[1:])]
    assert max(gaps) <= 30.0 + 1e-6
    assert min(gaps[:-1]) >= 10.0 - 1e-6       # the last may be shorter: the destination
    assert (wps[-1].lat, wps[-1].lon) == pytest.approx(route.points[-1])
    # Cutting corners by at most the tolerance keeps the length.
    assert along(points) == pytest.approx(route.length, rel=0.02)
    assert 60 <= len(wps) <= 200


def test_waypoints_face_along_the_street():
    # 100 m east, then 100 m north.
    points = [CARLETON, moved(CARLETON, 100, 0), moved(CARLETON, 100, 100)]
    wps = osrm_route.waypoints(points, min_spacing=10.0, max_spacing=50.0)
    assert len(wps) == 4
    assert wps[0].yaw == pytest.approx(0.0, abs=1e-3)             # east
    assert wps[1].yaw == pytest.approx(math.pi / 4, abs=1e-3)     # the corner
    assert wps[-1].yaw == pytest.approx(math.pi / 2, abs=1e-3)    # north


def test_spacing_must_make_sense():
    with pytest.raises(ValueError):
        osrm_route.waypoints([CARLETON, LANSDOWNE], min_spacing=40.0, max_spacing=30.0)


def test_summary():
    route = osrm_route.StreetRoute([CARLETON, LANSDOWNE], 1986.949, 241.981)
    assert osrm_route.summary(route, 67) == (
        'route: 1.99 km, about 4 min for a normal car, 67 waypoints')
