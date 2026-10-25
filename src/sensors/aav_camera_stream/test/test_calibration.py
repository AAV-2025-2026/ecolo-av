"""The checkerboard, the calibrator's command, and filing camera_calibration's result."""

import io
import os
import re
import shutil
import tarfile

from aav_camera_stream import calibration, lens as lenses
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)

# What camera_calibration's SAVE writes as ost.yaml (its lryaml), for a 1280x720 camera.
OST = """image_width: 1280
image_height: 720
camera_name: narrow_stereo
camera_matrix:
  rows: 3
  cols: 3
  data: [951.2, 0.0, 641.5, 0.0, 950.8, 362.1, 0.0, 0.0, 1.0]
distortion_model: plumb_bob
distortion_coefficients:
  rows: 1
  cols: 5
  data: [-0.31, 0.11, 0.0004, -0.0002, 0.0]
rectification_matrix:
  rows: 3
  cols: 3
  data: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
projection_matrix:
  rows: 3
  cols: 4
  data: [700.0, 0.0, 640.0, 0.0, 0.0, 800.0, 360.0, 0.0, 0.0, 0.0, 1.0, 0.0]
"""


def test_the_board_is_9x6_corners_of_25_mm_on_a4():
    board = calibration.Board()
    assert board.size == '9x6'
    assert board.mm() == (250.0, 175.0)
    svg = calibration.board_svg(board)
    assert 'width="297mm" height="210mm"' in svg
    squares = re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="25.00" height="25.00"/>', svg)
    assert len(squares) == 35                   # half of the 10 x 7 squares are black
    assert '--size 9x6 --square 0.025' in svg


def test_a_board_too_big_for_the_page_is_refused():
    with pytest.raises(ValueError, match='does not fit'):
        calibration.board_svg(calibration.Board(square_m=0.035))      # 350 mm: A3, not A4
    assert 'width="420mm"' in calibration.board_svg(calibration.Board(square_m=0.035),
                                                    (420.0, 297.0))


def test_the_calibrator_reads_the_streams_picture():
    argv = calibration.calibrator_command('cameracalibrator', calibration.Board(),
                                          '/sensors/camera/front_left/image_raw')
    assert argv[:5] == ['cameracalibrator', '--size', '9x6', '--square', '0.025']
    assert '--no-service-check' in argv
    assert argv[-2:] == ['-r', 'image:=/sensors/camera/front_left/image_raw']


def tarball(path, members):
    with tarfile.open(path, 'w:gz') as archive:
        for name, text in members.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return str(path)


def test_the_result_comes_out_of_the_tarball(tmp_path):
    saved = tarball(tmp_path / 'calibrationdata.tar.gz', {'left-0000.png': 'x', 'ost.yaml': OST,
                                                          'ost.txt': '# oST version 5.0'})
    assert calibration.read_result(saved) == OST
    empty = tarball(tmp_path / 'other.tar.gz', {'left-0000.png': 'x'})
    with pytest.raises(ValueError, match='no ost.yaml'):
        calibration.read_result(empty)
    plain = tmp_path / 'ost.yaml'
    plain.write_text(OST)
    assert calibration.read_result(str(plain)) == OST


def workspace(tmp_path):
    """Copy the package's cameras.yaml to its place under a pretend repository."""
    cameras = tmp_path / calibration.CAMERAS
    cameras.parent.mkdir(parents=True)
    shutil.copy(os.path.join(PACKAGE, 'config', 'cameras.yaml'), cameras)
    return cameras


def test_install_files_it_and_points_cameras_yaml_to_it(tmp_path):
    cameras = workspace(tmp_path)
    before = cameras.read_text()
    relative = calibration.install(OST, 'front_left', str(tmp_path), note='board 25 mm')
    assert relative == 'src/sensors/aav_camera_stream/config/calibrations/front_left.yaml'
    lens = lenses.load(str(tmp_path / relative))      # the node's own reader
    assert lens.k[0] == 951.2 and lens.d[0] == -0.31
    assert '# board 25 mm' in (tmp_path / relative).read_text()
    after = cameras.read_text()
    assert f'    calibration: {relative}' in after
    # Only front_left's line changed: front_right's and every comment stay.
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
    assert changed == [("    calibration: ''", f'    calibration: {relative}')]
    # Again (a better one): the same line, replaced.
    calibration.install(OST, 'front_left', str(tmp_path))
    assert cameras.read_text() == after


def test_install_refuses_what_doesnt_fit(tmp_path):
    workspace(tmp_path)
    with pytest.raises(ValueError, match='does not fit'):
        calibration.install(OST.replace('image_height: 720', 'image_height: 1024'),
                            'front_left', str(tmp_path))
    with pytest.raises(ValueError, match='no lens'):
        calibration.install(OST.replace('[951.2,', '[0.0,'), 'front_left', str(tmp_path))
    with pytest.raises(ValueError, match='camera_info YAML'):
        calibration.install('hello: 1\n', 'front_left', str(tmp_path))
    with pytest.raises(ValueError, match='rear: not in'):
        calibration.install(OST, 'rear', str(tmp_path))
    assert not (tmp_path / calibration.FOLDER).exists()     # nothing written
