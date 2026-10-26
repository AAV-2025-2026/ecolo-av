"""Tests for route.py: the app's route to Nav2's GPS waypoints."""

import math

from aav_routes import route
import pytest

START = (45.3860, -75.6960)     # the navsat datum: Carleton


def moved(p, east, north):
    """Return the point `east` and `north` metres from p."""
    lat = p[0] + math.degrees(north / route.EARTH_RADIUS)
    lon = p[1] + math.degrees(east / (route.EARTH_RADIUS * math.cos(math.radians(p[0]))))
    return lat, lon


def l_shape(step=2):
    """100 m east, then 100 m north: a point every `step` metres."""
    east = [moved(START, x, 0) for x in range(0, 101, step)]
    north = [moved(START, 100, y) for y in range(step, 101, step)]
    return east + north


def test_parse_the_apps_route():
    data = [{'lat': 45.386, 'lon': -75.696}, {'lat': 45, 'lon': -75}]
    assert route.parse_route(data) == [(45.386, -75.696), (45.0, -75.0)]


def test_parse_an_osrm_response():
    data = {'routes': [{'geometry': {'coordinates': [[-75.696, 45.386], [-75.695, 45.387]]}}]}
    assert route.parse_route(data) == [(45.386, -75.696), (45.387, -75.695)]


@pytest.mark.parametrize('bad', [
    None, 'a string', [], {}, {'routes': []}, [1, 2],
    [{'lat': 45.0}],
    [{'lat': '45', 'lon': -75.0}],
    [{'lat': True, 'lon': -75.0}],
    [{'lat': 91.0, 'lon': 0.0}],
    [{'lat': math.nan, 'lon': 0.0}],
])
def test_bad_routes_raise(bad):
    with pytest.raises(ValueError):
        route.parse_route(bad)


def test_distance():
    # A degree of latitude is about 111.2 km.
    assert route.distance((45.0, -75.0), (46.0, -75.0)) == pytest.approx(111195, rel=1e-3)
    assert route.distance(START, moved(START, 30, 40)) == pytest.approx(50.0, abs=0.01)


def test_bearing_is_enu():
    assert route.bearing(START, moved(START, 10, 0)) == pytest.approx(0.0, abs=1e-6)
    assert route.bearing(START, moved(START, 0, 10)) == pytest.approx(math.pi / 2, abs=1e-6)
    assert abs(route.bearing(START, moved(START, -10, 0))) == pytest.approx(math.pi, abs=1e-6)
    assert route.bearing(START, moved(START, 0, -10)) == pytest.approx(-math.pi / 2, abs=1e-6)


def test_simplify_keeps_only_the_corner():
    points = l_shape()
    assert route.simplify(points, 1.0) == [points[0], points[50], points[-1]]


def test_simplify_keeps_bends_bigger_than_the_tolerance():
    points = [START, moved(START, 50, 3), moved(START, 100, 0)]
    assert route.simplify(points, 1.0) == points
    assert route.simplify(points, 5.0) == [points[0], points[-1]]


def test_space_out():
    points = [moved(START, x, 0) for x in range(0, 21)]     # every metre for 20 m
    # 4.9, not 5: five steps of 1 m east are a hair under 5 m on a great circle.
    assert route.space_out(points, 4.9) == points[::5]


def test_space_out_keeps_the_destination():
    points = [moved(START, x, 0) for x in (0, 5, 10, 12)]
    # 12 is too close to 10: the destination takes its place.
    assert route.space_out(points, 4.9) == [points[0], points[1], points[3]]
    assert route.space_out(points[:2], 50.0) == points[:2]


def test_headings_follow_the_route():
    points = [START, moved(START, 50, 0), moved(START, 50, 50)]
    assert route.headings(points) == pytest.approx([0.0, math.pi / 4, math.pi / 2], abs=1e-4)


def test_a_u_turn_faces_the_way_out():
    points = [START, moved(START, 50, 0), START]
    assert abs(route.headings(points)[1]) == pytest.approx(math.pi, abs=1e-4)


def test_one_point_faces_east():
    assert route.headings([START]) == [0.0]


def test_to_waypoints_drops_the_start():
    waypoints = route.to_waypoints(l_shape(), tolerance=1.0, min_spacing=5.0)
    assert len(waypoints) == 2
    corner, end = waypoints
    assert (corner.lat, corner.lon) == pytest.approx(moved(START, 100, 0))
    assert corner.yaw == pytest.approx(math.pi / 4, abs=1e-3)
    assert (end.lat, end.lon) == pytest.approx(moved(START, 100, 100))
    assert end.yaw == pytest.approx(math.pi / 2, abs=1e-3)


def test_short_routes_keep_the_destination():
    assert route.to_waypoints([START]) == [route.Waypoint(*START, 0.0)]
    north = moved(START, 0, 30)
    [only] = route.to_waypoints([START, north])
    assert (only.lat, only.lon) == north
    assert only.yaw == pytest.approx(math.pi / 2)
    near = moved(START, 1, 0)       # closer than the spacing
    assert [(w.lat, w.lon) for w in route.to_waypoints([START, near])] == [near]


def test_remaining():
    waypoints = route.to_waypoints(l_shape())
    assert route.remaining(waypoints, 0, START) == pytest.approx(200.0, abs=0.1)
    assert route.remaining(waypoints, 0) == pytest.approx(100.0, abs=0.1)
    assert route.remaining(waypoints, 1, moved(START, 100, 40)) == pytest.approx(60.0, abs=0.1)
    assert route.remaining(waypoints, 2, START) == 0.0


def test_quaternion():
    assert route.quaternion(0.0) == (0.0, 0.0, 0.0, 1.0)
    assert route.quaternion(math.pi / 2) == pytest.approx(
        (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5)))
