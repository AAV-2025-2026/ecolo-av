"""
The adaptive brake: brake harder when the car slows less than the car model says.

No ROS here (tests: test/test_adaptive_brake.py). Ben, 8 Nov: "if we brake without a
person vs with a person ... we are going to need to dynamically realize that we aren't
braking as fast as we expect and start applying more force. We don't want to overwhelm
the brakes though, so we might want to know what the max values are like the steering
system."

Where it sits: after the speed loop, before the brake actuator. Every safety stop goes
round it, as before.

```text
 ego's speed ─▶ speed loop ─▶ brake asked ─▶ AdaptiveBrake ─▶ brake sent ─▶ brake actuator
                    ▲                           ▲      │
              wheel speed ──────────────────────┘      └─ never above safe max, rises at
                                                          most rise_rate, high force only
 e-stop, stale command, silent spine ─▶ full brake          max_hold_time s a stop
 (the safety locks: never through this)
```

One tick of dt:

| Step | What |
|---|---|
| 1. measured | the slowing from the wheel speed, smoothed (`filter_time`), less the drag |
| 2. expected | the model's brake level for what was sent (dead time, lag) x `max_brake` |
|             | (the empty car's), smoothed the same way |
| 3. learn | effectiveness follows measured / expected (`adapt_time`), only while |
|          | braking for real: expected above `min_decel`, above `min_speed`, no throttle |
| 4. gain | 1 / effectiveness, from 1 (never weaker than asked) to `max_gain` |
| 5. extra | asked x (gain - 1), rising at most `rise_rate` a second, falling at once |
| 6. cap | asked + extra, never above `brake: safe_max`; the asked brake itself passes |
| 7. time | near the safe max (`high_share`) with extra on, for `brake: max_hold_time` s: |
|         | the extra is off until the brake is let go |

The effectiveness is kept from stop to stop (a person aboard stays aboard); reset() forgets
it (an e-stop, a new drive). Units: m/s, m/s^2, s; brake 0 (released) to 1 (full), as the
spine's `Brake.target` maps it onto the brake actuator's travel.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from aav_description.car_model import ActuatorConfig, clamp, delay, delay_steps, lag


@dataclass(frozen=True)
class BrakeLimits:
    """
    vehicle.yaml's `brake:` section: the brake actuator's travel, in its targets (counts).

    Like the steering's ends: the firmware maps 0..1 onto released..full
    (calibration.rs `Brake`); test_vehicle.py checks it keeps the same two numbers.
    PLACEHOLDERS until car day A7 rows 6-8 (docs/car-day.md).
    """

    released: float = 400.0       # target with the brake let go
    touch: float = 800.0          # target where the pads start to grip
    full: float = 3500.0          # target at full brake
    safe_max: float = 3200.0      # the most the brake may be pushed (the hardware lead's)
    max_hold_time: float = 5.0    # s near safe_max before the extra is taken off

    def __post_init__(self):
        if self.full == self.released:
            raise ValueError('brake: full and released are the same target')
        for name in ('touch', 'safe_max'):
            if not 0.0 <= self.fraction(getattr(self, name), clip=False) <= 1.0:
                raise ValueError(f'brake: {name} ({getattr(self, name):g}) is not between '
                                 f'released ({self.released:g}) and full ({self.full:g})')
        if self.max_hold_time < 0.0:
            raise ValueError('brake: max_hold_time must not be negative')

    def fraction(self, target: float, clip: bool = True) -> float:
        """Return a target as the brake command (0 released, 1 full), as the firmware maps it."""
        f = (target - self.released) / (self.full - self.released)
        return clamp(f, 0.0, 1.0) if clip else f

    @property
    def touch_fraction(self) -> float:
        return self.fraction(self.touch)

    @property
    def safe_max_fraction(self) -> float:
        return self.fraction(self.safe_max)

    @classmethod
    def from_vehicle(cls, cfg) -> 'BrakeLimits':
        """Build it from the whole of vehicle.yaml (as aav_description.vehicle.load gives)."""
        section = cfg.get('brake') or {}
        return cls(**{k: float(v) for k, v in section.items()})


@dataclass(frozen=True)
class AdaptiveBrakeConfig:
    """How quickly it learns and how hard it may push. Guesses: tune in the sim, then 4.3."""

    filter_time: float = 0.15   # s: smooths both slowings (the wheel speed is coarse)
    adapt_time: float = 0.3     # s: how fast the effectiveness follows what it sees
    min_decel: float = 0.3      # m/s^2: expected braking below this teaches nothing
    min_speed: float = 0.2      # m/s: slower, the slowing can't be read
    max_gain: float = 3.0       # the most it multiplies the asked brake
    rise_rate: float = 2.0      # brake (0..1) a second: the extra rises no faster
    high_share: float = 0.9     # of the safe max: "high force", timed by max_hold_time


@dataclass(frozen=True)
class BrakeOut:
    """One tick's answer."""

    brake: float            # 0..1: what to send the brake actuator
    asked: float            # 0..1: what the speed loop asked
    gain: float             # what the asked brake is multiplied by (1: as asked)
    effectiveness: float    # measured / expected braking (1: the empty car)
    capped: bool            # held at the safe max
    spent: bool             # the high-force time ran out this stop: no extra


