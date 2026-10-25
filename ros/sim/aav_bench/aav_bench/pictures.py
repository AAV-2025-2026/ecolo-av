"""
The pretend camera's pictures: the road, and stop signs where the bench world has them.

Needs NumPy and OpenCV, not ROS. The road is drawn from where the car really is: each
pixel below the horizon is followed down to the flat ground, and coloured by where that
point lies on the bench road (models.Road), so the lane lines move as the car does. The
stop sign is drawn like the real thing: a red octagon with a white rim and STOP, on a grey
post. The stock YOLO model knows it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional, Sequence

import cv2
import numpy as np

from .models import Camera, offset, Road, SignView, Truth

SKY = (205, 175, 125)      # BGR
GRASS = (70, 130, 80)
ROAD = (95, 95, 95)
PAINT = (235, 235, 235)


@dataclass
class _Ground:
    """Where each pixel below the horizon meets the ground, from the camera (level axes)."""

    pixels: np.ndarray    # flat indices into the picture
    forward: np.ndarray   # m
    left: np.ndarray      # m
    size: np.ndarray      # m across one pixel, sideways: for smooth edges


_GROUND: Dict[tuple, _Ground] = {}


def _ground(cam: Camera) -> _Ground:
    key = (cam.width, cam.height, cam.focal, cam.height_above_ground, cam.pitch)
    if key not in _GROUND:
        v, u = np.mgrid[0:cam.height, 0:cam.width].astype(np.float32)
        left = -(u - cam.width / 2.0) / cam.focal      # a ray through each pixel's centre
        up = -(v - cam.height / 2.0) / cam.focal
        c, s = math.cos(cam.pitch), math.sin(cam.pitch)
        forward, rise = c + s * up, -s + c * up         # tipped down with the camera
        down = rise < -1e-6
        reach = cam.height_above_ground / -rise[down]
        _GROUND[key] = _Ground(np.flatnonzero(down), reach * forward[down], reach * left[down],
                               reach / cam.focal)
    return _GROUND[key]


def _cover(inside: np.ndarray, size: np.ndarray) -> np.ndarray:
    """Return how much of a pixel lies inside an edge: `inside` m in from it (- = outside)."""
    return np.clip(0.5 + inside / size, 0.0, 1.0)[:, None]


def road(cam: Camera, truth: Optional[Truth] = None, lane: Optional[Road] = None) -> np.ndarray:
    """Draw sky, grass and the bench road with its two lines, as the car sees them."""
    truth = truth or Truth(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    lane = lane or Road()
    g = _ground(cam)
    x0, y0 = offset(truth, cam.xyz)
    c, s = math.cos(truth.yaw), math.sin(truth.yaw)
    across = lane.lateral(x0 + c * g.forward - s * g.left, y0 + s * g.forward + c * g.left)
    half = lane.lane_width / 2.0
    tarmac = _cover(half + lane.shoulder - np.abs(across), g.size)
    paint = _cover(lane.line_width / 2.0 - np.abs(np.abs(across) - half), g.size)
    colour = np.asarray(GRASS, np.float32) + tarmac * (np.subtract(ROAD, GRASS))
    colour += paint * (np.asarray(PAINT, np.float32) - colour)
    im = np.empty((cam.height, cam.width, 3), np.uint8)
    im[:] = SKY
    im.reshape(-1, 3)[g.pixels] = colour.round().astype(np.uint8)
    return im


def draw_stop_sign(im: np.ndarray, view: SignView) -> None:
    """Draw one stop sign, its centre at (u, v) and `size` pixels across, on its post."""
    r = view.size / 2.0
    c = np.array([view.u, view.v])
    post = max(1, int(r / 8))
    foot = im.shape[0] if view.foot_v is None else min(im.shape[0], int(round(view.foot_v)))
    cv2.rectangle(im, (int(view.u) - post, int(view.v + r)), (int(view.u) + post, foot),
                  (110, 110, 110), -1)
    angles = math.pi / 8 + np.arange(8) * math.pi / 4

    def octagon(radius):
        pts = c + radius * np.stack([np.cos(angles), np.sin(angles)], 1)
        return pts.round().astype(np.int32)

    cv2.fillPoly(im, [octagon(r)], (255, 255, 255), cv2.LINE_AA)
    cv2.fillPoly(im, [octagon(r * 0.9)], (30, 30, 200), cv2.LINE_AA)
    scale = r / 48.0
    if scale > 0.15:
        font, thick = cv2.FONT_HERSHEY_DUPLEX, max(1, int(scale * 3.4))
        (w, h), _ = cv2.getTextSize('STOP', font, scale, thick)
        cv2.putText(im, 'STOP', (int(view.u - w / 2), int(view.v + h / 2)), font, scale,
                    (255, 255, 255), thick, cv2.LINE_AA)


def scene(cam: Camera, signs: Sequence[SignView], truth: Optional[Truth] = None,
          lane: Optional[Road] = None) -> np.ndarray:
    """Draw the road, with the farthest sign first so nearer ones cover it."""
    im = road(cam, truth, lane)
    for view in sorted(signs, key=lambda s: -s.distance):
        draw_stop_sign(im, view)
    return im
