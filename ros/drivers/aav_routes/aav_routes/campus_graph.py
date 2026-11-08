"""
Directions on the campus: a road graph from the campus's OpenStreetMap file, and routes on it.

No ROS imports, so the tests run anywhere (docs/routes.md, "On the campus").

Why not Valhalla here: the campus is a few hundred roads, so a Python graph answers in
milliseconds, with no server and no tiles. It reads the very file that `pixi run campus`
builds Gazebo's world and Nav2's map from, with the same road kinds, so a route only uses
what Nav2's map marks free. Valhalla's car profile also avoids parking aisles and
private service roads, which is most of a campus.

    graph = CampusGraph.from_osm('maps/carla/carleton.osm', site['roads'])
    route = graph.route((45.3849, -75.6955), (45.3866, -75.6974))   # a StreetRoute

1. Read: every `highway=*` way whose kind the site file lets the car use, not in a tunnel,
   not `access=no`. One-way roads are kept one way.
2. Snap: the start and the destination go to the nearest point on any road (a foot of a
   perpendicular, not just a corner), within `max_snap` metres.
3. Search: Dijkstra over the corners, with the two snapped points as extra corners.

Positions are (lat, lon) in degrees. Lengths are metres.
"""

import heapq
import math
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

from aav_routes import route as geo
from aav_routes.osrm_route import RouteError, StreetRoute
import yaml

# The road kinds tools/campus_world.py draws as free on Nav2's map (its ROAD_WIDTHS).
DRAWN_ROADS = ('trunk', 'trunk_link', 'primary', 'primary_link', 'secondary',
               'secondary_link', 'tertiary', 'unclassified', 'residential', 'service')
MAX_SNAP = 60.0         # m: further than this from any road, no route
CLOSED = ('no', 'private_no')


class Snap(NamedTuple):
    """Where a point lands on the graph: on the segment a-b, a share t of the way along."""

    a: int              # corner indices
    b: int
    t: float
    lat: float
    lon: float
    off: float          # m from the point asked


class Place(NamedTuple):
    name: str
    lat: float
    lon: float
    kind: str           # building or parking
    stop: tuple = None  # (lat, lon) where the car pulls up, if the site file says


def target(place):
    """Return where a route to place ends: its stop, else its middle (snapped to a road)."""
    return tuple(place.stop) if place.stop else (place.lat, place.lon)


def _tags(element):
    return {t.get('k'): t.get('v') for t in element.iter('tag')}


def underground(tags):
    """Return True for a road under the ground or indoors: never the car's."""
    try:
        layer = int(tags.get('layer', '0'))
    except ValueError:
        layer = 0
    return (layer < 0 or tags.get('tunnel') not in (None, 'no') or tags.get('indoor') == 'yes'
            or tags.get('location') == 'underground')


def drivable(tags, roads):
    """Return True for a way the car may drive: a road kind in roads, open to cars."""
    return (tags.get('highway') in roads and not underground(tags)
            and tags.get('access') not in CLOSED
            and tags.get('motor_vehicle') not in CLOSED
            and tags.get('area') != 'yes')


def one_way(tags):
    """Return 1 (along the way), -1 (against it) or 0 (both ways)."""
    value = tags.get('oneway', 'no')
    if value in ('yes', 'true', '1'):
        return 1
    if value == '-1':
        return -1
    return 0


class Osm(NamedTuple):
    """What the routes need from an .osm file."""

    nodes: dict         # node id: (lat, lon)
    ways: dict          # way id: (tags, [node ids])
    relations: list     # (tags, [outer way ids])


def read_osm(path):
    """Read an .osm file into an Osm."""
    root = ElementTree.parse(path).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon')))
             for n in root.iter('node')}
    ways = {w.get('id'): (_tags(w), [nd.get('ref') for nd in w.iter('nd')])
            for w in root.iter('way')}
    relations = []
    for rel in root.iter('relation'):
        outer = [m.get('ref') for m in rel.iter('member')
                 if m.get('type') == 'way' and m.get('role') == 'outer']
        relations.append((_tags(rel), outer))
    return Osm(nodes, ways, relations)


def _mean(points):
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def places_from_osm(osm):
    """
    Every named building and parking lot: {name: Place}, at the middle of its corners.

    A lot is named by its `name`, else its `ref` ("P4"). Underground ones are left out.
    """
    out = {}

    def points_of(refs):
        return [osm.nodes[r] for r in refs if r in osm.nodes]

    for tags, refs in osm.ways.values():
        _add_place(out, tags, points_of(refs))
    for tags, outer in osm.relations:
        _add_place(out, tags, [p for ref in outer if ref in osm.ways
                               for p in points_of(osm.ways[ref][1])])
    return out


