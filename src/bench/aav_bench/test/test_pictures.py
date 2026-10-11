from aav_bench import models, pictures
import numpy as np

CAM = models.Camera([1.8, 0.29, 1.2], 640, 360, 343.0, 1.2)


def red(im):
    b, g, r = im[..., 0].astype(int), im[..., 1].astype(int), im[..., 2].astype(int)
    return (r > 150) & (g < 80) & (b < 80)


def test_the_road_alone_has_no_red():
    im = pictures.scene(CAM, [])
    assert im.shape == (360, 640, 3) and im.dtype == np.uint8
    assert not red(im).any()


def test_a_stop_sign_is_drawn_where_the_camera_sees_it():
    view = models.sign_in_view(CAM, models.Truth(0.0, 15.0, 0.0, 0.0, 0.0, 0.0),
                               (25.0, -2.0), 2.0, 0.75)
    im = pictures.scene(CAM, [view])
    ys, xs = np.nonzero(red(im))
    assert len(xs) > 0.4 * view.size ** 2, 'most of the plate is red'
    assert abs(xs.mean() - view.u) < 2 and abs(ys.mean() - view.v) < 2


def paint(im, row):
    """Return the columns of white paint in one row of the picture."""
    return np.flatnonzero(im[row].min(axis=1) > 180)


def test_the_lines_are_where_the_camera_sees_them():
    # The car 0.5 m left of the lane's centre, along the road: the camera (0.29 m left of
    # the car) has the lines 0.96 m to its left and 2.54 m to its right.
    im = pictures.road(CAM, models.Truth(0.0, 0.0, 0.5, 0.0, 0.0, 0.0))
    row = 300
    ahead = 343.0 * 1.2 / (row - 180.0)
    found = paint(im, row)
    for left in (1.75 - 0.5 - 0.29, -1.75 - 0.5 - 0.29):
        assert np.abs(found - (320.0 - 343.0 * left / ahead)).min() < 2.0


def test_turning_left_swings_the_road_to_the_right():
    straight = pictures.road(CAM, models.Truth(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    turned = pictures.road(CAM, models.Truth(0.0, 0.0, 0.0, 0.1, 0.0, 0.0))
    assert paint(turned, 200).mean() > paint(straight, 200).mean() + 20.0


def test_a_bend_to_the_left_curves_the_lines_left():
    car = models.Truth(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    straight = pictures.road(CAM, car)
    bend = pictures.road(CAM, car, models.Road(bend_x=0.0, bend_radius=40.0))
    assert (paint(bend, 300).mean() - paint(straight, 300).mean()) < 5.0, 'near: the same'
    assert paint(bend, 195).mean() < paint(straight, 195).mean() - 20.0, 'far: bent left'


def test_the_post_stands_on_the_ground():
    view = models.sign_in_view(CAM, models.Truth(0.0, 15.0, 0.0, 0.0, 0.0, 0.0),
                               (25.0, -2.0), 2.0, 0.75)
    im = pictures.scene(CAM, [view])
    post = (110, 110, 110)
    column = int(view.u)
    assert (im[int(view.foot_v) - 3, column] == post).all()
    assert not (im[int(view.foot_v) + 3:, column] == post).all(axis=1).any()
