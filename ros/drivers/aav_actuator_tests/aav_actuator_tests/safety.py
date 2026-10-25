"""
The actuator tests' safety rules: who may run what, how fast, and when to stop.

No ROS here. The node (actuator_test.py) asks these functions, and stops the car whenever
one says no. Every rule errs towards "this is the real car".

| Rule | Where |
|---|---|
| What we're driving: REAL, SIM, BENCH, REPLAY, or UNKNOWN (= REAL) | source_kind |
| Whether a test may start, its speed cap, and whether to ask first | decide |
| The person types the test's name to start it on the real car | confirmed |
| Speed, distance and time limits per test, checked every tick | Envelope.breach |
| Someone else is driving (the joystick outranks the tests) | taken_over |
"""

from __future__ import annotations

from dataclasses import dataclass
import enum
import math
from typing import Iterable, Mapping, Optional, Sequence, Tuple

REAL_CAP = 1.0         # m/s: never faster on the real car (ego.yaml's max_speed, 15 Oct)
STANDS_CAP = 0.3       # m/s with the wheels off the ground (READ-ME-TESTS.md stage 3)
SIM_DEFAULT_CAP = 3.0  # m/s in Gazebo, unless --max-speed says otherwise
SIM_MAX_CAP = 5.0      # m/s: ego's own ceiling for a simulator (sim_max_speed)

# aav_interfaces/SensorSource's values.
SOURCE_REAL, SOURCE_SIM, SOURCE_BENCH, SOURCE_REPLAY = 0, 1, 2, 3


class Kind(enum.Enum):
    """What /system/source says we're driving."""

    REAL = 'REAL'
    SIM = 'SIM'
    BENCH = 'BENCH'
    REPLAY = 'REPLAY'
    UNKNOWN = 'UNKNOWN'   # nobody announced: treated as the real car


def source_kind(announcements: Mapping[str, Sequence[int]]) -> Kind:
    """
    Merge /system/source's announcements (announcer -> its entries' source values).

    Anything REAL makes it REAL, even beside a simulator: one real actuator is enough.
    """
    values = [v for entries in announcements.values() for v in entries]
    if not values:
        return Kind.UNKNOWN
    if SOURCE_REAL in values:
        return Kind.REAL
    if SOURCE_REPLAY in values:
        return Kind.REPLAY
    if SOURCE_BENCH in values:
        return Kind.BENCH
    return Kind.SIM


@dataclass(frozen=True)
class Decision:
    """Whether a test may run, and how."""

    allowed: bool
    reason: str            # why not, or a note on what was decided
    cap: float = 0.0       # m/s: the hard speed cap for this run
    confirm: bool = False  # ask the person to type the test's name first
    real: bool = False     # treat it as the real car


