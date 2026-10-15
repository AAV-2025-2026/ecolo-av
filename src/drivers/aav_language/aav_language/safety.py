"""
The drive server's rules: the hard limits, where it may drive, and who is driving.

No ROS imports, so the tests run anywhere. The drive server (drive_tools.py) checks every
request against these rules itself; the language model never decides them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Dict, Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Caps:
    """The drive server's own limits. Each one is a hard cap: a request above it is refused."""

    max_speed: float = 1.0              # m/s forward
    max_distance: float = 200.0         # m per command (drive, turn, go_to_gps)
    max_reverse_speed: float = 0.5      # m/s
    max_reverse_distance: float = 10.0  # m
    acceleration: float = 0.5           # m/s^2, how the server speeds up
    deceleration: float = 0.5           # m/s^2, how it slows down (stop() too)
    max_wait: float = 120.0             # s, for wait()
    max_turn_deg: float = 360.0         # degrees, for turn()
    min_radius: float = 0.0             # m; raised to the car's own, from ego


# Nodes that only run on the real car. bench mode runs spine_bridge too, but always next
# to spine_sim, its stand-in for the spine board.
CAR_ONLY_NODES = ('legacy_uart_bridge', 'encoder_udp', 'socket_can_sender',
                  'socket_can_receiver')


def effective_caps(caps: Caps, ego: Optional[Mapping[str, float]]) -> Caps:
    """
    Return the tighter of the server's caps and ego's own limits.

    ego is ego's parameters (max_speed, max_reverse_speed, max_acceleration,
    max_deceleration, wheelbase, max_steering_angle), or None when ego can't be asked.
    """
    if not ego:
        return caps
    out = caps
    if ego.get('max_speed', 0) > 0:
        out = replace(out, max_speed=min(out.max_speed, ego['max_speed']))
    if ego.get('max_reverse_speed', 0) > 0:
        out = replace(out, max_reverse_speed=min(out.max_reverse_speed,
                                                 ego['max_reverse_speed']))
    if ego.get('max_acceleration', 0) > 0:
        out = replace(out, acceleration=min(out.acceleration, ego['max_acceleration']))
    if ego.get('max_deceleration', 0) > 0:
        out = replace(out, deceleration=min(out.deceleration, ego['max_deceleration']))
    wheelbase, steer = ego.get('wheelbase', 0), ego.get('max_steering_angle', 0)
    if wheelbase > 0 and 0 < steer < math.pi / 2:
        out = replace(out, min_radius=max(out.min_radius, wheelbase / math.tan(steer)))
    return out


def check_drive(caps: Caps, distance: float, speed: float, reverse: bool) -> Optional[str]:
    """Why a drive of `distance` m at `speed` m/s is refused, or None when it's allowed."""
    if not (math.isfinite(distance) and math.isfinite(speed)):
        return 'distance and speed must be numbers'
    if distance <= 0:
        return 'distance must be more than 0 m'
    if speed <= 0:
        return 'speed must be more than 0 m/s'
    if reverse:
        if distance > caps.max_reverse_distance:
            return (f'reverse is limited to {caps.max_reverse_distance:g} m per command '
                    f'(asked {distance:g} m)')
        if speed > caps.max_reverse_speed:
            return (f'reverse is limited to {caps.max_reverse_speed:g} m/s '
                    f'(asked {speed:g} m/s)')
        return None
    if distance > caps.max_distance:
        return f'distance is limited to {caps.max_distance:g} m per command (asked {distance:g} m)'
    if speed > caps.max_speed:
        return f'speed is limited to {caps.max_speed:g} m/s (asked {speed:g} m/s)'
    return None


def check_turn(caps: Caps, angle_deg: float, radius: float, speed: float) -> Optional[str]:
    """Why a turn is refused, or None when it's allowed."""
    if not (math.isfinite(angle_deg) and math.isfinite(radius) and math.isfinite(speed)):
        return 'angle, radius and speed must be numbers'
    if angle_deg == 0:
        return 'the angle must not be 0'
    if abs(angle_deg) > caps.max_turn_deg:
        return f'turns are limited to {caps.max_turn_deg:g} degrees (asked {abs(angle_deg):g})'
    if radius <= 0:
        return 'the radius must be more than 0 m'
    if radius < caps.min_radius:
        return (f'the car cannot turn tighter than a {caps.min_radius:.1f} m radius '
                f'(asked {radius:g} m)')
    length = radius * math.radians(abs(angle_deg))
    if length > caps.max_distance:
        return (f'that arc is {length:.0f} m; commands are limited to '
                f'{caps.max_distance:g} m')
    if speed <= 0:
        return 'speed must be more than 0 m/s'
    if speed > caps.max_speed:
        return f'speed is limited to {caps.max_speed:g} m/s (asked {speed:g} m/s)'
    return None


