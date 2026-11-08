"""
Test campus_graph: the campus's road graph, its places, and routes on it. No ROS.

A tiny made-up map, drawn in metres from a corner and written as an .osm file:

        D ------------- C          A-B-C: a road, 200 m then 100 m
        |               |          A-D-C: a road, 100 m then 200 m, but D-C is one way, C to D
        |               |          B-E: a footway (never the car's)
        A ------ B ---- C'         F-G: a tunnel; H-I: access=no
                 |                 J-K: a road on its own, 1 km east
                 E

The real campus (config/campus_site.yaml and maps/carla/carleton.osm) is checked last, when
pixi run campus has downloaded the map.
"""

import math
from pathlib import Path

from aav_routes import campus_graph as cg
from aav_routes import osrm_route
import pytest
import yaml

ORIGIN = (45.3860, -75.6960)
M_LAT = 1.0 / 111_195.0                                  # degrees of latitude per metre
M_LON = M_LAT / math.cos(math.radians(ORIGIN[0]))        # degrees of longitude per metre
PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parent.parent.parent
SITE = PACKAGE / 'config' / 'campus_site.yaml'
NAVSAT = ROOT / 'ros' / 'localization' / 'aav_localization' / 'config' / 'navsat.yaml'


def ll(east, north):
    """(lat, lon) of a point east and north of ORIGIN, m."""
    return ORIGIN[0] + north * M_LAT, ORIGIN[1] + east * M_LON


NODES = {'A': (0, 0), 'B': (200, 0), 'C': (300, 0), 'D': (0, 100), 'E': (200, -100),
         'F': (0, -50), 'G': (300, -50), 'H': (0, -60), 'I': (300, -60),
         'J': (1300, 0), 'K': (1400, 0),
         'b1': (50, 30), 'b2': (90, 30), 'b3': (90, 60), 'b4': (50, 60),
         'p1': (220, 10), 'p2': (260, 10), 'p3': (260, 40),
         'r1': (500, 500), 'r2': (520, 500), 'r3': (520, 520)}
WAYS = [
    ('1', ['A', 'B', 'C'], {'highway': 'service'}),
    ('2', ['A', 'D'], {'highway': 'residential'}),
    ('3', ['C', 'D'], {'highway': 'residential', 'oneway': 'yes'}),
    ('4', ['B', 'E'], {'highway': 'footway'}),
    ('5', ['F', 'G'], {'highway': 'tertiary', 'tunnel': 'yes'}),
    ('6', ['H', 'I'], {'highway': 'service', 'access': 'no'}),
    ('7', ['J', 'K'], {'highway': 'service'}),
    ('8', ['b1', 'b2', 'b3', 'b4', 'b1'], {'building': 'university', 'name': 'Minto Hall'}),
    ('9', ['p1', 'p2', 'p3', 'p1'], {'amenity': 'parking', 'ref': 'P4'}),
    ('10', ['r1', 'r2', 'r3', 'r1'], {}),
]
RELATION = {'building': 'yes', 'name': 'Mackenzie Building', 'type': 'multipolygon'}


def write_osm(path):
    lines = ["<?xml version='1.0'?>", "<osm version='0.6'>"]
    for name, (east, north) in NODES.items():
        lat, lon = ll(east, north)
        lines.append(f"<node id='{name}' lat='{lat:.9f}' lon='{lon:.9f}'/>")
    for way_id, refs, tags in WAYS:
        lines.append(f"<way id='{way_id}'>")
        lines += [f"<nd ref='{r}'/>" for r in refs]
        lines += [f"<tag k='{k}' v='{v}'/>" for k, v in tags.items()]
        lines.append('</way>')
    lines.append("<relation id='1'><member type='way' ref='10' role='outer'/>")
    lines += [f"<tag k='{k}' v='{v}'/>" for k, v in RELATION.items()]
    lines += ['</relation>', '</osm>']
    path.write_text('\n'.join(lines))
    return path


@pytest.fixture
def osm(tmp_path):
    return cg.read_osm(write_osm(tmp_path / 'tiny.osm'))


@pytest.fixture
def graph(osm):
    return cg.CampusGraph.from_osm_data(osm)


def test_only_roads_the_car_may_use(graph):
    # A, B, C, D and J, K: no footway, tunnel or closed road.
    assert len(graph) == 6
    assert graph.parts() == 2


def test_snap_lands_on_the_road_not_a_corner(graph):
    snap = graph.snap(ll(120, 7))
    assert snap.off == pytest.approx(7.0, abs=0.05)
    assert cg.geo.distance((snap.lat, snap.lon), ll(120, 0)) < 0.05


def test_too_far_from_any_road(graph):
    with pytest.raises(osrm_route.RouteError, match='from the nearest road'):
        graph.snap(ll(150, -40), max_snap=20)    # the tunnel at -50 is no road


def test_the_shortest_way_and_one_way_streets(graph):
    # A to C: 300 m along A-B-C; A-D-C would be 100 + 316 m, and D-C is one way anyway.
    there = graph.route(ll(0, 0), ll(300, 0), speed=2.0)
    assert there.length == pytest.approx(300.0, abs=0.5)
    assert there.duration == pytest.approx(150.0, abs=0.5)
    # D to C must go round by A (D-C is one way, C to D): 100 + 300 m.
    back = graph.route(ll(0, 100), ll(300, 0))
    assert back.length == pytest.approx(400.0, abs=0.5)
    # C to D may use the one-way road: about 316 m.
    assert graph.route(ll(300, 0), ll(0, 100)).length == pytest.approx(316.2, abs=0.5)


