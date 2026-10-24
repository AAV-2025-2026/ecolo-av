"""recent: every camera's newest obstacle points, published together."""

from aav_detector.recent import Recent


def test_both_cameras_count_every_time():
    r = Recent(max_age=1.0)
    r.update('camera_left_link', 10.0, [(5.0, 0.0)], [(12.0, 0.0)])
    r.update('camera_rear_link', 10.05, [(-3.0, 0.2)], [(-12.0, 0.0)])
    # A front picture with nobody in it: the person behind stays.
    r.update('camera_left_link', 10.1, [], [(12.0, 0.0)])
    assert r.obstacles(10.1) == [(-3.0, 0.2)]
    assert sorted(r.view(10.1)) == [(-12.0, 0.0), (12.0, 0.0)]
    assert r.cameras(10.1) == ['camera_left_link', 'camera_rear_link']


def test_a_silent_camera_drops_out():
    r = Recent(max_age=1.0)
    r.update('camera_rear_link', 10.0, [(-3.0, 0.0)], [])
    r.update('camera_left_link', 11.5, [], [])
    assert r.obstacles(11.5) == []                      # 1.5 s old: gone
    assert r.cameras(11.5) == ['camera_left_link']


def test_nothing_yet():
    assert Recent().obstacles(0.0) == [] and Recent().view(0.0) == []