@dataclass(frozen=True)
class Where:
    """What the server can tell about the ROS network it's on."""

    discovery_range: str          # ROS_AUTOMATIC_DISCOVERY_RANGE, '' when unset
    static_peers: str             # ROS_STATIC_PEERS, '' when unset
    sim_clock: bool               # someone publishes /clock (Gazebo, a replay)
    nodes: Tuple[str, ...]        # the node names it sees


def allowed_here(where: Where, car: bool) -> Optional[str]:
    """
    Why the server must not drive on this network, or None when it may.

    Without --car it drives only a stand-in: ROS discovery kept on this computer
    (LOCALHOST, no static peers) or a simulator's clock, and none of the car's own
    hardware nodes in sight. With --car it drives whatever it finds.
    """
    if car:
        return None
    real = [n for n in where.nodes if n in CAR_ONLY_NODES]
    if 'spine_bridge' in where.nodes and 'spine_sim' not in where.nodes:
        real.append('spine_bridge')
    if real:
        return (f"the real car's nodes are on this network ({', '.join(sorted(real))}); "
                'start the drive server with --car to drive it')
    local = where.discovery_range.upper() == 'LOCALHOST' and not where.static_peers
    if local or where.sim_clock:
        return None
    return ('this may be the real car: ROS discovery reaches other computers '
            f"(ROS_AUTOMATIC_DISCOVERY_RANGE={where.discovery_range or 'unset'}) and "
            'there is no simulator clock. Run the stand-ins with tools/ros.sh --local, '
            'or start the drive server with --car')


@dataclass(frozen=True)
class MuxInput:
    """One twist_mux input, from its configuration."""

    name: str
    topic: str
    priority: int
    timeout: float


@dataclass(frozen=True)
class MuxLock:
    """One twist_mux lock, from its configuration."""

    name: str
    topic: str
    priority: int
    timeout: float


def mux_config(params: Mapping) -> Tuple[Tuple[MuxInput, ...], Tuple[MuxLock, ...]]:
    """Read the inputs and locks from twist_mux's YAML (aav_mux/config/twist_mux.yaml)."""
    p = params.get('twist_mux', params).get('ros__parameters', params)
    inputs = tuple(sorted(
        (MuxInput(name, v['topic'], int(v['priority']), float(v['timeout']))
         for name, v in (p.get('topics') or {}).items()),
        key=lambda i: -i.priority))
    locks = tuple(MuxLock(name, v['topic'], int(v['priority']), float(v['timeout']))
                  for name, v in (p.get('locks') or {}).items())
    return inputs, locks


def mux_locks_from_diagnostics(statuses) -> Optional[Dict[str, bool]]:
    """
    Read twist_mux's locks from one /diagnostics message, or None if it isn't twist_mux's.

    statuses: (name, {key: value}) per DiagnosticStatus. twist_mux 4.5 sends, once a
    second, a status "twist_mux: Twist mux status" with a value per lock (seen on the
    turtle, 15 Oct): "lock locks.estop" = " locked (listening to /safety/estop @
    0.000000s with priority #255)", or " free (...)".
    """
    for name, values in statuses:
        if 'twist mux' not in name.lower() and 'twist_mux' not in name.lower():
            continue
        locks = {key[len('lock '):].split('.')[-1]: value.strip().startswith('locked')
                 for key, value in values.items() if key.startswith('lock ')}
        if locks:
            return locks
    return None


def mux_choice(inputs: Iterable[MuxInput], ages: Mapping[str, Optional[float]],
               locks: Iterable[MuxLock], lock_values: Mapping[str, Tuple[bool, float]]
               ) -> Dict[str, Optional[str]]:
    """
    Which input twist_mux passes on now, worked out from what reaches it.

    ages: seconds since each input's last message arrived (None = never). lock_values:
    each lock's last value and its age. twist_mux's own rules (aav_mux's YAML): an input
    counts while younger than its timeout, the highest priority wins, and a lock that is
    true blocks every input below its priority. Returns {'driver', 'blocked_by'}.
    """
    live = [i for i in inputs
            if ages.get(i.name) is not None and ages[i.name] <= i.timeout]
    live.sort(key=lambda i: -i.priority)
    top_lock = None
    for lock in locks:
        value, age = lock_values.get(lock.name, (False, math.inf))
        if value and (lock.timeout == 0 or age <= lock.timeout):
            if top_lock is None or lock.priority > top_lock.priority:
                top_lock = lock
    for i in live:
        if top_lock is not None and i.priority < top_lock.priority:
            return {'driver': None, 'blocked_by': top_lock.name}
        return {'driver': i.name, 'blocked_by': None}
    return {'driver': None, 'blocked_by': top_lock.name if top_lock else None}
