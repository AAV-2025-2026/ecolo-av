"""
What each pretend sensor would measure, given where the model car really is.

No ROS imports, so the tests run anywhere. The car's truth comes from spine_sim on
/bench/truth: position and heading in the map frame (x east, y north), speed, turn rate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Optional, Sequence, Tuple

import numpy as np

G = 9.80665                      # m/s^2
WGS84_A = 6378137.0              # m, the Earth's equatorial radius
WGS84_E2 = 6.69437999014e-3      # the ellipse's eccentricity squared

# The Earth's field near Ottawa, roughly (NOAA's model for 2026): 17 uT north, 52 uT down.
FIELD_NORTH_T = 17.0e-6
FIELD_DOWN_T = 52.0e-6


@dataclass
class Truth:
    """One /bench/truth sample."""

    t: float          # s
    x: float          # m, east of the datum
    y: float          # m, north of the datum
    yaw: float        # rad, from east, positive left
    speed: float      # m/s, negative in reverse
    yaw_rate: float   # rad/s


def offset(truth: Truth, xyz: Sequence[float]) -> Tuple[float, float]:
    """Return where a point fixed on the car is, in the map frame: e.g. the GPS antenna."""
    c, s = math.cos(truth.yaw), math.sin(truth.yaw)
    return truth.x + c * xyz[0] - s * xyz[1], truth.y + s * xyz[0] + c * xyz[1]


def geo_from_map(x: float, y: float, datum_lat: float, datum_lon: float) -> Tuple[float, float]:
    """
    Turn metres east and north of the datum into latitude and longitude (degrees).

    Uses the Earth's local radii at the datum: within a few hundred metres the error is
    millimetres, well under what navsat_transform's UTM grid differs by anyway.
    """
    phi = math.radians(datum_lat)
    w = 1.0 - WGS84_E2 * math.sin(phi) ** 2
    meridian = WGS84_A * (1.0 - WGS84_E2) / w ** 1.5   # north-south radius
    normal = WGS84_A / math.sqrt(w)                       # east-west radius
    return (datum_lat + math.degrees(y / meridian),
            datum_lon + math.degrees(x / (normal * math.cos(phi))))


Vec3 = Tuple[float, float, float]


def imu_reading(now: Truth, before: Optional[Truth]) -> Tuple[Vec3, Vec3]:
    """
    Return the IMU's (accel, gyro) in its own frame, without noise.

    accel x: speeding up; accel y: the turn's sideways pull (v times the turn rate); accel z:
    gravity, as a real accelerometer reads it at rest. gyro z: the turn rate.
    """
    ax = 0.0
    if before is not None and now.t > before.t:
        ax = (now.speed - before.speed) / (now.t - before.t)
    return (ax, now.speed * now.yaw_rate, G), (0.0, 0.0, now.yaw_rate)


def magnetic_field(yaw: float) -> Vec3:
    """Return the Earth's field in the car's frame (tesla): x forward, y left, z up."""
    return (FIELD_NORTH_T * math.sin(yaw), FIELD_NORTH_T * math.cos(yaw), -FIELD_DOWN_T)


def noisy(values: Sequence[float], stddev: float, rng: random.Random,
          bias: Sequence[float] = (0.0, 0.0, 0.0)) -> Tuple[float, ...]:
    """Add Gaussian noise (and a fixed bias) to each value."""
    return tuple(v + b + rng.gauss(0.0, stddev) for v, b in zip(values, bias))


def battery_voltage(hours_driven: float, full: float, empty: float, hours: float) -> float:
    """Return a steady drain from full to empty over `hours` of driving, never below empty."""
    left = max(0.0, 1.0 - hours_driven / hours)
    return empty + (full - empty) * left


@dataclass
class Camera:
    """A pinhole camera on the car: where it sits, and its lens."""

    xyz: Sequence[float]   # m, on the car (camera_left_link in vehicle.yaml)
    width: int
    height: int
    focal: float           # px
    height_above_ground: float
    pitch: float = 0.0     # rad, + = looking down (vehicle.yaml's rpy[1])

    def pixel(self, forward: float, left: float, up: float) -> Tuple[float, float, float]:
        """
        Return (u, v, depth) for a point forward, left and up of the camera (m, level axes).

        depth is the distance along the lens's axis: the point is behind the camera if it's
        not positive.
        """
        c, s = math.cos(self.pitch), math.sin(self.pitch)
        depth = c * forward - s * up
        rise = s * forward + c * up
        if depth <= 0.0:
            return math.nan, math.nan, depth
        return (self.width / 2.0 - self.focal * left / depth,
                self.height / 2.0 - self.focal * rise / depth, depth)


@dataclass
class SignView:
    """A stop sign in the picture: its centre (px), its size (px) and how far it is (m)."""

    u: float
    v: float
    size: float
    distance: float
    foot_v: Optional[float] = None   # px: the row where its post meets the ground


def sign_in_view(cam: Camera, truth: Truth, sign_xy: Sequence[float], sign_height: float,
                 sign_size: float) -> Optional[SignView]:
    """
    Return where a stop sign lands in the camera's picture, or None if the camera can't see it.

    The sign is a sign_size-metre plate whose centre stands sign_height metres up at sign_xy
    on the map.
    """
    cx, cy = offset(truth, cam.xyz)
    dx, dy = sign_xy[0] - cx, sign_xy[1] - cy
    c, s = math.cos(truth.yaw), math.sin(truth.yaw)
    forward, left = c * dx + s * dy, -s * dx + c * dy
    u, v, depth = cam.pixel(forward, left, sign_height - cam.height_above_ground)
    if depth < 1.0:
        return None
    size = cam.focal * sign_size / depth
    if not (0.0 <= u <= cam.width and 0.0 <= v <= cam.height) or size < 4.0:
        return None
    _, foot_v, _ = cam.pixel(forward, left, -cam.height_above_ground)
    return SignView(u, v, size, math.hypot(forward, left), foot_v)


@dataclass
class Road:
    """
    The bench world's road: one lane between two painted lines, in the map frame.

    It runs east along y, straight; with a bend_radius, it bends from bend_x on, round a
    half circle.
    """

    y: float = 0.0              # m north of the datum: the lane's centre line
    lane_width: float = 3.5     # m between the lines' centres
    line_width: float = 0.15    # m of paint
    shoulder: float = 0.5       # m of tarmac outside each line
    bend_x: float = 0.0         # m east: where the bend starts
    bend_radius: float = 0.0    # m: + bends left (north), - right, 0 straight

    def _centre(self) -> Tuple[float, float]:
        return self.bend_x, self.y + self.bend_radius

    def lateral(self, x, y):
        """Return how far (x, y) is left of the lane's centre line (m). Takes arrays too."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        across = y - self.y
        if self.bend_radius:
            r = self.bend_radius
            ox, oy = self._centre()
            arc = math.copysign(1.0, r) * (abs(r) - np.hypot(x - ox, y - oy))
            across = np.where(x > self.bend_x, arc, across)
        return across

    def pose(self, x: float, y: float, yaw: float) -> Tuple[float, float]:
        """Return the car's (offset, heading error): m left of the centre, rad left of the road."""
        direction = 0.0
        if self.bend_radius and x > self.bend_x:
            ox, oy = self._centre()
            direction = math.atan2(y - oy, x - ox) + math.copysign(math.pi / 2, self.bend_radius)
        error = (yaw - direction + math.pi) % (2.0 * math.pi) - math.pi
        return float(self.lateral(x, y)), error


def pairs(flat: Sequence[float]) -> List[Tuple[float, float]]:
    """Read a flat [x1, y1, x2, y2, ...] parameter as (x, y) pairs."""
    if len(flat) % 2:
        raise ValueError('stop_signs needs x, y pairs')
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
