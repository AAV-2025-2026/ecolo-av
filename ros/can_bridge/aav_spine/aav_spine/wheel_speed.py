"""
The front wheels' speeds, from the wheel nodes' CAN frames, for spine_bridge.

No ROS imports, so it runs and tests anywhere. The frames are WHEEL_SPEED_L (0x200)
and WHEEL_SPEED_R (0x201), already unpacked by can_codec.

Two jobs:
- keep the latest reading of each wheel, give it a sign when the sensor can't
  (one Hall sensor sees only a magnitude), and say when a pair is ready to publish;
- turn the front wheels' mean speed into the speed of base_link, under the rear axle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional

from aav_spine import can_codec as cc

SIDES = {cc.WHEEL_SPEED_L_ID: 'left', cc.WHEEL_SPEED_R_ID: 'right'}


@dataclass
class Wheel:
    """One wheel's latest frame."""

    speed: float          # m/s, as sent: a magnitude unless direction_known
    pulses: int
    direction_known: bool
    time: float           # s, when it arrived


@dataclass
class Reading:
    """Both front wheels, signed, for /vehicle/wheels (WheelSpeeds)."""

    left: float
    right: float
    left_fresh: bool
    right_fresh: bool
    direction_measured: bool
    left_pulses: int
    right_pulses: int

    def mean(self) -> Optional[float]:
        """Return the mean of the two wheels, or None unless both are fresh."""
        if self.left_fresh and self.right_fresh:
            return (self.left + self.right) / 2.0
        return None


def drive_sign(measured_speed: Optional[float], target_speed: Optional[float]) -> float:
    """
    Return +1 or -1: which way the car is going, for a sensor that only sees magnitude.

    The spine's measured speed first, then the commanded speed, then forward.
    """
    for v in (measured_speed, target_speed):
        if v:
            return math.copysign(1.0, v)
    return 1.0


def rear_axle_speed(front_mean: float, steering_angle: float) -> float:
    """
    Return base_link's speed (under the rear axle) from the front wheels' mean speed.

    In a turn the front axle travels on a wider circle than the rear one: with the
    bicycle model, v_rear = v_front * cos(steering). The two front wheels' mean is
    close to the front axle's centre (within 0.2 % at full lock on this car).
    """
    return front_mean * math.cos(steering_angle)


class FrontWheels:
    """The latest frame from each front wheel node."""

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.wheels: Dict[str, Wheel] = {}
        self.unpublished = set()

    def update(self, can_id: int, values: dict, now: float) -> bool:
        """
        Store one unpacked WHEEL_SPEED frame. Return True when it's time to publish.

        That is once both wheels have sent since the last publish, or at once if the
        other wheel has gone quiet: about 100 Hz either way.
        """
        side = SIDES[can_id]
        self.wheels[side] = Wheel(values['wheel_speed'], int(values['pulse_count']),
                                  bool(values['direction_known']), now)
        self.unpublished.add(side)
        other = 'right' if side == 'left' else 'left'
        if other in self.unpublished or not self.fresh(other, now):
            self.unpublished.clear()
            return True
        return False

    def fresh(self, side: str, now: float) -> bool:
        w = self.wheels.get(side)
        return w is not None and now - w.time <= self.timeout

    def reading(self, now: float, sign: float) -> Reading:
        """Both wheels at `now`; `sign` (from drive_sign) for a wheel that sent a magnitude."""
        def signed(side):
            w = self.wheels.get(side)
            if w is None:
                return 0.0
            return w.speed if w.direction_known else sign * abs(w.speed)

        def pulses(side):
            w = self.wheels.get(side)
            return w.pulses if w else 0

        known = [w.direction_known for w in self.wheels.values()]
        return Reading(
            left=signed('left'), right=signed('right'),
            left_fresh=self.fresh('left', now), right_fresh=self.fresh('right', now),
            direction_measured=bool(known) and all(known),
            left_pulses=pulses('left'), right_pulses=pulses('right'))
