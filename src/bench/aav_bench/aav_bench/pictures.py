"""
The pretend camera's pictures: a road, and stop signs where the bench world has them.

Needs NumPy and OpenCV, not ROS. The stop sign is drawn like the real thing: a red
octagon with a white rim and STOP, on a grey post. The stock YOLO model knows it.
"""

from __future__ import annotations

import math
from typing import Sequence

import cv2
import numpy as np

from .models import Camera, SignView

SKY = (205, 175, 125)      # BGR
GRASS = (70, 130, 80)
ROAD = (95, 95, 95)
PAINT = (235, 235, 235)


def road(cam: Camera) -> np.ndarray:
    """Draw sky, grass and a straight road with its edge lines, seen from the camera."""
    im = np.empty((cam.height, cam.width, 3), np.uint8)
    horizon = cam.height // 2
    im[:horizon] = SKY
    im[horizon:] = GRASS
    mid = cam.width // 2
    bottom = cam.height - 1
    # A 3.5 m lane in perspective: a point on the ground L metres to the side, at the
    # picture's bottom row, is L * (rows below the horizon) / (camera height) pixels out.
    edge = int(1.75 * (bottom - horizon) / cam.height_above_ground)
    pts = np.array([[mid - edge, bottom], [mid + edge, bottom], [mid, horizon]], np.int32)
    cv2.fillPoly(im, [pts], ROAD)
    for side in (-1, 1):
        cv2.line(im, (mid + side * edge, bottom), (mid, horizon), PAINT, 3, cv2.LINE_AA)
    return im


def draw_stop_sign(im: np.ndarray, view: SignView) -> None:
    """Draw one stop sign, its centre at (u, v) and `size` pixels across, on its post."""
    r = view.size / 2.0
    c = np.array([view.u, view.v])
    post = max(1, int(r / 8))
    cv2.rectangle(im, (int(view.u) - post, int(view.v + r)), (int(view.u) + post, im.shape[0]),
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


def scene(cam: Camera, signs: Sequence[SignView]) -> np.ndarray:
    """Draw the road, with the farthest sign first so nearer ones cover it."""
    im = road(cam)
    for view in sorted(signs, key=lambda s: -s.distance):
        draw_stop_sign(im, view)
    return im
