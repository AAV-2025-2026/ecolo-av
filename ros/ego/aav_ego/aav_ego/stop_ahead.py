"""
The stop point: where the car stops if it brakes fully now.

No ROS imports, so the tests run anywhere. ego publishes it on /ego/stop_point
(geometry_msgs/PoseStamped, frame base_link), from its twin of the car (trace_ahead.Twin),
so every screen and the stop-point check read one answer (docs/hud.md, "The squiggly line").

    the twin's state now ──▶ car model, full brake, the wheels held where they point
                         ──▶ step until the speed is 0 ──▶ where, how far, how long

The same shared car model as ego's trace (aav_description car_model.py): the brake's dead
time and lag, the drag, the bicycle. So the stop point and the end of a braking trace
agree. Its distance is the design's S(v) (docs/designs/2026-11-05_how-the-car-stops.md):
v times the brake's delay, plus v^2 / (2 max_brake), a little less for the drag.
Every number is a guess until car test 4.3.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from aav_description.car_model import Command, step

STOPPED = 0.01    # m/s: slower counts as stopped
MAX_TIME = 30.0   # s: a stop that takes longer is not found (a brake of 0?)


@dataclass(frozen=True)
class StopPoint:
    x: float          # m, base_link: where base_link stops
    y: float          # m
    yaw: float        # rad
    distance: float   # m, along the way there
    time: float       # s, from now
    found: bool       # False: still moving after MAX_TIME


def stop_point(cfg, state, dt: float = 0.02, max_time: float = MAX_TIME) -> StopPoint:
    """
    Return where the car stops if it brakes fully now, in base_link.

    cfg is the car model's ActuatorConfig, state its CarState now (the twin's); its x, y and
    yaw are ignored (base_link is where the car is). The throttle is let go, the brake
    pressed fully, the steering target held at the motor's setpoint. Nothing passed in is
    changed.
    """
    if dt <= 0.0:
        raise ValueError(f'dt must be positive, not {dt}')
    s = replace(state, x=0.0, y=0.0, yaw=0.0)
    brake = Command(steer=s.steer_setpoint, throttle=0.0, brake=1.0, reverse=s.v < 0.0)
    distance, t = 0.0, 0.0
    while abs(s.v) >= STOPPED:
        if t >= max_time:
            return StopPoint(s.x, s.y, s.yaw, distance, t, False)
        nxt = step(cfg, s, brake, dt)
        distance += math.hypot(nxt.x - s.x, nxt.y - s.y)
        s, t = nxt, t + dt
    return StopPoint(s.x, s.y, s.yaw, distance, t, True)


def s_of_v(v: float, tau: float, a: float) -> float:
    """Return the design's S(v) = v tau + v^2 / (2a): m to stop from v m/s."""
    v = abs(v)
    return v * tau + v * v / (2.0 * a)
