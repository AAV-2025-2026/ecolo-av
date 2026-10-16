"""
The wheels against the IMU: do they tell the same story? No ROS here.

A wheel-speed driver stuck in a loop sends its last speed again with fresh stamps. At a
steady speed that looks exactly like a car at a steady speed, so the watchdog's frozen
check can't tell (READ-ME-FULL-SIMULATION.md, "What's left", 15 Oct). The IMU can, as soon
as the car's speed or turn changes:

  speed   over the last `window` s, the change in the wheels' speed against the IMU's
          forward acceleration, added up over the same time. A frozen speed says 0 while
          the IMU feels the car speed up or brake
  turn    over the same window, the wheels' mean turn rate against the IMU's gyro

When either gap stays over its tolerance for `persist` s, the wheels count as wrong:
DISAGREE, latched like a GPS jump, until a person clears it (the watchdog's clear service).
Frozen at a speed the car really keeps, the wheels are still right, and nothing is said:
the gap only opens when the car's speed or turn changes, which is when it matters.

The IMU's forward reading also holds gravity on a slope, and a tilt in its mounting. Its
offset is first taken while the car stands still (the wheels say 0 for a whole window),
then follows a slow average of its difference from the wheels' (bias_time s), learnt only
while they agree.

Assumes imu_link's x points forward, as vehicle.yaml mounts it. Units: m/s, m/s^2, rad/s,
seconds on the node's clock.
"""

from collections import deque
from dataclasses import dataclass
import math
from typing import Optional, Tuple

DISAGREE = 'DISAGREE'


@dataclass(frozen=True)
class CrossCheck:
    """How hard to look. The numbers are tuned in Gazebo only (docs/simulation.md)."""

    window: float = 1.5             # s of samples compared
    speed_tolerance: float = 0.3    # m/s: wheels' change vs the IMU's, over the window
    yaw_tolerance: float = 0.15     # rad/s: mean turn rates, over the window
    persist: float = 1.0            # s a gap must last before it counts
    bias_time: float = 10.0         # s: how fast the IMU's forward offset is learnt

    def __post_init__(self):
        for name in ('window', 'speed_tolerance', 'yaw_tolerance', 'bias_time'):
            if not getattr(self, name) > 0.0:
                raise ValueError(f'cross check: {name} must be positive')
        if self.persist < 0.0:
            raise ValueError('cross check: persist must not be negative')


def trapezoid(samples, start: float, end: float) -> float:
    """Return the integral over [start, end] of (t, value) samples, sorted by t."""
    total = 0.0
    for (t0, a0), (t1, a1) in zip(samples, list(samples)[1:]):
        lo, hi = max(t0, start), min(t1, end)
        if hi <= lo:
            continue

        def at(t):
            return a0 + (a1 - a0) * (t - t0) / (t1 - t0)
        total += 0.5 * (at(lo) + at(hi)) * (hi - lo)
    return total


class WheelCheck:
    """The wheels' speed and turn rate against the IMU's, over a sliding window."""

    def __init__(self, check: CrossCheck = CrossCheck()):
        self.check = check
        self.wheel = deque()        # (t, speed, yaw rate)
        self.accel = deque()        # (t, forward acceleration)
        self.gyro = deque()         # (t, yaw rate)
        self.bias = None            # m/s^2: what the IMU's forward reading adds (slopes)
        self.since = None           # when the gaps last went over
        self.latched = None         # why, as text, until clear()
        self.last = None            # when update() last ran
        self.worst = (0.0, 0.0)     # the biggest gaps seen before any latch: for tuning
        self.gaps = None            # the newest (speed gap, turn gap), or None

    def wheels(self, now: float, speed: float, yaw_rate: float):
        if math.isfinite(speed) and math.isfinite(yaw_rate):
            self.wheel.append((now, speed, yaw_rate))

    def imu(self, now: float, forward: float, yaw_rate: float):
        if math.isfinite(forward):
            self.accel.append((now, forward))
        if math.isfinite(yaw_rate):
            self.gyro.append((now, yaw_rate))

    def measure(self, now: float) -> Optional[Tuple[float, float, float]]:
        """
        Return (speed gap m/s, turn gap rad/s, the IMU's own mean forward reading m/s^2).

        None while the window doesn't hold enough of both: the stale checks cover silence.
        """
        start = now - self.check.window
        for q in (self.wheel, self.accel, self.gyro):
            while len(q) > 2 and q[1][0] <= start:
                q.popleft()
        wheel = [w for w in self.wheel if w[0] >= start]
        if len(wheel) < 2 or len(self.accel) < 2 or len(self.gyro) < 1:
            return None
        t0, t1 = wheel[0][0], wheel[-1][0]
        span = t1 - t0
        if (span < 0.6 * self.check.window or self.accel[0][0] > t0 + 0.1
                or self.accel[-1][0] < t1 - 0.1):
            return None
        felt = trapezoid(self.accel, t0, t1)
        if self.bias is None:
            # The first look: a car standing still shows the IMU's own offset.
            still = all(abs(w[1]) < 0.01 for w in wheel)
            self.bias = (felt - (wheel[-1][1] - wheel[0][1])) / span if still else 0.0
        speed_gap = abs((wheel[-1][1] - wheel[0][1]) - (felt - self.bias * span))
        gyro = [g for t, g in self.gyro if t0 <= t <= t1] or [self.gyro[-1][1]]
        turn_gap = abs(sum(w[2] for w in wheel) / len(wheel) - sum(gyro) / len(gyro))
        return speed_gap, turn_gap, (felt - (wheel[-1][1] - wheel[0][1])) / span

    def update(self, now: float) -> Optional[str]:
        """Look again (each tick); return why the wheels are wrong, or None if they're not."""
        dt = 0.0 if self.last is None else max(0.0, now - self.last)
        self.last = now
        if self.latched is not None:
            return self.latched
        got = self.measure(now)
        self.gaps = None if got is None else got[:2]
        if got is None:
            self.since = None
            return None
        speed_gap, turn_gap, offset = got
        self.worst = (max(self.worst[0], speed_gap), max(self.worst[1], turn_gap))
        c = self.check
        if speed_gap > c.speed_tolerance or turn_gap > c.yaw_tolerance:
            self.since = now if self.since is None else self.since
            if now - self.since >= c.persist:
                self.latched = (f'the wheels and the IMU disagree: speed {speed_gap:.2f} m/s '
                                f'apart over {c.window:g} s, turn {turn_gap:.2f} rad/s')
            return self.latched
        self.since = None
        self.bias += (offset - self.bias) * min(1.0, dt / c.bias_time)
        return None

    def clear(self):
        """Forget a latched disagreement, and the samples from before it: start afresh."""
        self.latched, self.since, self.gaps = None, None, None
        for q in (self.wheel, self.accel, self.gyro):
            q.clear()
