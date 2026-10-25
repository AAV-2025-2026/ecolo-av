"""
The car's heading from the GPS receiver's own velocity (course over ground). No ROS here.

A GPS receiver measures its velocity from the Doppler shift of the satellites' signals, not
from one fix to the next, so it is good to about 0.05 m/s (a u-blox M8 or F9) even while
the position wanders by a metre. Its direction is where the antenna is going. On a car
that doesn't slide sideways, that is where the car points, or the opposite way when it
reverses: the heading. robot_localization can't get it by itself: it turns a world-frame
velocity into the car's frame with its own heading, so a heading error never shows.

    heading = the velocity's direction - the antenna's own direction of travel on the car

The antenna's direction on the car (beta) is 0 driving forward, pi reversing, and a
little more in a turn when the antenna is ahead of the rear axle (it swings outwards):

    the antenna's velocity in base_link = (v - w * y_a, w * x_a)
    beta = atan2(w * x_a, v - w * y_a)

v is the wheels' signed speed, w the turn rate, (x_a, y_a) the antenna from base_link.
Its uncertainty: the velocity's noise across the direction of travel, over the speed,
plus a floor for what the model leaves out (the tyres' slip, the timing).

The node (gps_heading.py) publishes it as an IMU's orientation for the global EKF.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple


@dataclass(frozen=True)
class CourseSettings:
    """When a velocity counts as a heading, and how sure it is. m/s and radians."""

    # Slower than this (the GPS's speed and the wheels' both), no heading: at 0.3 m/s,
    # 0.05 m/s of noise is already 10 degrees.
    min_speed: float = 0.3
    # The GPS's speed and the wheels' must agree to this: a spinning wheel, a GPS that
    # lost its lock or a stale velocity is no heading.
    max_speed_gap: float = 0.3
    # Added to every heading's standard deviation (rad): slip, the antenna's height
    # swaying, the velocity's time against the wheels'.
    floor: float = math.radians(2.0)


def wrap(angle: float) -> float:
    """Return an angle in [-pi, pi)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def antenna_direction(speed: float, turn: float, antenna: Tuple[float, float]) -> float:
    """Return the direction (rad) the antenna travels in base_link, at this speed and turn."""
    x_a, y_a = antenna
    return math.atan2(turn * x_a, speed - turn * y_a)


def heading(east: float, north: float, var_east: float, var_north: float, speed: float,
            turn: float, antenna: Tuple[float, float] = (0.0, 0.0),
            settings: CourseSettings = CourseSettings()) -> Optional[Tuple[float, float]]:
    """
    Return (heading rad, its variance rad^2) from the GPS's velocity, or None.

    east, north: the antenna's velocity (m/s, ENU) and their variances (m^2/s^2).
    speed: the wheels' signed speed (m/s, negative reversing); turn: the turn rate (rad/s).
    None when either speed is under settings.min_speed, or they disagree by more than
    settings.max_speed_gap: then the velocity says nothing about the heading.
    """
    ground = math.hypot(east, north)
    if (not all(map(math.isfinite, (east, north, var_east, var_north, speed, turn)))
            or ground < settings.min_speed or abs(speed) < settings.min_speed
            or abs(ground - math.hypot(speed - turn * antenna[1], turn * antenna[0]))
            > settings.max_speed_gap):
        return None
    course = math.atan2(north, east)
    # The noise across the direction of travel turns the course; along it, only the speed.
    across = var_east * math.sin(course) ** 2 + var_north * math.cos(course) ** 2
    variance = max(across, 0.0) / ground ** 2 + settings.floor ** 2
    return wrap(course - antenna_direction(speed, turn, antenna)), variance


def quaternion_z(yaw: float) -> Tuple[float, float, float, float]:
    """Return (x, y, z, w) of a turn by yaw about z."""
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)
