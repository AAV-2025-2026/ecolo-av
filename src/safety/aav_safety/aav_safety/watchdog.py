"""
The sensor watchdog's logic: is each sensor alive, sane and moving? No ROS here.

sensor_watchdog (the node) tells this module what arrived and when; this module says, for
each input, OK or what is wrong, and whether the automatic drivers must stop (twist_mux's
sensors lock). READ-ME-FULL-SIMULATION.md step 6; docs/simulation.md, "Sensor failures
on purpose".

What counts as wrong, per input (each check only where its rule asks for it):

  NEVER   nothing yet
  STALE   nothing good for max_age seconds (a cable pulled, a driver dead)
  NAN     the newest message has NaN or inf in it (a driver's bad parse)
  NO FIX  a GPS fix that says it has none, or NaN: the GPS counts as lost (STALE after
          max_age), as navsat_transform ignores those fixes too
  FROZEN  the same values again and again for frozen_after seconds (a driver stuck,
          sending its last message with fresh stamps). For a camera only while the car
          moves: a still car in a still world sees the same picture
  JUMP    two GPS fixes further apart than max_jump_speed allows in the time between
          their stamps, plus jump_margin for the fixes' own noise. Latched: the position
          after a jump can't be trusted until a person says so (clear())
  DISAGREE  the wheels' speed or turn against the IMU's, where the odom rule has a
          cross_check (wheel_check.py): a wheel speed frozen while the car speeds up,
          brakes or turns. Latched, as a jump

Times are seconds on the node's clock (Gazebo's, in the simulator).
"""

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple

from aav_safety.wheel_check import CrossCheck, DISAGREE, WheelCheck

OK = 'OK'
NEVER = 'NEVER'
STALE = 'STALE'
NAN = 'NAN'
FROZEN = 'FROZEN'
JUMP = 'JUMP'

KINDS = ('odom', 'imu', 'gps', 'image', 'cloud')
EARTH_RADIUS = 6371000.0    # m
MOVING = 0.2                # m/s: faster than this, the camera's picture must change


@dataclass(frozen=True)
class Rule:
    """How to watch one input. 0 turns a check off."""

    name: str
    topic: str
    kind: str                   # one of KINDS: which message, and what is in it
    max_age: float              # s without a good message: STALE
    stop: bool = True           # stop the automatic drivers while it isn't OK
    frozen_after: float = 0.0   # s of identical values: FROZEN
    max_jump_speed: float = 0.0  # m/s between two GPS fixes: JUMP
    jump_margin: float = 5.0    # m more, for the noise of two fixes (0.5 m each, in Gazebo)
    cross_check: Optional[CrossCheck] = None    # odom only: the wheels against the IMU

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f'{self.name}: kind {self.kind!r} is not one of {KINDS}')
        if not self.max_age > 0.0:
            raise ValueError(f'{self.name}: max_age must be a positive number of seconds')
        if self.cross_check is not None and self.kind != 'odom':
            raise ValueError(f'{self.name}: only an odom input has a cross check')


def finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(v) for v in values)