def _add_place(out, tags, points):
    if not points or underground(tags):
        return
    if tags.get('building', 'no') != 'no':
        kind = 'building'
    elif tags.get('amenity') == 'parking':
        kind = 'parking'
    else:
        return
    name = tags.get('name') or tags.get('ref')
    if not name or name.isdigit():
        return
    lat, lon = _mean(points[:-1] if len(points) > 1 and points[0] == points[-1] else points)
    out.setdefault(name, Place(name, lat, lon, kind))


def find_place(places, text):
    """
    Return the Place a person means, or raise RouteError saying what's close.

    Exact (any case) first, then the only name that starts with the text, then the only
    name that holds it: "mackenzie" finds "Mackenzie Building", "p4" finds "P4".
    """
    wanted = ' '.join(text.split()).casefold()
    if not wanted:
        raise RouteError('no place named')
    by_key = {name.casefold(): place for name, place in places.items()}
    if wanted in by_key:
        return by_key[wanted]
    for test in (str.startswith, str.__contains__):
        found = sorted({key for key in by_key if test(key, wanted)})
        if len(found) == 1:
            return by_key[found[0]]
        if found:
            names = ', '.join(by_key[k].name for k in found[:5])
            raise RouteError(f'{text!r} could be {names}: say which')
    raise RouteError(f'no place called {text!r} (pixi run campus-route --list)')


class CampusGraph:
    """The roads the car may use, as corners and one-way edges."""

    def __init__(self, points, edges):
        self.points = list(points)           # (lat, lon) of each corner
        self.edges = {i: {} for i in range(len(self.points))}   # i: {j: metres}
        self.segments = []                   # (i, j): each road piece once, for snapping
        seen = set()
        for i, j in edges:
            length = geo.distance(self.points[i], self.points[j])
            self.edges[i][j] = length
            if (j, i) not in seen:
                self.segments.append((i, j))
            seen.add((i, j))
        self.origin = self.points[0] if self.points else (0.0, 0.0)
        self.xy = [geo._east_north(self.origin, p) for p in self.points]

    @classmethod
    def from_osm(cls, path, roads=DRAWN_ROADS, oneway=True):
        """Build the graph from an .osm file, keeping only the road kinds in roads."""
        return cls.from_osm_data(read_osm(path), roads, oneway)

    @classmethod
    def from_osm_data(cls, osm, roads=DRAWN_ROADS, oneway=True):
        """Build the graph from read_osm's Osm; oneway=False drives one-way roads both ways."""
        nodes = osm.nodes
        index, points, edges = {}, [], []

        def corner(ref):
            if ref not in index:
                index[ref] = len(points)
                points.append(nodes[ref])
            return index[ref]

        for tags, refs in osm.ways.values():
            if not drivable(tags, roads):
                continue
            refs = [r for r in refs if r in nodes]
            direction = one_way(tags) if oneway else 0
            for r0, r1 in zip(refs, refs[1:]):
                a, b = corner(r0), corner(r1)
                if a == b:
                    continue
                if direction >= 0:
                    edges.append((a, b))
                if direction <= 0:
                    edges.append((b, a))
        return cls(points, edges)

    def __len__(self):
        return len(self.points)

    def snap(self, point, max_snap=MAX_SNAP):
        """Return the Snap on the nearest road to point (lat, lon); RouteError if none near."""
        if not self.segments:
            raise RouteError('the campus graph has no roads')
        p = geo._east_north(self.origin, point)
        best = None
        for a, b in self.segments:
            (ax, ay), (bx, by) = self.xy[a], self.xy[b]
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx
                                                            + (p[1] - ay) * dy) / length2))
            off = math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)
            if best is None or off < best[0]:
                best = (off, a, b, t)
        off, a, b, t = best
        if off > max_snap:
            raise RouteError(f'{off:.0f} m from the nearest road the car may use '
                             f'(more than {max_snap:.0f} m)')
        (la, oa), (lb, ob) = self.points[a], self.points[b]
        return Snap(a, b, t, la + (lb - la) * t, oa + (ob - oa) * t, off)

    def _ends(self, snap):
        """Return the corners a snapped point leaves to and arrives from, with metres."""
        ab = self.edges[snap.a].get(snap.b)
        ba = self.edges[snap.b].get(snap.a)
        length = ab if ab is not None else ba
        leave, arrive = [], []      # (corner, metres)
        if ab is not None:          # a -> b: the point leaves towards b, is reached from a
            leave.append((snap.b, (1.0 - snap.t) * length))
            arrive.append((snap.a, snap.t * length))
        if ba is not None:
            leave.append((snap.a, snap.t * length))
            arrive.append((snap.b, (1.0 - snap.t) * length))
        return leave, arrive

    def route(self, start, end, speed=1.0, max_snap=MAX_SNAP):
        """
        Return the shortest drive from start to end, both (lat, lon), as a StreetRoute.

        duration is length / speed (m/s): the car's own speed, not a normal car's.
        RouteError if either end is far from a road, or no road joins them.
        """
        s, e = self.snap(start, max_snap), self.snap(end, max_snap)
        start_id, end_id = -1, -2
        leave, _ = self._ends(s)
        _, arrive = self._ends(e)
        into_end = dict(arrive)
        best, before = {start_id: 0.0}, {}
        queue, count = [(0.0, 0, start_id)], 1
        # Both on the same road piece: straight along it, if its direction allows.
        if (s.a, s.b) == (e.a, e.b):
            along = self._along(s, e)
            if along is not None:
                best[end_id], before[end_id] = along, start_id
                heapq.heappush(queue, (along, count, end_id))
        while queue:
            cost, _, here = heapq.heappop(queue)
            if here == end_id:
                break
            if cost > best.get(here, math.inf):
                continue
            nexts = leave if here == start_id else list(self.edges[here].items())
            if here in into_end:
                nexts = nexts + [(end_id, into_end[here])]
            for there, length in nexts:
                total = cost + length
                if total < best.get(there, math.inf):
                    best[there], before[there] = total, here
                    count += 1
                    heapq.heappush(queue, (total, count, there))
        if end_id not in best:
            raise RouteError('no road the car may use joins these two places')
        corners, here = [], end_id
        while here != start_id:
            here = before[here]
            if here != start_id:
                corners.append(here)
        corners.reverse()
        points = [(s.lat, s.lon)] + [self.points[i] for i in corners] + [(e.lat, e.lon)]
        points = [p for k, p in enumerate(points) if k == 0 or p != points[k - 1]]
        if len(points) < 2:
            points = points * 2
        length = best[end_id]
        return StreetRoute(points, length, length / max(speed, 1e-3))

    def _along(self, s, e):
        """Metres from s to e on their one road piece, if its direction allows; else None."""
        length = self.edges[s.a].get(s.b) or self.edges[s.b].get(s.a)
        if e.t >= s.t and s.b in self.edges[s.a]:
            return (e.t - s.t) * length
        if e.t <= s.t and s.a in self.edges[s.b]:
            return (s.t - e.t) * length
        return None

    def parts(self):
        """Return how many separate road networks there are (1 means all joined)."""
        neighbours = {i: set(js) for i, js in self.edges.items()}
        for i, js in self.edges.items():
            for j in js:
                neighbours[j].add(i)
        seen, count = set(), 0
        for i in neighbours:
            if i in seen:
                continue
            count += 1
            stack = [i]
            while stack:
                k = stack.pop()
                if k not in seen:
                    seen.add(k)
                    stack.extend(neighbours[k] - seen)
        return count


