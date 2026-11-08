"""
ego's trace: where the car is going over the next few seconds, like a tail but in front.

No ROS imports, so the tests run anywhere. The node publishes it on /ego/trace
(nav_msgs/Path, frame base_link); the page: docs/vehicle-model.md, "ego's trace".

ego keeps a twin of the car (Twin): the shared car model (aav_description car_model.py),
stepped every tick with what ego sent, its speed set to the measured one (/vehicle/odom)
while that is fresh. The trace starts from the twin, moved to base_link (x = y = yaw = 0),
and runs ahead with a copy of ego itself, the driver's request held:

    request held ──▶ copy of ego (its lead, ramps, limits) ──▶ speed, angle each step
                 ──▶ car model (speed loop, dead times, lags, steering motor, bicycle)
                 ──▶ poses every `every` steps, from now to now + horizon

So a driver sees where its request takes the car, lag and limits included, and can match
it against its plan. Every number in the model is a guess until car tests 3.10-3.12 and
4.1-4.5.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

from aav_description.car_model import CarState, Command, predict, SpeedLoop, step


@dataclass(frozen=True)
class Pose:
    t: float      # s from now
    x: float      # m, base_link
    y: float      # m
    yaw: float    # rad
    v: float      # m/s
    steer: float  # rad


class Twin:
    """ego's copy of the car: the car model, stepped with what ego sends."""

    def __init__(self, cfg, loop_config):
        self.cfg = cfg
        self.loop = SpeedLoop(loop_config)
        self.state = CarState()

    def measured(self, speed: float) -> None:
        """Take the car's measured speed (m/s)."""
        self.state = replace(self.state, v=speed)

    def sent(self, speed: float, angle: float, dt: float) -> None:
        """Answer what ego sent this tick (m/s, rad) with the twin's actuators."""
        if dt > 0.0:
            self.state = step(self.cfg, self.state, Command(steer=angle, speed=speed), dt,
                              self.loop)


def ego_commands(model, cmd, lead, steps: int, dt: float) -> List[Command]:
    """
    Return what ego would send each step for `steps` steps, the request held.

    model is ego's EgoModel, lead its LagLead while the lead runs (else None): both copied.
    """
    model = copy.deepcopy(model)
    lead = copy.deepcopy(lead)
    out = []
    for _ in range(steps):
        speed, angle, _ = model.step(cmd, dt, None if lead is None else lead.step)
        out.append(Command(steer=angle, speed=speed))
    return out


def trace(twin: Twin, model, cmd: Optional[Tuple[float, float]], lead,
          horizon: float, dt: float, every: int) -> List[Pose]:
    """
    Return the poses every `every` steps of dt, from now to `horizon` s ahead, in base_link.

    model is ego's EgoModel, cmd its request (None: stopping), lead its LagLead while the
    lead runs (None otherwise). Nothing passed in is changed.
    """
    steps = max(1, round(horizon / dt))
    start = replace(twin.state, x=0.0, y=0.0, yaw=0.0)
    states = predict(twin.cfg, start, ego_commands(model, cmd, lead, steps, dt), dt, horizon,
                     twin.loop)
    poses = [Pose(0.0, 0.0, 0.0, 0.0, start.v, start.steer)]
    for i, s in enumerate(states, 1):
        if i % every == 0 or i == len(states):
            poses.append(Pose(i * dt, s.x, s.y, s.yaw, s.v, s.steer))
    return poses