def ground_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Return the metres between two (latitude, longitude) points, in degrees: short spans."""
    lat = math.radians((a[0] + b[0]) / 2.0)
    dy = math.radians(b[0] - a[0]) * EARTH_RADIUS
    dx = math.radians(b[1] - a[1]) * EARTH_RADIUS * math.cos(lat)
    return math.hypot(dx, dy)


class Watch:
    """One input's state, from what arrived."""

    def __init__(self, rule: Rule):
        self.rule = rule
        self.heard = None          # when anything last arrived
        self.good = None           # when a good message last arrived
        self.bad = None            # what was wrong with the newest message, or None
        self.digest = None         # the newest values, to spot a frozen sensor
        self.same_since = None     # when the values stopped changing
        self.fix = None            # the newest good GPS fix: (stamp, latitude, longitude)
        self.jumped = None         # the jump that latched, as text, until clear()
        # The wheels against the IMU (odom only): fed by arrived() and imu().
        self.cross = WheelCheck(rule.cross_check) if rule.cross_check is not None else None

    def arrived(self, now: float, values: Sequence[float] = (), digest=None,
                fix: Optional[Tuple[float, float]] = None, has_fix: bool = True,
                speed: Optional[float] = None, stamp: Optional[float] = None):
        """
        Note a message: its numbers (NaN check), a digest of it (frozen check), a GPS fix.

        speed is the car's newest wheel speed (m/s), for the camera's frozen check. stamp
        is the fix's own time (s): fixes can arrive two at once, so their arrival times
        say nothing about how far apart they were taken.
        """
        rule = self.rule
        self.heard = now
        if rule.kind == 'gps' and (not has_fix or fix is None or not finite(fix)):
            self.bad = 'NO FIX'
            return
        if not finite(values):
            self.bad = NAN
            return
        self.bad = None
        self.good = now
        if self.cross is not None and len(values) >= 3:
            self.cross.wheels(now, values[0], values[2])    # forward speed, turn rate
        if rule.frozen_after > 0.0 and digest is not None:
            moving = rule.kind != 'image' or (speed is not None and abs(speed) > MOVING)
            if digest != self.digest or not moving:
                self.same_since = now
            self.digest = digest
        if rule.kind == 'gps':
            taken = now if stamp is None else stamp
            if self.fix is not None and rule.max_jump_speed > 0.0 and self.jumped is None:
                dt = taken - self.fix[0]
                metres = ground_distance(self.fix[1:], fix)
                if dt > 0.0 and metres > rule.max_jump_speed * dt + rule.jump_margin:
                    self.jumped = f'{metres:.1f} m in {dt:.2f} s'
            if self.fix is None or taken > self.fix[0]:     # not an old fix, late
                self.fix = (taken, fix[0], fix[1])

    def state(self, now: float) -> Tuple[str, str]:
        """Return (OK or what is wrong, a few words for a person)."""
        rule = self.rule
        if self.jumped is not None:
            return JUMP, f'jumped {self.jumped}: clear it once the position is right'
        why = self.cross.update(now) if self.cross is not None else None
        if why is not None:
            return DISAGREE, why + ': clear it once the wheels are right'
        if self.heard is None:
            return NEVER, 'nothing yet'
        if self.bad == NAN:
            return NAN, 'NaN or inf in the newest message'
        age = now - self.good if self.good is not None else math.inf
        if age > rule.max_age:
            why = 'no fix' if self.bad == 'NO FIX' else 'nothing'
            since = f'for {age:.1f} s' if math.isfinite(age) else 'yet'
            return STALE, f'{why} {since} (more than {rule.max_age:g} s)'
        if (rule.frozen_after > 0.0 and self.same_since is not None
                and now - self.same_since > rule.frozen_after):
            return FROZEN, f'the same for {now - self.same_since:.1f} s'
        return OK, f'{age:.1f} s old'

    def clear(self):
        self.jumped = None
        if self.cross is not None:
            self.cross.clear()


class Watchdog:
    """Every input's Watch, and the verdict: whether the automatic drivers may drive."""

    def __init__(self, rules: Sequence[Rule]):
        self.watches = {r.name: Watch(r) for r in rules}

    def imu(self, now: float, forward: float, yaw_rate: float):
        """Note an IMU sample for every cross check: forward m/s^2, yaw rate rad/s."""
        for watch in self.watches.values():
            if watch.cross is not None:
                watch.cross.imu(now, forward, yaw_rate)

    def cross_checked(self) -> bool:
        return any(w.cross is not None for w in self.watches.values())

    def states(self, now: float):
        """Return [(name, state, detail, stops)] for every input, in the rules' order."""
        out = []
        for name, watch in self.watches.items():
            state, detail = watch.state(now)
            out.append((name, state, detail, watch.rule.stop and state != OK))
        return out

    def locked(self, now: float) -> bool:
        """Return True while any input whose rule says stop isn't OK."""
        return any(stops for _, _, _, stops in self.states(now))

    def summary(self, now: float) -> str:
        """Return one line for the HUD and the log: OK, or what is wrong and what it does."""
        wrong = [(n, s, d, stops) for n, s, d, stops in self.states(now) if s != OK]
        if not wrong:
            return 'OK'
        verdict = 'STOP' if any(stops for *_, stops in wrong) else 'WARN'
        return verdict + ': ' + '; '.join(f'{n} {s} ({d})' for n, s, d, _ in wrong)

    def clear(self):
        """Forget latched GPS jumps and wheel disagreements (a person checked)."""
        for watch in self.watches.values():
            watch.clear()
