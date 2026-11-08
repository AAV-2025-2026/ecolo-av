"""
The stop-point check's maths (sim_check.py --stop-point): where the car stopped.

Where the car really stopped, against where the car model said it would. No ROS: tested
in tools/tests/test_stop_points.py.

One run:

```text
  speed ▲  hold v ──────┐ set speed falls at `ramp`
        │               │╲      the car follows late (speed loop, lags)
        │               │ ╲ ╲
        └───────────────┴──────────▶ x
                        t0          stop: predicted, by truth, by localization
```

t0 is when the commanded speed starts to fall (the newest command still at the hold's
speed). The prediction is aav_description stop_law.stop_point from the speed the truth
had at t0. Distances are along the car's heading at t0, from where it was at t0. The same
code can score a bag from the real car: the commands, the odometry, and a tape for truth.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple

# A pass: within max(TOLERANCE, SHARE x the predicted distance). TOLERANCE is the behaviour
# design's starting band (0.17 m roll + 0.09 m for 1 px of the sign), rounded.
TOLERANCE = 0.25    # m
SHARE = 0.10
STILL = 0.01        # m/s: stood still


@dataclass(frozen=True)
class Sample:
    t: float        # s
    x: float        # m
    y: float        # m
    yaw: float      # rad
    v: float        # m/s


def slowing_start(commands: Sequence[Tuple[float, float]], hold: float,
                  after: float = -math.inf, eps: float = 0.01) -> Optional[float]:
    """
    Return the time the commanded speed first falls below `hold` − eps, after `after`.

    commands: (t, commanded speed). The command must have reached the hold's speed first,
    so the ramp up isn't taken for the slowing.
    """
    reached = False
    for t, v in commands:
        if t < after:
            continue
        if v >= hold - eps:
            reached = True
        elif reached:
            return t
    return None


def at(track: Sequence[Sample], t: float) -> Optional[Sample]:
    """Return the track's sample at time t, interpolated; None outside it."""
    if not track or not track[0].t <= t <= track[-1].t:
        return None
    times = [s.t for s in track]
    i = bisect.bisect_left(times, t)
    if times[i] == t:
        return track[i]
    a, b = track[i - 1], track[i]
    f = (t - a.t) / (b.t - a.t)
    return Sample(t, a.x + f * (b.x - a.x), a.y + f * (b.y - a.y), a.yaw + f * (b.yaw - a.yaw),
                  a.v + f * (b.v - a.v))


def stopped(track: Sequence[Sample], after: float, still: float = STILL,
            hold: float = 0.5) -> Optional[Sample]:
    """Return the first sample after `after` from which the car stays still for `hold` s."""
    start = None
    for s in track:
        if s.t < after:
            continue
        if abs(s.v) < still:
            if start is None:
                start = s
            if s.t - start.t >= hold:
                return start
        else:
            start = None
    return None


def along(origin: Sample, there: Sample) -> float:
    """Return how far `there` is from `origin` along origin's heading (m)."""
    return ((there.x - origin.x) * math.cos(origin.yaw)
            + (there.y - origin.y) * math.sin(origin.yaw))


def tolerance(predicted: float) -> float:
    return max(TOLERANCE, SHARE * abs(predicted))


@dataclass(frozen=True)
class Stop:
    """One stop, scored."""

    speed: float                 # m/s, the truth at t0
    predicted: float             # m, the car model's
    truth: float                 # m, Gazebo's truth (or a tape)
    localized: Optional[float]   # m, the global EKF's (None: no pose)
    law: float                   # m, the stopping law's S(v): what the planners allow

    @property
    def error(self) -> float:
        return self.truth - self.predicted

    @property
    def ok(self) -> bool:
        return abs(self.error) <= tolerance(self.predicted)

    @property
    def localized_ok(self) -> Optional[bool]:
        if self.localized is None:
            return None
        return abs(self.localized - self.predicted) <= tolerance(self.predicted) + TOLERANCE

    def words(self) -> str:
        loc = ('no pose' if self.localized is None else
               f'localization {self.localized:.2f} m ({self.localized - self.predicted:+.2f})')
        return (f'from {self.speed:.2f} m/s: predicted {self.predicted:.2f} m, truth '
                f'{self.truth:.2f} m ({self.error:+.2f}, tolerance '
                f'{tolerance(self.predicted):.2f}), {loc}; the stopping law plans '
                f'{self.law:.2f} m')
