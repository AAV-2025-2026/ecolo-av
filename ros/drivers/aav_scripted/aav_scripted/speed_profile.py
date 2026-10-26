"""
The speed plan for one ScriptedDrive goal: speed up, hold, slow down.

No ROS imports, so the tests run anywhere.
"""

from __future__ import annotations

import math
from typing import Optional

ACCELERATE, HOLD, DECELERATE, STOPPED = 0, 1, 2, 3


def goal_problem(target_speed: float, acceleration: float, deceleration: float,
                 hold_time: float, hold_distance: float, max_speed: float) -> Optional[str]:
    """Why a goal can't run, or None. Checked before the goal is accepted."""
    numbers = (target_speed, acceleration, deceleration, hold_time, hold_distance)
    if not all(math.isfinite(n) for n in numbers):
        return 'every number in the goal must be finite'
    if abs(target_speed) > max_speed:
        return f'|target_speed| above max_speed {max_speed}'
    if acceleration <= 0 or deceleration <= 0:
        return 'acceleration and deceleration must be positive'
    if hold_distance < 0:
        return 'hold_distance must not be negative'
    if hold_distance == 0 and hold_time < 0:
        return 'hold_time must not be negative'
    return None


def stop_reason(estop: bool, taken_over: bool, needs_odom: bool,
                odom_fresh: bool) -> Optional[str]:
    """Why a running goal must end now, or None."""
    if estop:
        return 'e-stop'
    if taken_over:
        return 'someone else is driving'
    if needs_odom and not odom_fresh:
        return 'odometry stopped arriving'
    return None


class SpeedProfile:

    def __init__(self, target_speed: float, acceleration: float, deceleration: float,
                 hold_time: float, hold_distance: float):
        if acceleration <= 0 or deceleration <= 0:
            raise ValueError('acceleration and deceleration must be positive')
        if hold_distance <= 0 and hold_time < 0:
            raise ValueError('hold_time must not be negative')
        self.target = target_speed
        self.accel = acceleration
        self.decel = deceleration
        self.hold_time = hold_time
        self.hold_distance = hold_distance
        self.speed = 0.0
        self.phase = ACCELERATE if target_speed != 0 else STOPPED
        self._held = 0.0
        self._hold_start: Optional[float] = None

    def cancel(self):
        """Slow down and stop from wherever the profile is."""
        if self.phase != STOPPED:
            self.phase = DECELERATE

    def stop(self):
        """Stop at once: zero from now on (an e-stop, or someone else driving)."""
        self.speed = 0.0
        self.phase = STOPPED

    def step(self, dt: float, distance: float = 0.0) -> float:
        """Advance by dt seconds; distance is metres travelled so far. Return the speed."""
        if self.phase == ACCELERATE:
            step = self.accel * dt
            if abs(self.target - self.speed) <= step:
                self.speed = self.target
                self.phase = HOLD
                self._hold_start = distance
            else:
                self.speed += step if self.target > self.speed else -step
        elif self.phase == HOLD:
            self._held += dt
            if self.hold_distance > 0:
                done = abs(distance - self._hold_start) >= self.hold_distance
            else:
                done = self._held >= self.hold_time
            if done:
                self.phase = DECELERATE
        elif self.phase == DECELERATE:
            step = self.decel * dt
            if abs(self.speed) <= step:
                self.speed = 0.0
                self.phase = STOPPED
            else:
                self.speed -= step if self.speed > 0 else -step
        return self.speed
