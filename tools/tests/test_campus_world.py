"""campus_world: reading the map, cutting shapes into triangles, kerbs, and the grid."""

import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campus_world as c  # noqa: E402, I100

OSM = """<osm>
 <node id="1" lat="0" lon="0"/><node id="2" lat="0" lon="10"/>
 <node id="3" lat="10" lon="10"/><node id="4" lat="10" lon="0"/>
 <node id="5" lat="5" lon="5"><tag k="natural" v="tree"/></node>
 <node id="6" lat="20" lon="0"/><node id="7" lat="20" lon="10"/>
 <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/>
   <tag k="amenity" v="parking"/><tag k="name" v="P4"/></way>
 <way id="11"><nd ref="6"/><nd ref="7"/><tag k="highway" v="service"/></way>
 <way id="12"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/>
   <tag k="highway" v="service"/></way>
 <way id="13"><nd ref="6"/><nd ref="7"/><tag k="highway" v="footway"/>
   <tag k="tunnel" v="yes"/></way>
</osm>"""
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]


def read_small(tmp_path):
    path = tmp_path / 'small.osm'
    path.write_text(OSM)
    return c.read_osm(path, lambda lat, lon: (lon, lat))


def area_of(ring, triangles):
    points = c.open_ring(ring)
    total = 0.0
    for a, b, d in triangles:
        total += abs(c.signed_area([points[a], points[b], points[d], points[a]]))
    return total


def test_reading_sorts_areas_lines_and_trees(tmp_path):
    campus = read_small(tmp_path)
    assert campus.trees == [(5.0, 5.0)]
    assert [a.tags.get('name') for a in campus.areas] == ['P4']
    # A closed loop of road is a line, not a filled shape.
    assert sum('highway' in line.tags for line in campus.lines) == 3


def test_a_relations_ways_join_into_a_ring_in_any_order_or_direction():
    a, b, d, e = (0, 0), (1, 0), (1, 1), (0, 1)
    rings = c.join_rings([[a, b], [d, b], [d, e], [a, e]])
    assert len(rings) == 1
    assert rings[0][0] == rings[0][-1] and set(rings[0]) == {a, b, d, e}


def test_a_ring_left_open_is_dropped():
    assert c.join_rings([[(0, 0), (1, 0)], [(1, 0), (1, 1)]]) == []


def test_triangles_cover_a_shape_with_a_dent_exactly():
    dented = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (5.0, 3.0), (0.0, 10.0), (0.0, 0.0)]
    triangles = c.triangulate(dented)
    assert len(triangles) == 3
    assert math.isclose(area_of(dented, triangles), abs(c.signed_area(dented)))


def test_triangles_dont_care_which_way_round_a_ring_goes():
    assert math.isclose(area_of(SQUARE[::-1], c.triangulate(SQUARE[::-1])), 100.0)


def test_a_mesh_faces_up_and_its_texture_repeats_in_metres(tmp_path):
    mesh = c.Mesh()
    mesh.flat(SQUARE, -0.01, tile=5.0)
    assert len(mesh.vertices) == 6
    assert all(n == (0.0, 0.0, 1.0) for n in mesh.normals)
    assert max(u for u, _ in mesh.uvs) == 2.0
    path = tmp_path / 'm.obj'
    mesh.write(path)
    assert path.read_text().count('\nf ') == 2


def test_walls_face_out_whichever_way_the_ring_goes():
    for ring in (SQUARE, SQUARE[::-1]):
        mesh = c.Mesh()
        mesh.prism_walls(ring, 0.0, 3.0)
        for corner, normal in zip(mesh.vertices, mesh.normals):
            outward = (corner[0] - 5.0) * normal[0] + (corner[1] - 5.0) * normal[1]
            assert outward > 0.0


def test_pavement_is_under_the_car_and_the_grass_a_foot_up():
    for z in (c.LOT_Z, c.ROAD_Z, c.PAINT_Z):
        assert z < 0.0
    assert c.GRASS_Z == c.KERB_HEIGHT == 0.30
    assert c.GRASS_Z < c.PATH_Z < c.KERB_TOP_Z


def test_rectangles_cover_a_mask_exactly():
    mask = np.zeros((6, 8), dtype=bool)
    mask[1:4, 2:5] = True
    mask[4, 2:7] = True
    mask[2, 7] = True
    made = np.zeros_like(mask)
    found = c.rectangles(mask)
    for col0, col1, row0, row1 in found:
        assert not made[row0:row1, col0:col1].any(), 'no overlaps'
        made[row0:row1, col0:col1] = True
    assert (made == mask).all()
    assert len(found) == 3, 'equal rows share a rectangle'


def test_kerbs_run_round_the_pavement_and_stay_on_the_map():
    grid = c.Grid((-20.0, -20.0, 30.0, 30.0))
    grid.fill(SQUARE, 1)
    edges = c.pavement_edges(grid.free, grid)
    assert len(edges) == 1 and edges[0][0] == edges[0][-1]
    xs = [p[0] for p in edges[0]]
    ys = [p[1] for p in edges[0]]
    assert abs(min(xs)) < 0.5 and abs(max(xs) - 10.0) < 0.5
    assert abs(min(ys)) < 0.5 and abs(max(ys) - 10.0) < 0.5


