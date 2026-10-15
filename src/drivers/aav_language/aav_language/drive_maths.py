"""
The maths behind drive() and turn(): a total distance becomes one ScriptedDrive goal.

No ROS imports, so the tests run anywhere.

A ScriptedDrive goal speeds up, holds for hold_distance, then slows down. The person asks
for the WHOLE distance, so the ramps count too:

    speeding up   v^2 / 2a
    slowing down  v^2 / 2b
    holding       d - both

If the distance is too short to reach v, the top speed drops until both ramps just fit:
v = sqrt(2 d a b / (a + b)), and the goal holds for no time at all.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DriveGoal:
    """The numbers of one ScriptedDrive goal, and what they add up to."""

    target_speed: float     # m/s, negative = reverse
    acceleration: float     # m/s^2
    deceleration: float     # m/s^2
    hold_distance: float    # m at target_speed; 0 = no hold (hold_time 0)
    curvature: float        # 1/m, + = left
    distance: float         # m in total, the ramps included

    @property
    def hold_time(self) -> float:
        """Seconds to hold when hold_distance is 0: none."""
        return 0.0

    @property
    def expected_duration(self) -> float:
        """Seconds the profile takes on paper (the real car lags a little)."""
        v = abs(self.target_speed)
        if v == 0:
            return 0.0
        return v / self.acceleration + v / self.deceleration + self.hold_distance / v

    def as_dict(self) -> dict:
        return {'target_speed': self.target_speed, 'acceleration': self.acceleration,
                'deceleration': self.deceleration, 'hold_time': self.hold_time,
                'hold_distance': self.hold_distance, 'curvature': self.curvature}


def ramp_distance(speed: float, rate: float) -> float:
    """Metres covered speeding up from 0 to speed (or slowing to 0) at rate m/s^2."""
    if rate <= 0:
        raise ValueError('acceleration and deceleration must be positive')
    return speed * speed / (2.0 * rate)


def plan_distance(distance: float, speed: float, acceleration: float, deceleration: float,
                  reverse: bool = False, curvature: float = 0.0) -> DriveGoal:
    """
    Return the goal that covers `distance` metres in total, at up to `speed` m/s.

    distance and speed are sizes (> 0); reverse makes the target speed negative.
    """
    if distance <= 0 or not math.isfinite(distance):
        raise ValueError('distance must be a positive number of metres')
    if speed <= 0 or not math.isfinite(speed):
        raise ValueError('speed must be a positive number of m/s')
    if acceleration <= 0 or deceleration <= 0:
        raise ValueError('acceleration and deceleration must be positive')
    ramps = ramp_distance(speed, acceleration) + ramp_distance(speed, deceleration)
    hold = distance - ramps
    if hold < 0:
        # Too short to reach the speed: the fastest profile that still fits.
        speed = math.sqrt(2.0 * distance * acceleration * deceleration
                          / (acceleration + deceleration))
        hold = 0.0
    return DriveGoal(target_speed=-speed if reverse else speed, acceleration=acceleration,
                     deceleration=deceleration, hold_distance=hold, curvature=curvature,
                     distance=distance)


@dataclass(frozen=True)
class Arc:
    """A turn as the car drives it: a curvature and a length along the arc."""

    curvature: float   # 1/m, + = left
    length: float      # m


def plan_arc(angle_deg: float, radius: float) -> Arc:
    """
    Return the arc that turns the car by angle_deg (+ = left) on a circle of radius m.

    length = radius * |angle in radians|; curvature = sign(angle) / radius.
    """
    if not math.isfinite(angle_deg) or angle_deg == 0:
        raise ValueError('angle must be a non-zero number of degrees')
    if radius <= 0 or not math.isfinite(radius):
        raise ValueError('radius must be a positive number of metres')
    angle = math.radians(angle_deg)
    return Arc(curvature=math.copysign(1.0 / radius, angle), length=radius * abs(angle))


def min_turn_radius(wheelbase: float, max_steering_angle: float) -> float:
    """Return the tightest circle the car can drive (bicycle model): L / tan(max steer)."""
    if wheelbase <= 0 or not 0 < max_steering_angle < math.pi / 2:
        raise ValueError('need a positive wheelbase and a steering limit below 90 degrees')
    return wheelbase / math.tan(max_steering_angle)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Metres between two latitude/longitude points (a sphere of the Earth's mean radius)."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))
