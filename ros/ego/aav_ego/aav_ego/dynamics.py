"""
The car as a body with weight: what its mass, its load and its shape allow.

No ROS imports, so the tests run anywhere (test/test_dynamics.py).

ego (ackermann.EgoModel) takes two limits from here, and logs the rest at start-up:
- how hard the car can speed up: the motor's push, shared by the car and its load;
- how fast it may take a turn: the sideways acceleration, below sliding and tipping;
- (logged) how far it needs to stop, and the energy it carries.

What the mass changes, and what it doesn't:

  | Changes with the load                 | Doesn't                                       |
  |---------------------------------------|-----------------------------------------------|
  | speeding up: the same motor, more     | the speed a turn allows: sliding (grip x g)   |
  | mass, a = F / m                       | and tipping (g x half the track / the height  |
  | braking: the same brakes, more mass   | of the centre of mass) both cancel the mass   |
  | the energy in a crash: 1/2 m v^2      |                                               |

Two things ego never does with these numbers: it never brakes less hard because the car
is heavy (that would only lengthen the stop), and it never steers less sharply in a turn
(it slows down instead, so the car stays on the path it was given).

The numbers come from vehicle.yaml (mass, track, centre_of_mass, tyre_grip, and the
actuators' max_accel and max_brake) and ego.yaml (payload, max_lateral_accel). Most are
guesses until the car is weighed and tested: docs/measure-the-car.md, docs/tests.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List

G = 9.81            # m/s^2
MARGIN = 2.0        # ego stays at half the sliding and tipping limits: their inputs are guesses
# s from an obstacle seen to the brakes biting: the radar, twist_mux, ego and the brake
# actuator (docs/costmaps.md: "about 0.4 m" at 1 m/s).
REACTION = 0.4


@dataclass
class Body:
    mass: float = 181.0                 # kg, the empty car: about 400 lb (vehicle.yaml)
    payload: float = 0.0                # kg aboard: people, cargo. May change while running
    track: float = 0.77                 # m between the left and right wheels' centres
    cg_height: float = 0.55             # m, the centre of mass above the ground
    tyre_grip: float = 0.7              # the most the tyres can push, in g, before they slide
    full_throttle_accel: float = 1.5    # m/s^2, the empty car at full throttle, on the flat
    full_brake_decel: float = 3.0       # m/s^2, the empty car at full brake
    max_lateral_accel: float = 2.0      # m/s^2 sideways in a turn: comfort for the people aboard


# What a running ego lets anyone change, and its range (ackermann.live_change).
LIVE_BODY = {'payload': (0.0, 300.0)}   # kg: two adults and some cargo at most


def total_mass(body: Body) -> float:
    return body.mass + body.payload


def load_share(body: Body) -> float:
    """Return the empty car's share of the total mass: a motor's or brake's push scales by it."""
    return body.mass / total_mass(body)


def speed_up_limit(body: Body) -> float:
    """Return the hardest (m/s^2) the loaded car can speed up: its motor, then its tyres."""
    return min(body.full_throttle_accel * load_share(body), body.tyre_grip * G)


def braking_limit(body: Body) -> float:
    """Return the hardest (m/s^2) the loaded car can brake: its brakes, then its tyres."""
    return min(body.full_brake_decel * load_share(body), body.tyre_grip * G)


def sliding_accel(body: Body) -> float:
    """Return the sideways acceleration (m/s^2) at which the tyres slide."""
    return body.tyre_grip * G


def tipping_accel(body: Body) -> float:
    """Return the sideways acceleration (m/s^2) at which the inside wheels lift."""
    return G * (body.track / 2.0) / body.cg_height


def lateral_limit(body: Body) -> float:
    """Return the sideways acceleration (m/s^2) ego allows: comfort, or half of slide or tip."""
    return min(body.max_lateral_accel,
               sliding_accel(body) / MARGIN, tipping_accel(body) / MARGIN)


def curve_speed(body: Body, curvature: float) -> float:
    """Return the fastest (m/s) a turn of this curvature (1/m) allows; inf when straight."""
    k = abs(curvature)
    return math.inf if k < 1e-9 else math.sqrt(lateral_limit(body) / k)


def stopping_distance(body: Body, speed: float, decel: float, reaction: float = REACTION) -> float:
    """Return the distance (m) to stop from speed: the reaction time, then braking at decel."""
    return abs(speed) * reaction + speed * speed / (2.0 * decel)


def energy(body: Body, speed: float) -> float:
    """Return the energy of motion (J): 1/2 m v^2, the load included."""
    return 0.5 * total_mass(body) * speed * speed


def describe(body: Body, wheelbase: float, max_steering_angle: float, max_speed: float,
             max_acceleration: float, max_deceleration: float) -> List[str]:
    """Return short lines for ego's log: what this body allows with ego's limits."""
    speed_up = min(max_acceleration, speed_up_limit(body))
    brake = min(max_deceleration, braking_limit(body))
    lock = wheelbase / math.tan(max_steering_angle)
    lines = [
        f'body: {body.mass:.0f} kg + {body.payload:.0f} kg aboard',
        f'speeds up at {speed_up:.2f} m/s^2 at most (the motor could give '
        f'{speed_up_limit(body):.2f})',
        f'stops from {max_speed:g} m/s in {stopping_distance(body, max_speed, brake):.2f} m, '
        f'braking at {brake:.2f} m/s^2 after {REACTION:g} s',
        f'turns: at most {lateral_limit(body):.1f} m/s^2 sideways (slides at '
        f'{sliding_accel(body):.1f}, tips at {tipping_accel(body):.1f}); full lock '
        f'({lock:.2f} m) at up to {curve_speed(body, 1.0 / lock):.1f} m/s',
        f'carries {energy(body, max_speed):.0f} J at {max_speed:g} m/s',
    ]
    if braking_limit(body) < max_deceleration:
        lines.append(f'WARNING: with {body.payload:.0f} kg aboard the brakes give only '
                     f'{braking_limit(body):.2f} m/s^2, less than max_deceleration '
                     f'{max_deceleration:g}: stops take longer than ego plans')
    return lines
