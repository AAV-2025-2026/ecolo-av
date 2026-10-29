"""
The geofence: an area the computer's drivers may not leave. No ROS here, so the tests run anywhere.

The fence is a `Circle` (round where the car first stood still) or a site's `Polygon`, in
the map frame. `Geofence` takes each global pose and says whether twist_mux's geofence lock
should be on: when any corner of the car, moved on by its stopping distance, comes within
`margin` (plus the pose's own spread) of the edge, or when the pose can't be trusted.

    d = v * reaction_time + v^2 / (2 * braking)        (RSS's safe stopping distance)

Design: docs/designs/2026-10-29_geofence.md. Units: m, s, rad, m/s.
"""

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]

STARTING, OK, NEAR, OUTSIDE, LOST = 'STARTING', 'OK', 'NEAR', 'OUTSIDE', 'LOST'


def _finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


class Circle:
    """A round fence: `radius` m round (cx, cy)."""

    def __init__(self, cx: float, cy: float, radius: float):
        if not _finite(cx, cy, radius) or radius <= 0.0:
            raise ValueError('a circle needs a finite centre and a radius > 0')
        self.cx, self.cy, self.radius = cx, cy, radius

    def depth(self, x: float, y: float) -> float:
        """Return how far (x, y) is inside the fence (m); negative outside."""
        return self.radius - math.hypot(x - self.cx, y - self.cy)

    def outline(self, n: int = 36) -> List[Point]:
        """Return n points round the circle, for drawing."""
        return [(self.cx + self.radius * math.cos(2 * math.pi * i / n),
                 self.cy + self.radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


class Polygon:
    """A fence with corners (x, y), in order round it, either way. Not self-crossing."""

    def __init__(self, corners: Sequence[Point]):
        points = [(float(x), float(y)) for x, y in corners]
        if len(points) < 3 or not all(_finite(x, y) for x, y in points):
            raise ValueError('a polygon needs at least 3 finite corners')
        area = sum(x0 * y1 - x1 * y0
                   for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])) / 2.0
        if abs(area) < 1.0:
            raise ValueError(f'the polygon is {abs(area):.2f} m^2: is it a line?')
        self.corners = points

    @classmethod
    def from_flat(cls, values: Sequence[float]) -> 'Polygon':
        """Make one from [x0, y0, x1, y1, ...], as a ROS parameter holds it."""
        if len(values) % 2:
            raise ValueError('a polygon parameter needs pairs: x0, y0, x1, y1, ...')
        return cls(list(zip(values[0::2], values[1::2])))

    def _edges(self):
        return zip(self.corners, self.corners[1:] + self.corners[:1])

    def contains(self, x: float, y: float) -> bool:
        inside = False
        for (x0, y0), (x1, y1) in self._edges():
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
        return inside

    def depth(self, x: float, y: float) -> float:
        """Return how far (x, y) is inside the fence (m); negative outside."""
        nearest = min(_to_segment(x, y, a, b) for a, b in self._edges())
        return nearest if self.contains(x, y) else -nearest

    def outline(self) -> List[Point]:
        return list(self.corners)


def _to_segment(x: float, y: float, a: Point, b: Point) -> float:
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def stopping_distance(speed: float, reaction_time: float, braking: float) -> float:
    """Return how far the car goes before it stands still (m): RSS's v*rho + v^2/(2b)."""
    v = abs(speed)
    return v * reaction_time + v * v / (2.0 * braking)


@dataclass
class Settings:
    """The geofence's limits (config/geofence.yaml)."""

    margin: float = 1.0          # m kept between the stopping point and the edge
    reaction_time: float = 0.6   # s from the lock to ego braking
    braking: float = 1.0         # m/s^2 the car can count on
    hysteresis: float = 0.5      # m further in before NEAR lets go
    max_std: float = 3.0         # m: a pose spread (1 sigma) over this can't be trusted
    max_age: float = 1.0         # s without a pose: lost
    settle_time: float = 3.0     # s of good poses before the fence is used (and a circle placed)
    still_speed: float = 0.1     # m/s: the car stands still, so a circle may be placed

    def __post_init__(self):
        for name in ('margin', 'reaction_time', 'hysteresis', 'max_age', 'settle_time',
                     'still_speed'):
            value = getattr(self, name)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError(f'{name} must be a finite number >= 0')
        for name in ('braking', 'max_std'):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(f'{name} must be a finite number > 0')


@dataclass
class Pose:
    """The global EKF's pose: map frame, base_link's position and heading, forward speed."""

    x: float
    y: float
    yaw: float
    speed: float        # m/s along base_link's x, negative reversing
    std: float          # m: the position's spread, 1 sigma

    def good(self, max_std: float) -> bool:
        return _finite(self.x, self.y, self.yaw, self.speed, self.std) and self.std <= max_std