def test_one_way_off(osm):
    both_ways = cg.CampusGraph.from_osm_data(osm, oneway=False)
    assert both_ways.route(ll(0, 100), ll(300, 0)).length == pytest.approx(316.2, abs=0.5)


def test_start_and_end_part_way_along_roads(graph):
    route = graph.route(ll(50, 3), ll(250, -4))
    assert route.length == pytest.approx(200.0, abs=0.5)
    assert route.points[0] == pytest.approx(ll(50, 0), abs=1e-7)
    assert route.points[-1] == pytest.approx(ll(250, 0), abs=1e-7)
    assert ll(200, 0) == pytest.approx(route.points[1], abs=1e-7)    # by corner B


def test_both_ends_on_one_road_piece(graph):
    ahead = graph.route(ll(20, 0), ll(80, 0))
    assert ahead.length == pytest.approx(60.0, abs=0.2)
    assert len(ahead.points) == 2
    # On the one-way piece, against its way: round by A.
    d_to_c = cg.geo.distance(ll(0, 100), ll(300, 0))
    against = graph.route(ll(30, 90), ll(270, 10))
    assert against.length > d_to_c


def test_no_road_joins_them(graph):
    with pytest.raises(osrm_route.RouteError, match='joins'):
        graph.route(ll(0, 0), ll(1350, 0))


def test_a_route_cuts_into_nav2_waypoints(graph):
    route = graph.route(ll(0, 100), ll(300, 0))
    points = osrm_route.waypoints(route.points, 1.0, 10.0, 30.0)
    gaps = [cg.geo.distance(a, b) for a, b in zip(points, points[1:])]
    assert all(10.0 - 0.01 <= gap <= 30.0 + 0.01 for gap in gaps)
    assert (points[-1].lat, points[-1].lon) == pytest.approx(ll(300, 0), abs=1e-7)
    assert points[0].yaw == pytest.approx(-math.pi / 2, abs=0.01)     # south, from D to A


def test_places_from_osm(osm):
    places = cg.places_from_osm(osm)
    assert set(places) == {'Minto Hall', 'P4', 'Mackenzie Building'}
    minto = places['Minto Hall']
    assert minto.kind == 'building'
    assert (minto.lat, minto.lon) == pytest.approx(ll(70, 45), abs=1e-7)
    assert places['P4'].kind == 'parking'


@pytest.mark.parametrize('text, name', [
    ('Minto Hall', 'Minto Hall'), ('minto', 'Minto Hall'), ('  p4 ', 'P4'),
    ('kenzie', 'Mackenzie Building')])
def test_find_place(osm, text, name):
    assert cg.find_place(cg.places_from_osm(osm), text).name == name


def test_find_place_says_why_not(osm):
    places = cg.places_from_osm(osm)
    with pytest.raises(osrm_route.RouteError, match='no place called'):
        cg.find_place(places, 'Tory')
    with pytest.raises(osrm_route.RouteError, match='say which'):
        cg.find_place(places, 'n')     # Minto Hall, Mackenzie Building


def test_a_site_file(tmp_path):
    write_osm(tmp_path / 'tiny.osm')
    (tmp_path / 'site.yaml').write_text(yaml.safe_dump({
        'datum': list(ORIGIN), 'osm': 'tiny.osm', 'roads': ['service'], 'max_snap': 30,
        'places': [{'name': 'Minto', 'kind': 'building', 'lat': ll(70, 45)[0],
                    'lon': ll(70, 45)[1], 'osm': 'Minto Hall', 'stop': list(ll(70, 0))}]}))
    campus = cg.Campus(tmp_path / 'site.yaml', tmp_path)
    assert len(campus.graph) == 5       # service only: A, B, C and J, K
    assert 'Minto Hall' not in campus.places       # the site file's name replaces it
    minto = campus.find('minto')
    assert cg.target(minto) == pytest.approx(ll(70, 0))
    assert campus.route(ll(0, 0), cg.target(minto)).length == pytest.approx(70.0, abs=0.2)


def test_a_site_file_with_no_map(tmp_path):
    (tmp_path / 'site.yaml').write_text(yaml.safe_dump({'datum': list(ORIGIN),
                                                        'osm': 'missing.osm'}))
    with pytest.raises(osrm_route.RouteError, match='pixi run campus'):
        cg.Campus(tmp_path / 'site.yaml', tmp_path)


def test_campus_site_is_on_navsats_datum():
    site = cg.read_site(SITE)
    navsat = yaml.safe_load(NAVSAT.read_text())['navsat_transform']['ros__parameters']
    assert site.datum == pytest.approx(tuple(navsat['datum'][:2]))
    assert not set(site.roads) - set(cg.DRAWN_ROADS)   # only what Nav2's map has free
    assert {'Mackenzie Building', 'P4'} <= set(site.places)


CARLETON_OSM = ROOT / cg.read_site(SITE).osm


@pytest.mark.skipif(not CARLETON_OSM.exists(), reason='pixi run campus downloads the map')
def test_every_campus_place_has_a_route_from_p4():
    campus = cg.Campus(SITE, ROOT)
    start = cg.target(campus.find('P4'))
    for place in campus.site.places.values():
        route = campus.route(start, cg.target(place))
        assert route.length < 3000.0, place.name
