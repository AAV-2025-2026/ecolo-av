import math

from aav_yolo import ground
import pytest

# The bench camera: 640 x 360, 343 px focal length, centred; 1.2 m up, 1.8 m ahead of
# base_link (vehicle.yaml's camera_left_link, without its 0.29 m to the left).
LENS = ground.Lens(fx=343.0, fy=343.0, cx=320.0, cy=180.0, width=640, height=360)
LEVEL = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
CAMERA = ground.Mount((1.8, 0.0, 1.2), LEVEL, optical=False)


def row_for(distance, lens=LENS, height=1.2):
    """Return the row where a level pinhole camera sees the road `distance` m ahead."""
    return lens.cy + lens.fy * height / distance


def pitched_down(angle):
    """Return CAMERA tilted down by `angle` (rad): + pitch, about y."""
    return ground.Mount((1.8, 0.0, 1.2), ground.rotation(0.0, math.sin(angle / 2), 0.0,
                                                         math.cos(angle / 2)), optical=False)


def test_a_level_camera_sees_the_road_at_the_known_distance():
    for d in (3.0, 5.0, 10.0):
        x, y = ground.on_road(LENS, CAMERA, LENS.cx, row_for(d))
        assert x == pytest.approx(1.8 + d) and y == pytest.approx(0.0, abs=1e-9)


def test_left_of_the_centre_is_left():
    x, y = ground.on_road(LENS, CAMERA, LENS.cx - LENS.fx * 0.5 / 10.0, row_for(10.0))
    assert x == pytest.approx(11.8) and y == pytest.approx(0.5)


def test_a_tilted_camera_sees_the_road_where_it_points():
    tilt = math.atan2(1.2, 10.0)      # the centre of the picture looks at the road 10 m ahead
    x, y = ground.on_road(LENS, pitched_down(tilt), LENS.cx, LENS.cy)
    assert x == pytest.approx(11.8) and y == pytest.approx(0.0, abs=1e-9)


def test_the_horizon_and_above_never_meet_the_road():
    assert ground.on_road(LENS, CAMERA, LENS.cx, LENS.cy) is None
    assert ground.on_road(LENS, CAMERA, LENS.cx, LENS.cy - 50.0) is None


def test_an_optical_frame_gives_the_same_point():
    # REP-103's camera_optical_frame: z forward, x right, y down; rpy (-pi/2, 0, -pi/2).
    optical = ground.Mount((1.8, 0.0, 1.2), ground.rotation(-0.5, 0.5, -0.5, 0.5),
                           optical=True)
    assert ground.is_optical('camera_left_optical_frame')
    assert not ground.is_optical('camera_left_link')
    u, v = LENS.cx - 40.0, row_for(7.0)
    assert ground.on_road(LENS, optical, u, v) == pytest.approx(ground.on_road(LENS, CAMERA, u, v))


def test_the_rotation_of_a_quarter_turn_left():
    r = ground.rotation(0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4))
    assert ground.turn(r, (1.0, 0.0, 0.0)) == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)


def test_a_box_becomes_points_along_its_bottom_edge():
    # A person 0.5 m wide, 10 m ahead: 17.15 px wide, feet on row_for(10).
    width_px, bottom = LENS.fx * 0.5 / 10.0, row_for(10.0)
    points = ground.box_points(LENS, CAMERA, LENS.cx, bottom - 40.0, width_px, 80.0,
                               step=0.1, max_range=12.0)
    assert len(points) == 6
    assert all(x == pytest.approx(11.8) for x, _ in points)
    assert points[0][1] == pytest.approx(0.25) and points[-1][1] == pytest.approx(-0.25)
    gaps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    assert max(gaps) <= 0.1 + 1e-9


def test_a_box_too_far_away_is_dropped():
    points = ground.box_points(LENS, CAMERA, LENS.cx, row_for(20.0) - 10.0, 10.0, 20.0,
                               step=0.1, max_range=12.0)
    assert points == []


def test_a_box_cut_off_by_the_bottom_of_the_picture_is_at_least_that_close():
    points = ground.box_points(LENS, CAMERA, LENS.cx, 330.0, 20.0, 200.0, step=0.1,
                               max_range=12.0)
    nearest_road = 1.2 * LENS.fy / (LENS.height - LENS.cy)     # the bottom row: 2.29 m
    assert points and all(x == pytest.approx(1.8 + nearest_road) for x, _ in points)


def test_a_box_in_the_sky_gives_nothing():
    assert ground.box_points(LENS, CAMERA, LENS.cx, 60.0, 40.0, 40.0, 0.1, 12.0) == []


def test_the_view_edge_spans_the_picture_at_its_range():
    edge = ground.view_edge(LENS, CAMERA, view_range=12.0, step=0.1)
    half = math.atan2(LENS.cx, LENS.fx)             # 43 degrees each side
    first, last = edge[0], edge[-1]
    assert math.atan2(first[1], first[0] - 1.8) == pytest.approx(-half)
    assert math.atan2(last[1], last[0] - 1.8) == pytest.approx(half)
    assert all(math.hypot(x - 1.8, y) == pytest.approx(12.0) for x, y in edge)
    assert max(math.dist(a, b) for a, b in zip(edge, edge[1:])) <= 0.1 + 1e-9


def test_a_camera_tilted_hard_down_sees_less_far():
    tilt = math.radians(40.0)            # more than half its view (27.7 degrees) down
    edge = ground.view_edge(LENS, pitched_down(tilt), view_range=12.0, step=0.1)
    top = tilt - math.atan2(LENS.cy, LENS.fy)                  # the top row looks 12.3 down
    reach = 1.2 / math.tan(top)
    assert all(math.hypot(x - 1.8, y) == pytest.approx(reach) for x, y in edge)
    assert reach < 12.0


def test_stop_signs_never_count():
    assert not ground.counts('stop sign', ['stop sign', 'person'])
    assert not ground.counts('Stop_Sign', ['Stop_Sign'])
    assert ground.counts('person', ground.ROAD_USERS)
    assert ground.counts('Person', ['person'])
    assert not ground.counts('traffic light', ground.ROAD_USERS)
    assert 'stop sign' not in ground.ROAD_USERS


def test_the_lens_comes_from_camera_info():
    lens = ground.lens_from_k([343.0, 0.0, 320.0, 0.0, 343.0, 180.0, 0.0, 0.0, 1.0], 640, 360)
    assert lens == LENS
    assert ground.lens_from_k([0.0] * 9, 640, 360) is None
