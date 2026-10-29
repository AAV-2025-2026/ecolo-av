"""
The legacy bridge's speed loop: feed-forward plus PI, one signed acceleration. No ROS here.

Today's ESP32 (the C++ or our Rust in its place) drives open loop: the frame's speed
number goes straight to the throttle, and its accel number, below -0.05, to the brake.
This closes the loop on the Orin, before the frame (docs/designs/2026-10-27_control-plan.md,
step 1):

    ego's speed ──> wanted acceleration (how fast ego's speed is changing) ── feed-forward
                └─> speed error ──> PI ───────────────────────────────────── feedback
                                     │
                    one signed acceleration ──> the car model, inverted ──> throttle OR brake

  - Feed-forward: ego already shapes the speed (its acceleration and jerk limits), so the
    slope of its commands is the acceleration it wants. Sent at once, before any error.
  - Feedback: PI on the wheel speed (/vehicle/odom) cleans up what the model got wrong:
    slope, wind, wear. The integral is limited, runs only near the target, and is frozen
    while a pedal is pinned.
  - The model (vehicle.yaml's actuators:, guesses until tests 4.1-4.4): full throttle
    gives max_accel, full brake max_brake, and coasting loses drag x speed. A motor
    controller that holds a speed per throttle fits the same model: drag = max_accel /
    the speed at full throttle.
  - Never throttle and brake together; a small dead band between them, where it coasts.
  - A zero target: brake at least `hold_brake` until stopped, then hold it. Never coast to
    a stop: just above "stopped" the loop alone would ask for a feather of brake, and creep.
  - Without a wheel speed: feed-forward only.

Units: m/s, m/s^2, s. Throttle and brake are 0..1. Forward only: a target below zero
brakes to a stop (reversing is off on the car, and the legacy path keeps it that way).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpeedControlConfig:
    """The loop's gains, and the car model it inverts."""

    # Gains: GUESSES, tried against a model car with 0.1-0.2 s of dead time (calm, within
    # 2 % holding 1 m/s). Tune on the car (docs/measure-the-car.md).
    kp: float = 2.0              # m/s^2 per m/s of speed error
    ki: float = 0.5              # m/s^2 per (m/s x s)
    integral_limit: float = 0.5  # m/s^2: the most the integral may add or take
    integral_band: float = 0.3   # m/s: integrate only this close, so a big step can't wind it up
    accel_filter: float = 0.1    # s: smooths the slope of ego's speed (it steps at 20-50 Hz)
    dead_band: float = 0.05      # m/s^2 either side of zero: coast, neither pedal
    stopped_speed: float = 0.05  # m/s: slower counts as stopped
    hold_brake: float = 0.2      # brake (0..1) held while stopped with a zero target
    # The car model: vehicle.yaml actuators:.
    max_accel: float = 1.5       # m/s^2 at full throttle
    max_brake: float = 3.0       # m/s^2 at full brake
    drag: float = 0.1            # 1/s: m/s lost per second per m/s, coasting


@dataclass(frozen=True)
class Pedals:
    """One tick's output: throttle and brake, 0..1, never both above 0."""

    throttle: float
    brake: float
    accel: float           # m/s^2: the signed acceleration asked of the car
    feedforward: float     # m/s^2: of which, from ego's slope
    integral: float        # m/s^2: of which, the integral


def clamp(x: float, low: float, high: float) -> float:
    return min(high, max(low, x))


class SpeedControl:
    """Feed-forward plus PI on wheel speed, out as throttle or brake."""

    def __init__(self, cfg: SpeedControlConfig = SpeedControlConfig()):
        self.cfg = cfg
        self.integral = 0.0
        self.feedforward = 0.0
        self.last_target: Optional[float] = None

    def reset(self) -> None:
        """Forget the past: on a stale command, an e-stop, or a new drive."""
        self.integral = 0.0
        self.feedforward = 0.0
        self.last_target = None

    def update(self, target: float, measured: Optional[float], dt: float) -> Pedals:
        """
        Return this tick's pedals.

        target is ego's speed now (m/s), measured the wheel speed (None if there is none
        fresh), dt the time since the last update (s).
        """
        c = self.cfg
        if dt <= 0.0:
            raise ValueError(f'dt must be positive, not {dt}')
        target = max(0.0, target)
        slope = 0.0 if self.last_target is None else (target - self.last_target) / dt
        self.last_target = target
        self.feedforward += (slope - self.feedforward) * clamp(dt / max(c.accel_filter, dt),
                                                               0.0, 1.0)

        if measured is None:
            # Open loop: assume the car is where ego says, and trust the model alone.
            self.integral = 0.0
            speed = target
        else:
            speed = max(0.0, measured)

        stopping = target < c.stopped_speed
        if stopping:
            self.integral = 0.0
            self.feedforward = 0.0
            if speed < c.stopped_speed:
                return Pedals(0.0, c.hold_brake, 0.0, 0.0, 0.0)

        error = target - speed if measured is not None else 0.0
        integral = self.integral
        if abs(error) < c.integral_band and not stopping:
            integral = clamp(integral + c.ki * error * dt, -c.integral_limit, c.integral_limit)
        accel = self.feedforward + c.kp * error + integral
        throttle, brake = self.pedals(accel, speed)
        if stopping:
            throttle, brake = 0.0, max(brake, c.hold_brake)
        # Anti-windup: keep the new integral unless a pedal is pinned and it would grow more.
        pinned = (throttle >= 1.0 and error > 0.0) or (brake >= 1.0 and error < 0.0)
        if not pinned:
            self.integral = integral
        return Pedals(throttle, brake, accel, self.feedforward, self.integral)

    def pedals(self, accel: float, speed: float):
        """Invert the model: the throttle or brake that gives `accel` at `speed`."""
        c = self.cfg
        # Coasting already slows the car by drag x speed: the pedals make up the rest.
        push = accel + c.drag * speed
        if push > c.dead_band:
            return clamp(push / c.max_accel, 0.0, 1.0), 0.0
        if push < -c.dead_band:
            return 0.0, clamp(-push / c.max_brake, 0.0, 1.0)
        return 0.0, 0.0
