import math

from aav_lane_finder.birds_eye import BirdsEye, Grid, Lens, Mount, project
import numpy as np
from scenes import BENCH_CAMERA, picture

LENS = Lens.pinhole(640, 360, 343.0)
BENCH = Mount(BENCH_CAMERA)


def test_a_point_on_the_ground_lands_where_the_pinhole_says():
    # 10 m in front of the camera, on its axis: v = cy + f * height / distance.
    uv, seen = project(np.array([[11.8, 0.29, 0.0]]), LENS, BENCH)
    assert seen[0]
    assert abs(uv[0, 0] - 320.0) < 1e-6
    assert abs(uv[0, 1] - (180.0 + 343.0 * 1.2 / 10.0)) < 1e-6


def test_a_point_on_the_left_lands_left_of_centre():
    uv, _ = project(np.array([[11.8, 1.29, 0.0]]), LENS, BENCH)
    assert abs(uv[0, 0] - (320.0 - 343.0 * 1.0 / 10.0)) < 1e-6


def test_tilting_the_camera_down_lifts_the_horizon():
    tilted = Mount(BENCH_CAMERA, (0.0, 0.1, 0.0))
    uv, seen = project(np.array([[1e5, 0.29, 0.0]]), LENS, tilted)
    assert seen[0]
    assert abs(uv[0, 1] - (180.0 - 343.0 * math.tan(0.1))) < 0.5


def test_turning_the_camera_left_moves_the_road_ahead_right():
    turned = Mount(BENCH_CAMERA, (0.0, 0.0, 0.1))
    uv, _ = project(np.array([[20.0, 0.29, 0.0]]), LENS, turned)
    assert uv[0, 0] > 320.0 + 30.0


def test_points_behind_or_outside_the_picture_are_not_seen():
    _, seen = project(np.array([[-5.0, 0.0, 0.0], [5.0, 30.0, 0.0], [2.5, 0.29, 0.0]]),
                      LENS, BENCH)
    assert not seen.any()


def test_the_bench_camera_sees_the_road_from_about_4_m():
    view = BirdsEye(LENS, BENCH, Grid(x_min=2.0))
    # The bottom row looks down at atan(179.5 / 343): 2.29 m ahead of the camera.
    assert abs(view.nearest_seen() - (1.8 + 1.2 * 343.0 / 179.5)) < 0.06


def test_the_lines_land_where_they_are_on_the_ground():
    grid = Grid()
    view = BirdsEye(LENS, BENCH, grid)
    bev = view.warp(picture(offset=0.4))
    # The car is 0.4 m left of the centre: the lines are 1.35 m left and 2.15 m right.
    row = int(round(float(grid.row_of_x(8.0))))
    paint = np.flatnonzero(bev[row].min(axis=1) > 200)
    found = grid.y_of_col(paint)
    assert np.any(np.abs(found - 1.35) < 0.06) and np.any(np.abs(found + 2.15) < 0.06)
    assert not np.any((found > -2.0) & (found < 1.2)), 'nothing but tarmac between them'


def test_a_picture_of_the_wrong_size_is_refused():
    view = BirdsEye(LENS, BENCH)
    try:
        view.warp(np.zeros((480, 640, 3), np.uint8))
    except ValueError:
        return
    raise AssertionError('a 640 x 480 picture went through a 640 x 360 lens')
