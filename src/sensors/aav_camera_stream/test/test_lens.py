"""Calibration files, scaling a lens to the stream's size, and undistortion."""

import os

from aav_camera_stream import lens as lenses
import numpy
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
LEFT_INI = os.path.join(HERE, '..', '..', 'aav_sensors', 'config', 'cameras', 'left.ini')

YAML = """
image_width: 640
image_height: 360
camera_name: front_left
camera_matrix: {rows: 3, cols: 3, data: [343.0, 0, 319.5, 0, 343.0, 179.5, 0, 0, 1]}
distortion_model: plumb_bob
distortion_coefficients: {rows: 1, cols: 5, data: [-0.3, 0.07, 0, 0, 0]}
"""


def test_reads_the_2024_25_ini():
    lens = lenses.load(LEFT_INI)
    assert (lens.width, lens.height) == (1920, 1080)
    assert lens.k[0] == pytest.approx(1030.472906) and lens.k[5] == pytest.approx(543.009182)
    assert lens.d == pytest.approx([-0.328913, 0.075192, -0.001220, -0.001370, 0.0])


def test_reads_camera_info_yaml(tmp_path):
    path = tmp_path / 'front_left.yaml'
    path.write_text(YAML)
    lens = lenses.load(str(path))
    assert (lens.width, lens.height, lens.k[0], lens.d[0]) == (640, 360, 343.0, -0.3)


def test_bad_files(tmp_path):
    bad = tmp_path / 'bad.yaml'
    bad.write_text('image_width: 640\n')
    with pytest.raises(ValueError, match='camera_info'):
        lenses.load(str(bad))
    with pytest.raises(ValueError, match='INI'):
        lenses.parse_ini('[image]\nwidth\n')


def test_scaled_to_the_stream():
    lens = lenses.scaled(lenses.load(LEFT_INI), 1280, 720)
    s = 1280 / 1920
    assert lens.k[0] == pytest.approx(1030.472906 * s)
    assert lens.k[2] == pytest.approx((963.397952 + 0.5) * s - 0.5)
    assert lens.d == lenses.load(LEFT_INI).d          # distortion has no units: unchanged


def test_another_shape_is_refused():
    with pytest.raises(ValueError, match='shape'):
        lenses.scaled(lenses.load(LEFT_INI), 640, 480)


def test_no_distortion_changes_nothing():
    pytest.importorskip('cv2')
    undistort = lenses.Undistorter(lenses.identity(640, 360, 343.0))
    frame = numpy.random.default_rng(0).integers(0, 256, (360, 640, 3), dtype=numpy.uint8)
    out = undistort.apply(frame)
    assert numpy.abs(out.astype(int) - frame).max() <= 1
    assert undistort.lens().k == pytest.approx(lenses.identity(640, 360, 343.0).k, abs=1e-6)


def test_undistortion_straightens_a_line():
    """A straight edge, bent by the 2024-25 lens, comes out straight again."""
    cv2 = pytest.importorskip('cv2')
    lens = lenses.scaled(lenses.load(LEFT_INI), 1280, 720)
    k = numpy.array(lens.k).reshape(3, 3)
    d = numpy.array(lens.d)
    undistort = lenses.Undistorter(lens)
    # Where a straight row of the undistorted picture (y = 150) lands in the raw one.
    new_k = numpy.array(undistort.lens().k).reshape(3, 3)
    xs = numpy.linspace(200, 1080, 12)
    ideal = numpy.stack([xs, numpy.full_like(xs, 150.0)], axis=1)
    rays = cv2.undistortPoints(ideal.reshape(-1, 1, 2), new_k, None)
    raw, _ = cv2.projectPoints(cv2.convertPointsToHomogeneous(rays), numpy.zeros(3),
                               numpy.zeros(3), k, d)
    raw = raw.reshape(-1, 2)
    assert numpy.ptp(raw[:, 1]) > 5                  # bent in the raw picture
    frame = numpy.zeros((720, 1280), numpy.uint8)
    for x, y in raw:
        cv2.circle(frame, (int(round(x)), int(round(y))), 3, 255, -1)
    out = undistort.apply(frame)
    found = []
    for x in xs:
        column = out[:, int(round(x))]
        if column.max() > 100:
            found.append(float(numpy.average(numpy.arange(720), weights=column)))
    assert len(found) >= 10
    assert numpy.ptp(found) < 3                       # straight once undistorted


def test_projection():
    p = lenses.projection(lenses.identity(640, 360, 343.0))
    assert len(p) == 12 and p[0] == 343.0 and p[3] == 0.0 and p[10] == 1.0
