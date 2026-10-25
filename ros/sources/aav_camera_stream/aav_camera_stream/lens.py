"""
lens: a camera's calibration, and undistorting its pictures with OpenCV.

Reads ROS's two calibration formats: the INI that camera_calibration writes (such as
aav_sensors/config/cameras/left.ini) and camera_info_manager's YAML. A calibration made
at another size of the same picture (1920x1080 for a 1280x720 stream) is scaled; one of
another shape is refused, since a crop moves the centre. Only the lens (K, D) is used:
a stereo pair's rectification (R) is for the pair, not for one camera's detections.

Undistorter builds OpenCV's pixel maps once; apply() is one cv2.remap per picture. Its
lens() is the picture after undistortion (K', no distortion): the camera_info to publish
with the detections, whose boxes are in that picture.
"""

from dataclasses import dataclass, field
from typing import List

import yaml


@dataclass
class Lens:
    width: int
    height: int
    k: List[float]                                  # 3x3, row by row
    d: List[float] = field(default_factory=lambda: [0.0] * 5)
    model: str = 'plumb_bob'


def _numbers(lines):
    return [float(x) for line in lines for x in line.split()]


def parse_ini(text: str) -> Lens:
    """Read a camera_calibration INI: width, height, camera matrix, distortion."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith('#')]

    def block(name, rows):
        i = lines.index(name)
        return _numbers(lines[i + 1:i + 1 + rows])
    try:
        width, height = int(block('width', 1)[0]), int(block('height', 1)[0])
        k = block('camera matrix', 3)
        d = block('distortion', 1)
    except (ValueError, IndexError) as e:
        raise ValueError(f'not a camera_calibration INI file: {e}')
    return Lens(width, height, k, d)


def parse_yaml(text: str) -> Lens:
    """Read camera_info_manager's YAML: image_width, camera_matrix.data..."""
    data = yaml.safe_load(text) or {}
    try:
        return Lens(int(data['image_width']), int(data['image_height']),
                    [float(x) for x in data['camera_matrix']['data']],
                    [float(x) for x in data.get('distortion_coefficients', {}).get(
                        'data', [0.0] * 5)],
                    data.get('distortion_model', 'plumb_bob'))
    except (KeyError, TypeError) as e:
        raise ValueError(f'not a camera_info YAML file: missing {e}')


def load(path: str) -> Lens:
    """Read a calibration file, INI or YAML by its ending."""
    with open(path) as f:
        text = f.read()
    lens = parse_ini(text) if path.endswith('.ini') else parse_yaml(text)
    if len(lens.k) != 9:
        raise ValueError(f'{path}: the camera matrix needs 9 numbers, not {len(lens.k)}')
    return lens


def scaled(lens: Lens, width: int, height: int) -> Lens:
    """Return the same lens for the picture scaled to width x height (same shape)."""
    sx, sy = width / lens.width, height / lens.height
    if abs(sx - sy) > 0.01 * max(sx, sy):
        raise ValueError(f'a {lens.width}x{lens.height} calibration does not fit a '
                         f'{width}x{height} picture: another shape, a crop')
    fx, _, cx, _, fy, cy, _, _, _ = lens.k
    # Pixel centres: OpenCV's pixel (0, 0) is the middle of the first pixel.
    k = [fx * sx, 0.0, (cx + 0.5) * sx - 0.5,
         0.0, fy * sy, (cy + 0.5) * sy - 0.5,
         0.0, 0.0, 1.0]
    return Lens(width, height, k, list(lens.d), lens.model)


def identity(width: int, height: int, focal: float) -> Lens:
    """Return a lens with no distortion: a simulator's camera."""
    return Lens(width, height, [focal, 0.0, (width - 1) / 2.0, 0.0, focal, (height - 1) / 2.0,
                                0.0, 0.0, 1.0])


class Undistorter:
    """Undistort pictures of one size. alpha 0 keeps only valid pixels; 1 keeps them all."""

    def __init__(self, lens: Lens, alpha: float = 0.0):
        import cv2
        import numpy
        if lens.model not in ('plumb_bob', 'rational_polynomial'):
            raise ValueError(f'distortion model {lens.model}: only plumb_bob and '
                             'rational_polynomial')
        k = numpy.array(lens.k, dtype=numpy.float64).reshape(3, 3)
        d = numpy.array(lens.d, dtype=numpy.float64)
        size = (lens.width, lens.height)
        new_k, _ = cv2.getOptimalNewCameraMatrix(k, d, size, alpha, size)
        self.map1, self.map2 = cv2.initUndistortRectifyMap(k, d, None, new_k, size,
                                                           cv2.CV_16SC2)
        self.out = Lens(lens.width, lens.height, [float(x) for x in new_k.flatten()])

    def apply(self, frame):
        import cv2
        return cv2.remap(frame, self.map1, self.map2, cv2.INTER_LINEAR)

    def lens(self) -> Lens:
        return self.out


def projection(lens: Lens):
    """Return the 3x4 P of a lens with no distortion: K beside a zero column."""
    k = lens.k
    return [k[0], k[1], k[2], 0.0, k[3], k[4], k[5], 0.0, k[6], k[7], k[8], 0.0]
