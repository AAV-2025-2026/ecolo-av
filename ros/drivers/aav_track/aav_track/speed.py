"""
The one speed policy every tracker drives with, so the trial compares steering only.

No ROS here. Built from aav_drive_to_point's own pieces:

| Part | From |
|---|---|
| cruise | Regulated Pure Pursuit's `desired_linear_vel` (nav2.yaml), or sim_speed:= |
| slow for a bend ahead | `line.turn_speed_limit`: at most `lateral_accel` sideways |
| stop at the path's end | `approach.Approach` on the stopping law (stop_law.py): v = v_cap(d) (7 Nov) |
| speed up | the velocity smoother's `max_accel` |

A tracker may lower it further (`Command.speed_cap`). The bend is looked for from the car
to a little past where it could stop (`preview`), so it slows before the bend, not in it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from aav_description import stop_law
from aav_description.stop_law import StopCurve
from aav_drive_to_point.approach import Approach, planned_deceleration
from aav_drive_to_point.line import turn_speed_limit
from aav_track.path import Path


@dataclass(frozen=True)
class SpeedPolicy:
    cruise: float               # m/s
    accel: float                # m/s^2, speeding up
    max_brake: float            # m/s^2, vehicle.yaml's full braking (half is planned)
    lateral_accel: float = 1.0  # m/s^2 sideways in a bend
    preview: float = 2.0        # m past the stopping distance to look for a bend
    creep: float = 0.1          # m/s: the least it asks for short of the end
    # The stopping law; None: from max_brake and the car model's other numbers. Never less
    # cautious than the old sqrt(2 a d) with a = max_brake / 2 (test_speed.py).
    curve: Optional[StopCurve] = None

    def __post_init__(self):
        # The approach checks the numbers itself.
        curve = self.curve or stop_law.from_numbers(self.max_brake)
        object.__setattr__(self, 'curve', curve)
        object.__setattr__(self, 'approach', Approach(
            cruise=self.cruise, accel=self.accel,
            decel=planned_deceleration(self.max_brake), creep=self.creep, stop_band=0.0,
            curve=curve))

    def step(self, path: Path, s: float, previous: float, measured: float, dt: float,
             cap: Optional[float] = None) -> float:
        """Return the speed to ask for: s m along `path`, last asked `previous` m/s."""
        ahead = self.curve.distance(max(measured, previous, 0.0))
        bend = path.max_curvature(s, s + ahead + self.preview)
        limit = turn_speed_limit(bend, self.lateral_accel)
        if cap is not None:
            limit = min(limit, max(cap, 0.0))
        speed, _ = self.approach.step(previous, dt, path.left(s), measured, limit)
        return speed if math.isfinite(speed) else 0.0
