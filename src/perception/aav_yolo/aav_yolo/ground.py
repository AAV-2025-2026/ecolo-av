"""
Where a camera's picture meets a flat road: a detection's box to points on the ground.

No ROS imports, so the tests run anywhere. The camera is a pinhole: each pixel looks along
one ray. base_link sits on the road, so the road is z = 0 there, and the ray through the
bottom edge of a box meets it where the object stands. The lens (intrinsics) comes from
the camera's CameraInfo; where the camera is, and how it's tilted, from TF.

Frames: base_link is x forward, y left, z up. A camera's frame is either the same way round
(camera_left_link in vehicle.yaml) or an optical frame, z forward, x right, y down (a name
that ends in _optical or _optical_frame, as REP-103 says). Lens distortion is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Tuple

from aav_yolo.boxes import normal_label

Vec3 = Tuple[float, float, float]
Matrix = Tuple[Vec3, Vec3, Vec3]
Point = Tuple[float, float]

# Never obstacles, whatever the class list says. A stop sign stops the car through
# twist_mux's lock instead, and it stands up on a post: the bottom of its box isn't where
# it meets the road, so its point would land far beyond it.
NEVER = frozenset({'stop sign'})

# COCO classes that stand on the road (the stock model's names).
ROAD_USERS = ('person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'cat', 'dog', 'horse')


@dataclass(frozen=True)
class Lens:
    """A pinhole camera's intrinsics, in pixels: CameraInfo's K, and the picture's size."""

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


@dataclass(frozen=True)
class Mount:
    """Where a camera is on the car: its position in base_link, and its rotation to it."""

    position: Vec3
    rotation: Matrix      # turns a direction in the camera's frame into base_link
    optical: bool         # the camera's frame is z forward, x right, y down


def lens_from_k(k: Sequence[float], width: int, height: int) -> Optional[Lens]:
    """Read CameraInfo's K (row by row, 3 x 3). None for an uncalibrated camera (K is 0)."""
    fx, fy = float(k[0]), float(k[4])
    if fx <= 0.0 or fy <= 0.0 or width <= 0 or height <= 0:
        return None
    return Lens(fx, fy, float(k[2]), float(k[5]), int(width), int(height))


def is_optical(frame_id: str) -> bool:
    """Return True for an optical frame's name (REP-103: z forward, x right, y down)."""
    return frame_id.endswith(('_optical', '_optical_frame'))


def rotation(x: float, y: float, z: float, w: float) -> Matrix:
    """Return the rotation matrix of a unit quaternion (TF's x, y, z, w)."""
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def turn(m: Matrix, v: Vec3) -> Vec3:
    return tuple(sum(m[r][c] * v[c] for c in range(3)) for r in range(3))


def ray(lens: Lens, u: float, v: float, optical: bool) -> Vec3:
    """Return the direction a pixel looks along, in the camera's own frame."""
    right, down = (u - lens.cx) / lens.fx, (v - lens.cy) / lens.fy
    return (right, down, 1.0) if optical else (1.0, -right, -down)


def on_road(lens: Lens, mount: Mount, u: float, v: float) -> Optional[Point]:
    """Return where a pixel's ray meets the road, (x, y) in base_link; None above the horizon."""
    d = turn(mount.rotation, ray(lens, u, v, mount.optical))
    px, py, pz = mount.position
    if d[2] >= -1e-9 or pz <= 0.0:
        return None
    s = -pz / d[2]
    return px + s * d[0], py + s * d[1]


def ground_range(mount: Mount, p: Point) -> float:
    """Return how far a point on the road is from the spot under the camera."""
    return math.hypot(p[0] - mount.position[0], p[1] - mount.position[1])


def along(a: Point, b: Point, step: float) -> List[Point]:
    """Return points from a to b, no more than `step` apart, both ends included."""
    n = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def box_points(lens: Lens, mount: Mount, cx: float, cy: float, width: float, height: float,
               step: float, max_range: float) -> List[Point]:
    """
    Return points on the road along a box's bottom edge, `step` metres apart.

    The box is a detection's, in pixels: its centre and size. Its bottom edge is where the
    object stands; a box cut off by the bottom of the picture gives the nearest road the
    camera sees, so the object is at least that close. Returns nothing above the horizon,
    or farther than `max_range` from the camera: the road's distance grows quickly with any
    error in the camera's tilt.
    """
    v = min(cy + height / 2.0, float(lens.height))
    left = on_road(lens, mount, max(cx - width / 2.0, 0.0), v)
    right = on_road(lens, mount, min(cx + width / 2.0, float(lens.width)), v)
    if left is None or right is None:
        return []
    return [p for p in along(left, right, step) if ground_range(mount, p) <= max_range]


def bearing(mount: Mount, lens: Lens, u: float, v: float) -> float:
    """Return which way a pixel looks, across the road: radians from x, + left."""
    d = turn(mount.rotation, ray(lens, u, v, mount.optical))
    return math.atan2(d[1], d[0])


def view_edge(lens: Lens, mount: Mount, view_range: float, step: float) -> List[Point]:
    """
    Return points on the road `view_range` from the camera, across its picture's width.

    The edge of what the camera sees: the costmap clears its camera layer from the car out
    to these points, then marks what the detectors see now, so old boxes don't linger.
    A camera tilted so far down that the top of its picture shows the road sees less far:
    the edge comes in to where the top row meets the road.
    """
    top = on_road(lens, mount, lens.cx, 0.0)
    reach = min(view_range, ground_range(mount, top)) if top else view_range
    right = bearing(mount, lens, float(lens.width), lens.cy)
    left = bearing(mount, lens, 0.0, lens.cy)
    span = (left - right) % (2.0 * math.pi)
    n = max(1, math.ceil(reach * span / step))
    ox, oy = mount.position[0], mount.position[1]
    angles = (right + span * i / n for i in range(n + 1))
    return [(ox + reach * math.cos(a), oy + reach * math.sin(a)) for a in angles]


def counts(label: str, classes: Sequence[str]) -> bool:
    """Return True if a detection's label goes in the costmap: listed, and never a stop sign."""
    name = normal_label(label)
    return name not in NEVER and name in {normal_label(c) for c in classes}