def test_a_path_stops_at_the_road_it_crosses():
    grid = c.Grid((-20.0, -20.0, 30.0, 30.0))
    grid.fill(SQUARE, 1)
    parts = c.off_pavement([(-10.0, 5.0), (20.0, 5.0)], grid)
    assert len(parts) == 2
    assert parts[0][-1][0] <= 1.0 and parts[1][0][0] >= 9.0


def test_a_park_round_a_road_leaves_the_road_open(tmp_path):
    meshes, _, grid, _, _, _, _, _ = c.build(read_small(tmp_path), (-5, -5, 30, 30))
    assert grid.is_free(2.0, 7.0), 'the lot is drivable'
    assert meshes['grass'].vertices and meshes['kerb'].vertices
    assert not grid.is_free(-3.0, 5.0), 'the grass is not'


def test_the_grid_is_blocked_until_a_road_opens_it_and_y_goes_up():
    grid = c.Grid((-10.0, -10.0, 10.0, 10.0), cell=0.5)
    assert not grid.is_free(5.0, 5.0)
    grid.fill([(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)], 1)
    assert grid.is_free(5.0, 5.0)
    assert not grid.is_free(5.0, -5.0)
    assert not grid.is_free(50.0, 5.0)


def test_the_cars_start_has_room_round_it():
    grid = c.Grid((-20.0, -20.0, 20.0, 20.0))
    grid.fill(SQUARE, 1)
    x, y = grid.nearest_free(-15.0, -15.0)
    assert 0.5 < x < 9.5 and 0.5 < y < 9.5
    assert c.Grid((0.0, 0.0, 5.0, 5.0)).nearest_free(1.0, 1.0) is None


def test_build_keeps_the_tunnel_and_the_tree_right(tmp_path):
    meshes, _, grid, _, trunks, report, lots, _ = c.build(read_small(tmp_path), (-5, -5, 30, 30))
    assert report['lots'] == 1 and len(lots) == 1
    assert report['paths'] == 0, 'a footway in a tunnel is under the ground'
    assert report['trees'] == 1 and len(trunks) == 1
    assert meshes['lot'].vertices and meshes['leaves'].vertices


def test_heights_come_from_the_map_then_a_guess():
    assert c.floors_of({'height': '12 m'}) == 12.0
    assert c.floors_of({'building:levels': '5'}) == 5 * c.FLOOR_HEIGHT
    assert c.floors_of({'name': 'Dunton Tower'}) == 22 * c.FLOOR_HEIGHT
    assert c.floors_of({'amenity': 'shelter'}) == 3.0
    assert c.floors_of({}, 'a') == c.floors_of({}, 'a')


def test_a_line_moved_left_stays_its_distance_round_a_bend():
    moved = c.offset_line([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], 1.0)
    assert moved[0] == pytest.approx((0.0, 1.0))
    assert moved[1] == pytest.approx((9.0, 1.0))    # the mitre: 1 m from both segments
    assert moved[2] == pytest.approx((9.0, 10.0))
    right = c.offset_line([(0.0, 0.0), (10.0, 0.0)], -2.0)
    assert right == pytest.approx([(0.0, -2.0), (10.0, -2.0)])


def test_a_painted_road_has_an_edge_line_each_side_inside_its_edges():
    shapes = c.edge_lines([(0.0, 0.0), (20.0, 0.0)], 7.0)
    assert len(shapes) == 2
    ys = sorted(sum(p[1] for p in s) / len(s) for s in shapes)
    assert ys == pytest.approx([-3.5 + c.EDGE_INSET, 3.5 - c.EDGE_INSET])
    for s in shapes:
        width = max(p[1] for p in s) - min(p[1] for p in s)
        assert width == pytest.approx(c.LINE_WIDTH)


def test_road_widths_come_from_the_map_then_their_kind():
    assert c.road_width({'width': '7.5', 'highway': 'service'}) == 7.5
    assert c.road_width({'lanes': '2', 'highway': 'service'}) == 2 * c.LANE_WIDTH
    assert c.road_width({'highway': 'service'}) == c.ROAD_WIDTHS['service']


def test_ndts_guess_stays_above_the_floor_and_on_the_shapes():
    points = c.guess_ndt([([(0.0, 0.0), (10.0, 0.0)], 3.0)], [])
    assert len(points) > 100
    assert points[:, 2].min() >= c.NDT_FLOOR
    assert points[:, 2].max() <= 3.0
    assert np.allclose(points[:, 1], 0.0)


def test_textures_tile_and_bump_maps_are_flat_on_a_flat_picture():
    noise = c.periodic_noise(64, 3.0, seed=1)
    assert abs(noise).max() <= 1.0
    # Its edges meet: no bigger a step across the seam than anywhere else.
    assert abs(noise[0] - noise[-1]).max() < 3.0 * abs(noise[1:] - noise[:-1]).max()
    flat = c.normal_map(np.zeros((8, 8)), 5.0)
    assert (flat[..., 2] == 255).all() and (flat[..., 0] == 127).all()
