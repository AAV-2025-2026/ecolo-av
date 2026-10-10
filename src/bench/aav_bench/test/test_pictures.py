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
