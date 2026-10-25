"""
calibration: the checkerboard, ROS's camera_calibration's command, and its result filed. No ROS.

    print the board ──> camera_calibration on the stream ──> SAVE ──> install()
    (board_svg)          (calibrator_command)                         config/calibrations/
                                                                      <camera>.yaml, and
                                                                      cameras.yaml points
                                                                      to it

The board: 9 x 6 inner corners (10 x 7 squares) of 25 mm, 250 x 175 mm: A4 or Letter,
landscape, printed at 100%. camera_calibration counts the inner corners (--size 9x6) and
needs the square's real size (--square 0.025, in m): measure it on the paper, since a
printer can scale. A bigger board (--square 0.035, on A3) can be seen from farther away.

The result: camera_calibration's SAVE writes /tmp/calibrationdata.tar.gz, with the
pictures it used and ost.yaml, camera_info_manager's YAML (lens.py reads it). install()
checks it fits the stream's picture (the same shape: lens.scaled), writes it to
ros/sources/aav_camera_stream/config/calibrations/<camera>.yaml and points the camera's
`calibration:` in config/cameras.yaml to it.
"""

from dataclasses import dataclass
import os
import re
import tarfile

from aav_camera_stream import lens as lenses

RESULT = '/tmp/calibrationdata.tar.gz'     # where camera_calibration's SAVE puts it
FOLDER = os.path.join('ros', 'sources', 'aav_camera_stream', 'config', 'calibrations')
CAMERAS = os.path.join('ros', 'sources', 'aav_camera_stream', 'config', 'cameras.yaml')
A4_LANDSCAPE_MM = (297.0, 210.0)


@dataclass(frozen=True)
class Board:
    """A checkerboard: inner corners across and down, and one square's side (m)."""

    cols: int = 9
    rows: int = 6
    square_m: float = 0.025

    @property
    def size(self) -> str:
        """camera_calibration's --size: the inner corners, such as 9x6."""
        return f'{self.cols}x{self.rows}'

    def mm(self):
        """Return the board's printed width and height (mm): one square more than corners."""
        side = 1000.0 * self.square_m
        return (self.cols + 1) * side, (self.rows + 1) * side


def board_svg(board: Board = Board(), paper_mm=A4_LANDSCAPE_MM, margin_mm=10.0) -> str:
    """Return the board as an SVG page in mm, centred, to print at 100% (actual size)."""
    width, height = board.mm()
    page_w, page_h = paper_mm
    if width + 2 * margin_mm > page_w or height + 2 * margin_mm + 8 > page_h:
        raise ValueError(f'a {width:g} x {height:g} mm board does not fit a {page_w:g} x '
                         f'{page_h:g} mm page: a smaller square, or bigger paper')
    side = 1000.0 * board.square_m
    x0, y0 = (page_w - width) / 2, (page_h - height - 8) / 2
    squares = [f'<rect x="{x0 + c * side:.2f}" y="{y0 + r * side:.2f}" width="{side:.2f}" '
               f'height="{side:.2f}"/>'
               for r in range(board.rows + 1) for c in range(board.cols + 1) if (r + c) % 2 == 0]
    label = (f'AAV camera calibration: {board.size} inner corners, squares {side:g} mm '
             f'(--size {board.size} --square {board.square_m:g}). Print at 100%; measure a '
             'square; glue it flat')
    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w:g}mm" height="{page_h:g}mm" '
        f'viewBox="0 0 {page_w:g} {page_h:g}">',
        f'<rect x="0" y="0" width="{page_w:g}" height="{page_h:g}" fill="white"/>',
        '<g fill="black">', *squares, '</g>',
        f'<text x="{page_w / 2:.1f}" y="{y0 + height + 7:.1f}" font-family="sans-serif" '
        f'font-size="4" text-anchor="middle">{label}</text>',
        '</svg>', ''])


def calibrator_command(program: str, board: Board, image_topic: str):
    """Return camera_calibration's cameracalibrator argv, reading this image topic."""
    return [program, '--size', board.size, '--square', f'{board.square_m:g}',
            # camera_stream serves no set_camera_info: SAVE, not COMMIT, keeps the result.
            '--no-service-check', '--ros-args', '-r', f'image:={image_topic}']


def read_result(path: str) -> str:
    """Return the calibration YAML from camera_calibration's tarball, or from a .yaml file."""
    if path.endswith(('.tar.gz', '.tgz', '.tar')):
        with tarfile.open(path) as archive:
            try:
                member = archive.extractfile('ost.yaml')
            except KeyError:
                member = None
            if member is None:
                raise ValueError(f"{path}: no ost.yaml in it (not camera_calibration's SAVE?)")
            return member.read().decode()
    with open(path) as f:
        return f.read()


def point_to(cameras_yaml: str, camera: str, relative: str) -> str:
    """Return config/cameras.yaml's text with this camera's calibration: set; comments kept."""
    block = re.search(rf'^  {re.escape(camera)}:\n((?:    .*\n?|\s*\n)*)', cameras_yaml,
                      re.MULTILINE)
    if block is None:
        raise ValueError(f'{camera}: not in config/cameras.yaml')
    body = block.group(1)
    line = f'    calibration: {relative}'
    if re.search(r'^    calibration:.*$', body, re.MULTILINE):
        body = re.sub(r'^    calibration:.*$', line, body, count=1, flags=re.MULTILINE)
    else:
        body = body.rstrip('\n') + '\n' + line + '\n'
    return cameras_yaml[:block.start(1)] + body + cameras_yaml[block.end(1):]


def install(text: str, camera: str, root: str, width: int = 1280, height: int = 720,
            note: str = '') -> str:
    """
    File a calibration for this camera; return its path from the repository's root.

    Refuses one that isn't a camera_info YAML, or that doesn't fit the stream's
    width x height (another shape: a crop, or another camera mode).
    """
    lens = lenses.parse_yaml(text)
    if len(lens.k) != 9 or lens.k[0] <= 0 or lens.k[4] <= 0:
        raise ValueError('the calibration has no lens (its camera matrix is empty)')
    lenses.scaled(lens, width, height)          # raises if it doesn't fit the stream
    relative = os.path.join(FOLDER, f'{camera}.yaml')
    cameras = os.path.join(root, CAMERAS)
    with open(cameras) as f:
        updated = point_to(f.read(), camera, relative)
    os.makedirs(os.path.join(root, FOLDER), exist_ok=True)
    header = (f"# {camera}: camera_calibration's result (pixi run calibrate-camera; "
              f'docs/camera-calibration.md), {lens.width}x{lens.height}.')
    with open(os.path.join(root, relative), 'w') as f:
        f.write(header + (f'\n# {note}' if note else '') + '\n' + text.lstrip())
    with open(cameras, 'w') as f:
        f.write(updated)
    return relative