class Geofence:
    """
    Decide the geofence lock from each pose.

    fence: a Circle or a Polygon; None for a circle of `radius` placed where the car first
    stands still for `settle_time` s with good poses. footprint: the car's corners in
    base_link (aav_description vehicle.footprint_points). Times: any steady clock, in s.
    """

    def __init__(self, footprint: Sequence[Point], settings: Settings = Settings(),
                 fence=None, radius: Optional[float] = None):
        if fence is None and radius is None:
            raise ValueError('give a fence, or a radius for a circle round the start')
        if fence is None:
            Circle(0.0, 0.0, radius)     # checks the radius now, not at the start
        self.footprint = [(float(x), float(y)) for x, y in footprint]
        if not self.footprint:
            raise ValueError('the footprint needs corners')
        self.settings, self.fence, self.radius = settings, fence, radius
        self.pose: Optional[Pose] = None
        self.pose_time: Optional[float] = None
        self.good_since: Optional[float] = None
        self.outside = False         # latched until clear()
        self.near = False
        self.state, self.why = STARTING, 'no global pose yet'

    def update(self, now: float, pose: Pose) -> None:
        """Take a pose that arrived at `now`."""
        s = self.settings
        if not pose.good(s.max_std):
            self.pose, self.pose_time, self.good_since = pose, now, None
            return
        if self.good_since is None:
            self.good_since = now
        self.pose, self.pose_time = pose, now
        if (self.fence is None and now - self.good_since >= s.settle_time
                and abs(pose.speed) <= s.still_speed):
            self.fence = Circle(pose.x, pose.y, self.radius)

    def points(self, pose: Pose) -> List[Point]:
        """Return the car's corners, and the same corners moved on by its stopping distance."""
        s = self.settings
        d = math.copysign(stopping_distance(pose.speed, s.reaction_time, s.braking), pose.speed)
        c, n = math.cos(pose.yaw), math.sin(pose.yaw)
        out = []
        for ahead in (0.0, d):
            for fx, fy in self.footprint:
                bx = fx + ahead
                out.append((pose.x + bx * c - fy * n, pose.y + bx * n + fy * c))
        return out

    def check(self, now: float) -> Tuple[bool, str, str]:
        """Return (locked, state, why) at `now`."""
        s = self.settings
        pose = self.pose
        if pose is None:
            return self._say(True, STARTING, 'no global pose yet')
        if now - self.pose_time > s.max_age:
            return self._say(True, LOST, f'no global pose for {now - self.pose_time:.1f} s')
        if not pose.good(s.max_std):
            return self._say(True, LOST, f'the global pose is unsure: {pose.std:.1f} m '
                                         f'(over {s.max_std:.1f} m) or not a number')
        if self.fence is None or now - self.good_since < s.settle_time:
            return self._say(True, STARTING, 'waiting for the pose to settle, standing still')
        here = self.fence.depth(pose.x, pose.y)
        if here < 0.0:
            self.outside = True
        if self.outside:
            return self._say(True, OUTSIDE, f'the car is {-here:.1f} m outside the fence: '
                             'a person drives it back in, then clears it' if here < 0.0 else
                             f'back inside ({here:.1f} m): waiting for a person to clear it')
        nearest = min(self.fence.depth(x, y) for x, y in self.points(pose))
        need = s.margin + pose.std + (s.hysteresis if self.near else 0.0)
        self.near = nearest < need
        if self.near:
            return self._say(True, NEAR, f'the stopping point is {nearest:.1f} m from the '
                                         f'edge (needs {need:.1f} m) at {pose.speed:.1f} m/s')
        return self._say(False, OK, f'{nearest:.1f} m from the edge at {pose.speed:.1f} m/s')

    def clear(self, now: float) -> Tuple[bool, str]:
        """A person says the car is back in: forget OUTSIDE. Refused while it isn't."""
        if not self.outside:
            return True, 'nothing to clear'
        pose = self.pose
        if (pose is None or self.fence is None or now - self.pose_time > self.settings.max_age
                or not pose.good(self.settings.max_std)):
            return False, 'no good global pose: the fence cannot say where the car is'
        here = self.fence.depth(pose.x, pose.y)
        if here < 0.0:
            return False, f'the car is still {-here:.1f} m outside the fence'
        self.outside = False
        return True, f'cleared: the car is {here:.1f} m inside'

    def _say(self, locked: bool, state: str, why: str) -> Tuple[bool, str, str]:
        self.state, self.why = state, why
        return locked, state, why
