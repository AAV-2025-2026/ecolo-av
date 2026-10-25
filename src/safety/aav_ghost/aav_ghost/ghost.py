"""
The ghost's maths: where a pretend obstacle stands, and the scan Nav2 sees of it.

No ROS here. ghost_obstacle (the node) asks TF where the car is, then calls these.

The ghost is an upright cylinder standing on the road: a person is about 0.5 m wide and
1.7 m tall, a post narrower. It stays put in a fixed frame (map) once placed; the scan is
what a perfect 2D lidar at base_link would see of it, inf in every other direction, so
the layer that reads it clears itself when the ghost goes.
"""

from dataclasses import dataclass
import math

import numpy


@dataclass(frozen=True)
class Pose:
    """The car's base_link in the fixed frame: x, y (m) and heading (rad, left of x)."""

    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class Ghost:
    """A pretend obstacle: its centre in the fixed frame (m), its width and height (m)."""

    x: float
    y: float
    width: float = 0.5
    height: float = 1.7


@dataclass(frozen=True)
class ScanShape:
    """The ghost's scan: all the way round base_link, as lidar_scan's (aav_lidar)."""

    angle_min: float = -math.pi
    angle_increment: float = math.radians(0.5)
    count: int = 720
    range_min: float = 0.2      # m from base_link
    range_max: float = 30.0     # m: a ghost further away is not in the scan


def ahead_of(pose, front, ahead, width):
    """
    Return (x, y) of a ghost's centre `ahead` m in front of the car's front bumper.

    front is base_link to the front bumper (m); the ghost's near edge is `ahead` m from
    the bumper, on the car's heading.
    """
    d = front + ahead + width / 2.0
    return pose.x + d * math.cos(pose.yaw), pose.y + d * math.sin(pose.yaw)


def to_base(x, y, pose):
    """Return the fixed-frame point (x, y) in base_link's frame, the car at `pose`."""
    dx, dy = x - pose.x, y - pose.y
    c, s = math.cos(pose.yaw), math.sin(pose.yaw)
    return c * dx + s * dy, -s * dx + c * dy


def ranges(ghost, pose, shape=ScanShape()):
    """
    Return the scan of the ghost, in m: its near side, inf in every other direction.

    Each beam from base_link meets the ghost's circle (radius width / 2) at its nearest
    crossing. With base_link inside the ghost, every beam reads range_min: something is
    touching the car all round.
    """
    out = numpy.full(shape.count, numpy.inf)
    cx, cy = to_base(ghost.x, ghost.y, pose)
    r = ghost.width / 2.0
    if math.hypot(cx, cy) - r > shape.range_max:
        return out
    angles = shape.angle_min + shape.angle_increment * numpy.arange(shape.count)
    ux, uy = numpy.cos(angles), numpy.sin(angles)
    # |t u - c|^2 = r^2: t^2 - 2 t (u.c) + |c|^2 - r^2 = 0
    b = ux * cx + uy * cy
    disc = b * b - (cx * cx + cy * cy - r * r)
    hit = disc >= 0.0
    root = numpy.sqrt(numpy.where(hit, disc, 0.0))
    near = b - root
    if cx * cx + cy * cy <= r * r:
        out[:] = shape.range_min
        return out
    hit &= near > 0.0
    out[hit] = numpy.clip(near[hit], shape.range_min, None)
    out[out > shape.range_max] = numpy.inf
    return out


USAGE = """\
ghost ahead <m>               a ghost <m> in front of the car's front bumper, where it is now
ghost at <x> <y>              a ghost at map x, y (m)
ghost size <width> <height>   m: a person 0.5 1.7 (the default), a post 0.3 1.2
ghost on                      the last ghost again (ahead: in front of the car now)
ghost off                     take it away"""


def command(words):
    """
    Return the ghost_obstacle parameters a command line sets, as {name: value}.

    Raises ValueError, with the usage, for anything else. A size alone leaves the ghost
    on or off as it was. `at` sets ahead to -1: a negative ahead means "at x, y".
    """
    if words:
        verb, rest = words[0], words[1:]
        try:
            numbers = [float(w) for w in rest]
        except ValueError:
            numbers = None
        if numbers is not None:
            if verb == 'ahead' and len(numbers) == 1 and numbers[0] >= 0.0:
                return {'ahead': numbers[0], 'enabled': True}
            if verb == 'at' and len(numbers) == 2:
                return {'ahead': -1.0, 'x': numbers[0], 'y': numbers[1], 'enabled': True}
            if verb == 'size' and len(numbers) == 2 and min(numbers) > 0.0:
                return {'width': numbers[0], 'height': numbers[1]}
            if verb in ('on', 'off') and not numbers:
                return {'enabled': verb == 'on'}
    raise ValueError(USAGE)