def decide(kind: Kind, sim: bool, stands: bool, stage: int,
           requested_cap: Optional[float] = None) -> Decision:
    """
    Decide whether this test (stage 3 or 4 of READ-ME-TESTS.md) may run, and its speed cap.

    sim: the user said --sim (Gazebo, simulated time). stands: --stands (wheels off the
    ground). requested_cap: --max-speed, or None for the default.
    """
    if requested_cap is not None and not (math.isfinite(requested_cap) and requested_cap > 0):
        return Decision(False, f'--max-speed must be above 0 m/s (got {requested_cap})')
    if kind is Kind.REPLAY:
        return Decision(False, '/system/source says REPLAY: a recording plays; there is '
                               'nothing to drive')
    if sim and kind is not Kind.SIM:
        return Decision(False, f'--sim, but /system/source says {kind.value}. '
                               'Start Gazebo first (pixi run sim ...), on this ROS domain')
    if not sim and kind is Kind.SIM:
        return Decision(False, 'Gazebo announces SIM on /system/source: add --sim '
                               '(simulated time, this computer only)')

    if kind in (Kind.REAL, Kind.UNKNOWN):
        if stage == 3 and not stands:
            return Decision(False, 'a stage-3 test on the real car runs with the wheels off '
                                   'the ground: put it on stands and add --stands')
        if stage == 4 and stands:
            return Decision(False, 'a stage-4 test needs the wheels on the ground, in an '
                                   'empty lot: drop --stands')
        if requested_cap is not None and requested_cap > REAL_CAP:
            return Decision(False, f'the real car is capped at {REAL_CAP} m/s '
                                   f'(asked {requested_cap})')
        cap = REAL_CAP if requested_cap is None else requested_cap
        if stands:
            cap = min(cap, STANDS_CAP)
        note = ('nobody announced /system/source: treated as the real car'
                if kind is Kind.UNKNOWN else 'the real car')
        return Decision(True, note, cap, confirm=True, real=True)

    if kind is Kind.BENCH:
        if requested_cap is not None and requested_cap > REAL_CAP:
            return Decision(False, f"the bench runs the real car's limits: at most {REAL_CAP} "
                                   f'm/s (asked {requested_cap})')
        cap = REAL_CAP if requested_cap is None else requested_cap
        return Decision(True, 'the bench (stand-ins)',
                        min(cap, STANDS_CAP) if stands else cap)

    # Gazebo
    cap = SIM_DEFAULT_CAP if requested_cap is None else requested_cap
    if cap > SIM_MAX_CAP:
        return Decision(False, f'Gazebo tops out at {SIM_MAX_CAP} m/s (ego sim_max_speed); '
                               f'asked {cap}')
    return Decision(True, 'Gazebo', min(cap, STANDS_CAP) if stands else cap)


def confirmed(typed: Optional[str], test: str) -> bool:
    """Return True if the person typed the test's name exactly (spaces aside)."""
    return typed is not None and typed.strip() == test


@dataclass(frozen=True)
class Envelope:
    """The limits one test runs inside. Crossing any of them stops the car at once."""

    max_speed: float     # m/s, measured
    max_distance: float  # m since the test started
    max_time: float      # s since the test started

    def breach(self, speed: float, distance: float, elapsed: float) -> Optional[str]:
        """Why the test must stop now, or None."""
        if not math.isfinite(speed):
            return 'the measured speed is not a number'
        if abs(speed) > self.max_speed:
            return f'speed {abs(speed):.2f} m/s is over the limit {self.max_speed:.2f} m/s'
        if distance > self.max_distance:
            return f'drove {distance:.1f} m, over the limit {self.max_distance:.1f} m'
        if elapsed > self.max_time:
            return f'ran {elapsed:.0f} s, over the limit {self.max_time:.0f} s'
        return None


def speed_limit(cap: float) -> float:
    """Return the measured speed that aborts a test capped at `cap` (some overshoot)."""
    return cap * 1.2 + 0.1


def taken_over(ours: Iterable[Tuple[float, float]], theirs: Tuple[float, float],
               tolerance: float = 1e-3) -> bool:
    """
    Whether twist_mux's output (theirs: speed, turn rate) is none of our recent commands.

    True means a higher-priority driver (the joystick, the keyboard) is driving.
    """
    return not any(abs(v - theirs[0]) <= tolerance and abs(w - theirs[1]) <= tolerance
                   for v, w in ours)


STANDS_CHECKLIST = (
    'All four wheels are OFF the ground, on stands',
    'Someone holds the e-stop, and knows to press it',
    "The 2025-26 team's drive software is stopped (only our stack drives)",
    'Nobody near the wheels or the steering linkage',
    f'This test caps the speed at {STANDS_CAP} m/s (READ-ME-TESTS.md, stage 3)',
)

LOT_CHECKLIST = (
    'Stage 3 passed on stands, and the ESP32 timeout fix (test 3.9) is in',
    'A safety driver in the seat, holding the joystick: its deadman outranks this test',
    'Someone else holds the e-stop',
    'An empty lot: nobody in the way, and the space this test needs (shown above) is clear',
    'Walking pace first: start with the default speed cap',
)


def checklist(stands: bool) -> Tuple[str, ...]:
    """Return what to check before a test on the real car (READ-ME-TESTS.md, Before)."""
    return STANDS_CHECKLIST if stands else LOT_CHECKLIST
