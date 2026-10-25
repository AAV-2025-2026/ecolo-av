"""
One drive to B, tick by tick: the speed (approach.py) and the steering (line.py) together.

No ROS here. goto_driver.py gives it the pose and the speed from the global EKF, and
publishes what it returns: a speed and a curvature (TwistStamped: angular.z = v * k).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from aav_goto.approach import Approach, STOPPING, TURN
from aav_goto.line import (bearing_error, Line, Point, Pose, pursuit_curvature,
                           turn_speed_limit)


@dataclass(frozen=True)
class Steering:
    """How to steer. Distances in m, angles in rad, times in s."""

    max_curvature: float          # 1/m: full lock, tan(max_steering) / wheelbase
    lookahead_min: float = 2.0    # about the wheelbase or more, or a car weaves
    lookahead_time: float = 1.0   # s of driving: the lookahead grows with speed
    turn_above: float = math.radians(20.0)   # B further off the nose: turn towards it first
    aligned: float = math.radians(10.0)      # ... until it is this close, then the line
    lateral_accel: float = 1.5    # m/s^2: slow down in tight turns


@dataclass(frozen=True)
class Command:
    speed: float       # m/s
    curvature: float   # 1/m, + left
    phase: int         # approach.TURN ... STOPPING
    left: float        # m to B: along the line, or straight while turning
    cross: float       # m left (+) of the line; 0 while turning


class Drive:
    """Drive from where the car is to `target`, and stop there."""

    def __init__(self, target: Point, approach: Approach, steering: Steering, start: Pose):
        self.target = target
        self.approach = approach
        self.steering = steering
        self.line: Optional[Line] = None
        self.speed = 0.0
        if abs(bearing_error(start, target)) <= steering.turn_above:
            self.line = Line((start.x, start.y), target)

    def tick(self, pose: Pose, measured: float, dt: float) -> Command:
        st = self.steering
        if self.line is None and abs(bearing_error(pose, self.target)) <= st.aligned:
            self.line = Line((pose.x, pose.y), self.target)
        lookahead = max(st.lookahead_min, st.lookahead_time * abs(measured))
        if self.line is None:
            left = math.hypot(self.target[0] - pose.x, self.target[1] - pose.y)
            cross = 0.0
            k = pursuit_curvature(pose, self.target, st.max_curvature)
        else:
            left, cross = self.line.progress((pose.x, pose.y))
            k = pursuit_curvature(pose, self.line.carrot((pose.x, pose.y), lookahead),
                                  st.max_curvature)
        speed, phase = self.approach.step(self.speed, dt, left, measured,
                                          turn_speed_limit(k, st.lateral_accel))
        if self.line is None and phase != STOPPING:
            phase = TURN
        self.speed = speed
        return Command(speed, k if speed > 0 else 0.0, phase, left, cross)
