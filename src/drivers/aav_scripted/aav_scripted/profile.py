"""The speed plan for one ScriptedDrive goal: speed up, hold, slow down.

No ROS imports, so the tests run anywhere.
"""

from __future__ import annotations

from typing import Optional

ACCELERATE, HOLD, DECELERATE, STOPPED = 0, 1, 2, 3


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
