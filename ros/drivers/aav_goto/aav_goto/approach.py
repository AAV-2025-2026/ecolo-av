r"""
The speed for driving to B: speed up gently, hold, then slow down by the distance left.

No ROS here, so the tests run anywhere. goto_driver.py asks `Approach.step` every tick.

```text
 speed
   ^          hold (cruise)
   |      +-------------+
   |     /               \   v = sqrt(2 a (d - lead v))   a = half the measured braking
   |    / up at          \
   |   /  `accel`         \
   +--/--------------------\---> distance left to B
     A                      B: stop (d <= stop_band)
```

Slowing down follows the distance left, not the time: v = sqrt(2 a d) is the speed from
which braking at `a` stops exactly at B. So a car that slows a little late (the brake's
lag, the spine's speed loop) sees d shrink faster, and the command drops to match: it
corrects itself. Speeding up follows the time (a ramp), as sqrt(2 a d) from the start is
zero at the start.

Why not aav_scripted's speed_profile.py: it holds for a distance or a time, then slows at a
fixed rate from wherever it is. Here the slowing must END at B whatever happened before
(a stop sign, a slow start), so it is computed from the distance left on every tick.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Tuple

# The feedback's phases (aav_interfaces/action/GoTo).
TURN, ACCELERATE, HOLD, DECELERATE, STOPPING = 0, 1, 2, 3, 4

BRAKE_FRACTION = 0.5    # of the measured braking: READ-ME-TESTS.md 5.2


def planned_deceleration(max_brake: float, fraction: float = BRAKE_FRACTION) -> float:
    """Return the deceleration to plan with (m/s^2): a fraction of full braking."""
    if not (math.isfinite(max_brake) and max_brake > 0):
        raise ValueError(f'max_brake must be above 0 m/s^2 (got {max_brake})')
    if not 0 < fraction <= 1:
        raise ValueError(f'the braking fraction must be in (0, 1] (got {fraction})')
    return max_brake * fraction


def stopping_distance(speed: float, deceleration: float) -> float:
    """Return the metres it takes to stop from `speed` at `deceleration`."""
    return speed * speed / (2.0 * deceleration)


@dataclass(frozen=True)
class Approach:
    """One drive's speed plan. Speeds in m/s, accelerations in m/s^2, distances in m."""

    cruise: float              # the speed to hold
    accel: float               # how fast to speed up (gently)
    decel: float               # how fast to slow down: half the measured braking
    lead: float = 0.0          # s: the car's delay in braking; start slowing this much sooner
    stop_band: float = 0.05    # m: this close to B (or past it), command zero
    ahead: float = 0.5         # m/s: never command more than this above the measured speed
    creep: float = 0.1         # m/s: the least it asks for short of B (a speed loop's deadband)

    def __post_init__(self):
        for name in ('cruise', 'accel', 'decel'):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0):
                raise ValueError(f'{name} must be above 0 (got {value})')
        if self.lead < 0 or self.stop_band < 0 or self.ahead <= 0 or self.creep < 0:
            raise ValueError('lead, stop_band and creep must not be negative; ahead above 0')

    def braking_speed(self, left: float, measured: float = 0.0) -> float:
        """Return the fastest speed from which slowing at `decel` stops at B."""
        room = left - max(measured, 0.0) * self.lead
        return math.sqrt(2.0 * self.decel * room) if room > 0 else 0.0

    def step(self, previous: float, dt: float, left: float, measured: float,
             limit: float = math.inf) -> Tuple[float, int]:
        """
        Return (the speed to command, the phase).

        previous: the last speed commanded. left: metres to B (negative once past it).
        measured: the car's speed. limit: a cap for this tick (a tight turn).
        """
        if left <= self.stop_band:
            return 0.0, STOPPING
        up = min(previous + self.accel * max(dt, 0.0), max(measured, 0.0) + self.ahead)
        brake = self.braking_speed(left, measured)
        cruise = min(self.cruise, limit)
        speed = min(up, cruise, brake)
        if brake <= min(up, cruise):
            phase = DECELERATE
            # Short of B but nearly stopped (the lead, a speed loop that won't creep):
            # keep rolling slowly, or it would stop before B and stay there.
            speed = max(speed, min(self.creep, math.sqrt(2.0 * self.decel * left)))
        elif cruise <= up:
            phase = HOLD
        else:
            phase = ACCELERATE
        return max(speed, 0.0), phase

    def ideal_time(self, distance: float) -> float:
        """Return the seconds a perfect car takes for `distance` m (for a time limit)."""
        up = stopping_distance(self.cruise, self.accel)
        down = stopping_distance(self.cruise, self.decel)
        if up + down >= distance:
            # A triangle: never reaches cruise.
            peak = math.sqrt(2.0 * distance * self.accel * self.decel / (self.accel + self.decel))
            return peak / self.accel + peak / self.decel
        return (self.cruise / self.accel + self.cruise / self.decel
                + (distance - up - down) / self.cruise)