class AdaptiveBrake:
    """The brake asked in, a stronger one out when the car slows less than the model."""

    def __init__(self, car: ActuatorConfig = ActuatorConfig(),
                 limits: BrakeLimits = BrakeLimits(),
                 tuning: AdaptiveBrakeConfig = AdaptiveBrakeConfig()):
        self.car = car
        self.limits = limits
        self.tuning = tuning
        self.effectiveness = 1.0
        self.reset_stop()

    def reset(self) -> None:
        """Forget everything, the effectiveness too: an e-stop, a new drive."""
        self.effectiveness = 1.0
        self.reset_stop()

    def reset_stop(self) -> None:
        """Forget this stop: the filters, the extra, the high-force time."""
        self.level = 0.0            # the model's brake level for what was sent
        self.line = ()              # the model's brake dead-time line
        self.sent = 0.0             # brake sent last tick
        self.speed: Optional[float] = None
        self.measured = 0.0         # m/s^2, smoothed
        self.expected = 0.0         # m/s^2, smoothed
        self.extra = 0.0
        self.high_time = 0.0
        self.spent = False
        self.quiet = 0.0            # s since the throttle was last asked for

    @property
    def gain(self) -> float:
        return clamp(1.0 / max(self.effectiveness, 1e-6), 1.0, self.tuning.max_gain)

    def update(self, throttle: float, brake: float, speed: Optional[float],
               dt: float) -> BrakeOut:
        """
        Return the brake to send, from the speed loop's throttle and brake and the speed.

        speed is the measured wheel speed (m/s), None if there is none fresh: then it
        learns nothing and adds nothing.
        """
        if dt <= 0.0:
            raise ValueError(f'dt must be positive, not {dt}')
        c, t, lim = self.car, self.tuning, self.limits
        asked = clamp(brake, 0.0, 1.0)
        k = dt / (t.filter_time + dt)

        # 2. What the empty car's brake would be doing now, for what was sent.
        delayed, self.line = delay(self.line, self.sent, delay_steps(c.brake_dead_time, dt),
                                   0.0)
        self.level = lag(self.level, delayed, c.brake_lag, dt)
        self.expected += (self.level * c.max_brake - self.expected) * k

        # 1. What the car really does: the slowing, less what coasting gives anyway.
        if speed is None or not math.isfinite(speed):
            self.speed = None
            return self._send(asked, asked)
        v = abs(speed)
        if self.speed is not None:
            slowing = (self.speed - v) / dt - c.drag * v
            self.measured += (slowing - self.measured) * k
        self.speed = v

        # A new stop starts when the brake is let go (or the throttle is asked for).
        self.quiet = 0.0 if throttle > 0.0 else self.quiet + dt
        if throttle > 0.0 or asked < lim.touch_fraction:
            self.extra, self.high_time, self.spent = 0.0, 0.0, False

        # 3. Learn, only while braking for real.
        settled = self.quiet > c.throttle_dead_time + 3.0 * c.throttle_lag
        if settled and v > t.min_speed and self.expected > t.min_decel:
            seen = clamp(self.measured / self.expected, 1.0 / t.max_gain, 1.5)
            self.effectiveness += (seen - self.effectiveness) * dt / (t.adapt_time + dt)

        # 4, 5. The extra: up at most rise_rate, down at once; none once spent.
        want = 0.0 if self.spent else asked * (self.gain - 1.0)
        self.extra = min(want, self.extra + t.rise_rate * dt)
        return self._send(asked, asked + self.extra, dt)

    def _send(self, asked: float, wanted: float, dt: float = 0.0) -> BrakeOut:
        """6, 7. Cap at the safe max (the asked brake passes as it is); time high force."""
        lim, t = self.limits, self.tuning
        top = max(asked, lim.safe_max_fraction)
        out = min(wanted, top)
        capped = wanted > top
        if self.extra > 0.0 and out >= t.high_share * lim.safe_max_fraction:
            self.high_time += dt
            if self.high_time > lim.max_hold_time:
                self.spent, self.extra, out = True, 0.0, asked
        self.sent = out
        return BrakeOut(brake=out, asked=asked, gain=self.gain,
                        effectiveness=self.effectiveness, capped=capped, spent=self.spent)