class Site(NamedTuple):
    """The site file's parts that directions use (config/campus_site.yaml)."""

    datum: tuple        # (lat, lon): must be navsat.yaml's
    osm: str            # the .osm file, relative to the repo's root
    roads: tuple        # highway kinds the car may use
    oneway: bool
    max_snap: float
    places: dict        # name: Place
    aliases: dict       # OpenStreetMap's name: the site file's, for the same place


def read_site(path):
    """Read a site file into a Site; ValueError if a part is missing or wrong."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    try:
        places = {}
        for entry in data.get('places') or []:
            stop = entry.get('stop')
            places[entry['name']] = Place(
                entry['name'], float(entry['lat']), float(entry['lon']),
                entry.get('kind', 'building'),
                (float(stop[0]), float(stop[1])) if stop else None)
        osm_names = {e['osm']: e['name'] for e in data.get('places') or [] if e.get('osm')}
        return Site(tuple(float(v) for v in data['datum'][:2]), str(data['osm']),
                    tuple(data.get('roads') or DRAWN_ROADS), bool(data.get('oneway', True)),
                    float(data.get('max_snap', MAX_SNAP)), places, osm_names)
    except (KeyError, TypeError, IndexError) as e:
        raise ValueError(f'{path}: not a site file ({e})') from None


class Campus:
    """The graph and the places: everything directions need, from a site file and its .osm."""

    def __init__(self, site_path, root='.'):
        site = read_site(site_path)
        osm_path = Path(root) / site.osm
        if not osm_path.exists():
            raise RouteError(f'no {site.osm}: make it with pixi run campus')
        osm = read_osm(osm_path)
        self.site = site
        self.graph = CampusGraph.from_osm_data(osm, site.roads, site.oneway)
        # OpenStreetMap's names, then the site file's on top; an alias is replaced.
        self.places = {name: place for name, place in places_from_osm(osm).items()
                       if name not in site.aliases}
        self.places.update(site.places)

    def find(self, text):
        """Return the Place a person means (find_place)."""
        return find_place(self.places, text)

    def route(self, start, end, speed=1.0):
        """Route from start to end, both (lat, lon): CampusGraph.route with the site's snap."""
        return self.graph.route(start, end, speed, self.site.max_snap)
