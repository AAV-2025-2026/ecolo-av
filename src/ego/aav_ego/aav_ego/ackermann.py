"""
The math behind ego: a Twist (v, w) becomes an Ackermann (speed, steering).

No ROS imports, so the tests run anywhere.

Model: the bicycle model about the rear axle (base_link). A car moving at speed
v with front-wheel angle d turns at w = v * tan(d) / L, where L is the
wheelbase. So d = atan(L * w / v). Nav2's car-aware planners and controllers
(SmacPlannerHybrid, Regulated Pure Pursuit, MPPI with its Ackermann model)
only ask for turns the car can make, so this conversion is exact for them.

A car can't turn on the spot: with v near 0 the formula has no answer, so ego
keeps the wheels where they are until the car moves.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Tuple


@dataclass
class Limits:
    wheelbase: float = 1.57              # m, rear axle to front axle
    max_steering_angle: float = 0.5      # rad, either side
    max_speed: float = 1.0               # m/s forward (set per profile)
    max_reverse_speed: float = 0.5       # m/s
    max_acceleration: float = 1.0        # m/s^2 while speeding up
    max_deceleration: float = 2.0        # m/s^2 while slowing down
    max_steering_rate: float = 0.6       # rad/s
    min_speed_for_steering: float = 0.05  # m/s; below this the steering holds


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def steering_angle(v: float, w: float, lim: Limits, hold: float) -> float:
    """Return the front-wheel angle for (v, w), or `hold` if the car is too slow to tell."""
    if abs(v) < lim.min_speed_for_steering:
        return hold
    d = math.atan(lim.wheelbase * w / v)
    return clamp(d, -lim.max_steering_angle, lim.max_steering_angle)


def turn_rate(v: float, d: float, wheelbase: float) -> float:
    """Return the yaw rate of the bicycle model, the inverse of steering_angle."""
    return v * math.tan(d) / wheelbase


def slew_speed(current: float, target: float, lim: Limits, dt: float) -> Tuple[float, float]:
    """Move the speed toward target within the limits; return (speed, rate used)."""
    if current != 0.0 and target != 0.0 and (current > 0.0) != (target > 0.0):
        target = 0.0  # change direction through a stop
    speeding_up = abs(target) > abs(current)
    rate = lim.max_acceleration if speeding_up else lim.max_deceleration
    step = rate * dt
    if target > current:
        return min(target, current + step), rate
    return max(target, current - step), rate


class EgoModel:
    """The car as ego sees it: the speed and steering it last commanded."""

    def __init__(self, limits: Limits):
        self.lim = limits
        self.speed = 0.0
        self.steering = 0.0

    def step(self, cmd: Optional[Tuple[float, float]], dt: float) -> Tuple[float, float, float]:
        """
        Advance one tick.

        cmd is (v, w) from /control/cmd_vel, or None when it is missing or stale,
        which means stop. Returns (speed, steering angle, acceleration limit).
        """
        lim = self.lim
        if cmd is None:
            target_v, target_d = 0.0, self.steering
        else:
            v, w = cmd
            # Keep the requested curvature w / v even when the speed is capped.
            target_d = steering_angle(v, w, lim, self.steering)
            target_v = clamp(v, -lim.max_reverse_speed, lim.max_speed)
        self.speed, accel = slew_speed(self.speed, target_v, lim, dt)
        step = lim.max_steering_rate * dt
        self.steering = clamp(target_d, self.steering - step, self.steering + step)
        return self.speed, self.steering, accel
