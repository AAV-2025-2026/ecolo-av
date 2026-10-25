"""
The bird's-eye view: the road ahead, seen from above, made from one camera picture.

No ROS imports, so the tests run anywhere. The road is taken to be flat, so each pixel
below the horizon sees one point on the ground. Where that point is follows from the lens
(focal length, centre, distortion), where the camera sits on the car, and how it is
tilted.

The view is a grid on the ground in base_link (x forward, y left, metres, REP-103):

    row 0          the far edge (x_max)       column 0         the left edge (+y_max)
    the last row   the near edge (x_min)      the last column  the right edge (-y_max)

Cells the camera can't see stay black, and `valid` says which ones they are.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, Tuple

import cv2
import numpy as np

# Rays that meet the ground closer than this in front of the lens are left out.
NEAREST = 0.1   # m


@dataclass(frozen=True)
class Lens:
    """A camera's intrinsics, as in sensor_msgs/CameraInfo: K, and D (plumb_bob)."""

    width: int                  # px
    height: int                 # px
    fx: float                   # px
    fy: float                   # px
    cx: float                   # px
    cy: float                   # px
    distortion: Tuple[float, ...] = ()   # k1, k2, p1, p2, k3; empty for none

    @classmethod
    def pinhole(cls, width: int, height: int, focal: float) -> 'Lens':
        """Return a lens with no distortion, centred on the picture: the bench camera's kind."""
        return cls(width, height, focal, focal, width / 2.0, height / 2.0)

    def matrix(self) -> np.ndarray:
        return np.array([[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]])


@dataclass(frozen=True)
class Mount:
    """Where the camera sits on the car, as vehicle.yaml gives it (base_link to the camera)."""

    xyz: Tuple[float, float, float]                     # m; z is the height above the road
    rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # rad; pitch + = looking down


@dataclass(frozen=True)
class Grid:
    """The patch of road the bird's-eye view covers, in base_link."""

    x_min: float = 4.0         # m ahead of base_link: the near edge
    x_max: float = 16.0        # m ahead: the far edge
    y_max: float = 4.0         # m either side
    resolution: float = 0.05   # m per pixel

    @property
    def rows(self) -> int:
        return int(round((self.x_max - self.x_min) / self.resolution))

    @property
    def cols(self) -> int:
        return int(round(2.0 * self.y_max / self.resolution))

    def x_of_row(self, row):
        """Return the forward distance (m) of a row's centre."""
        return self.x_max - (np.asarray(row) + 0.5) * self.resolution

    def y_of_col(self, col):
        """Return the sideways distance (m, + = left) of a column's centre."""
        return self.y_max - (np.asarray(col) + 0.5) * self.resolution

    def row_of_x(self, x):
        return (self.x_max - np.asarray(x)) / self.resolution - 0.5

    def col_of_y(self, y):
        return (self.y_max - np.asarray(y)) / self.resolution - 0.5


def rotation(rpy: Sequence[float]) -> np.ndarray:
    """Return the matrix that turns the camera's axes into base_link's (roll, pitch, yaw)."""
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ])


def project(points: np.ndarray, lens: Lens, mount: Mount) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return where points in base_link (N x 3, metres) land in the picture.

    Returns (uv, seen): uv is N x 2 in pixels, and seen says which points are in front of
    the lens and inside the picture. Pixel centres are whole numbers, as in OpenCV.
    """
    in_camera = (np.asarray(points, float) - np.asarray(mount.xyz, float)) @ rotation(mount.rpy)
    # The optical frame: x right, y down, z along the lens's axis.
    optical = np.stack([-in_camera[:, 1], -in_camera[:, 2], in_camera[:, 0]], axis=1)
    ahead = optical[:, 2] > NEAREST
    depth = np.where(ahead, optical[:, 2], 1.0)
    # Distortion models go wild far outside the picture, so judge "nearly in view" by the
    # plain pinhole first.
    plain = np.stack([lens.fx * optical[:, 0] / depth + lens.cx,
                      lens.fy * optical[:, 1] / depth + lens.cy], axis=1)
    near_view = (ahead & (plain[:, 0] > -0.25 * lens.width) & (plain[:, 0] < 1.25 * lens.width)
                 & (plain[:, 1] > -0.25 * lens.height) & (plain[:, 1] < 1.25 * lens.height))
    uv = plain
    if any(lens.distortion):
        uv, _ = cv2.projectPoints(optical.reshape(-1, 1, 3), np.zeros(3), np.zeros(3),
                                  lens.matrix(), np.asarray(lens.distortion, float))
        uv = uv.reshape(-1, 2)
    seen = (near_view & (uv[:, 0] >= 0.0) & (uv[:, 0] <= lens.width - 1.0)
            & (uv[:, 1] >= 0.0) & (uv[:, 1] <= lens.height - 1.0))
    return uv, seen


class BirdsEye:
    """Warp camera pictures into the bird's-eye view: one look-up table, made once."""

    def __init__(self, lens: Lens, mount: Mount, grid: Grid = Grid()):
        self.lens, self.mount, self.grid = lens, mount, grid
        rows, cols = np.mgrid[0:grid.rows, 0:grid.cols]
        ground = np.stack([grid.x_of_row(rows).ravel(), grid.y_of_col(cols).ravel(),
                           np.zeros(rows.size)], axis=1)
        uv, seen = project(ground, lens, mount)
        uv[~seen] = -10.0   # outside the picture: the border colour, black
        map_x = uv[:, 0].reshape(rows.shape).astype(np.float32)
        map_y = uv[:, 1].reshape(rows.shape).astype(np.float32)
        # Fixed-point tables make cv2.remap about twice as fast.
        self._maps = cv2.convertMaps(map_x, map_y, cv2.CV_16SC2)
        self.valid = seen.reshape(rows.shape)

    def warp(self, image: np.ndarray) -> np.ndarray:
        """Return the bird's-eye view of one picture (the same channels as the picture)."""
        if image.shape[0] != self.lens.height or image.shape[1] != self.lens.width:
            raise ValueError(f'the picture is {image.shape[1]} x {image.shape[0]}, the lens '
                             f'{self.lens.width} x {self.lens.height}')
        return cv2.remap(image, self._maps[0], self._maps[1], cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    def nearest_seen(self) -> float:
        """Return how far ahead of base_link (m) the camera first sees the road, in the grid."""
        rows = np.flatnonzero(self.valid.any(axis=1))
        return float(self.grid.x_of_row(rows.max())) if rows.size else math.inf
