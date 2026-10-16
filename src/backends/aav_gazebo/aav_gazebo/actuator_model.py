"""
The actuator model: how the car answers a command, between ego and Gazebo.

No ROS here. gazebo_adapter steps it at 50 Hz (Gazebo's time) and sends Gazebo the speed
and steering it gives (READ-ME-FULL-SIMULATION.md, option A):

    ego's speed ──> SpeedLoop ──> throttle %, brake % ──> Actuators ──> speed  ──> Gazebo
    ego's angle ─────────────────────────────────────> Actuators ──> angle  ──> Gazebo

  - SpeedLoop: a stand-in for the spine's speed loop (spine-core speed_loop.rs), with its
    gains, until the spine itself runs in the loop (step 4).
  - Actuators: throttle % -> acceleration, brake % -> deceleration, coasting drag; the
    steering motor's speed limit, the linkage's lag, the centre offset and a deadband.
    Its numbers are vehicle.yaml's `actuators:` section (guesses until tests 3.10-3.12
    and 4.1-4.5 in READ-ME-TESTS.md).
  - Ideal: the old behaviour, for comparison (actuator_model:=false): the speed follows
    the command within Gazebo's old limits (+1.5 / -3.0 m/s^2), the steering at once.

With the spine in the loop (sim.launch.py spine:=true, step 4), the spine's own speed
loop runs in spine_sim (spine-core, Rust), and its throttle, brake, gear and steering
target go straight to Actuators.drive, skipping SpeedLoop:

    spine_sim ──> throttle %, brake %, reverse, steering target ──> Actuators.drive ──> Gazebo

Units: m/s, m/s^2, rad, s. Throttle and brake are 0..1. Positive steering turns left.
"""

from dataclasses import dataclass, fields
import math


@dataclass(frozen=True)
class ActuatorConfig:
    """vehicle.yaml's `actuators:` section, plus the steering limit from `vehicle:`."""

    max_accel: float = 1.5          # m/s^2 at full throttle, on the flat
    throttle_deadband: float = 0.0  # throttle (0..1) below which the car doesn't push
    throttle_lag: float = 0.1       # s: the throttle's first-order response
    max_brake: float = 3.0          # m/s^2 at full brake
    brake_lag: float = 0.2          # s: the brake actuator's first-order response
    drag: float = 0.1               # 1/s: coasting, m/s lost per second per m/s
    steer_rate: float = 0.8         # rad/s: the fastest the motor turns the wheels
    steer_lag: float = 0.1          # s: the linkage's first-order lag after the motor
    steer_offset: float = 0.0       # rad: where the wheels point when told straight
    steer_deadband: float = 0.005   # rad: a change smaller than this doesn't move the motor
    max_steering: float = 0.5       # rad: full lock (vehicle.yaml max_steering_angle)

    @classmethod
    def from_vehicle(cls, cfg):
        """Build it from the whole of vehicle.yaml (as aav_description.vehicle.load gives)."""
        known = {f.name for f in fields(cls)}
        values = {k: float(v) for k, v in (cfg.get('actuators') or {}).items() if k in known}
        values['max_steering'] = float(cfg['vehicle']['max_steering_angle'])
        return cls(**values)


@dataclass(frozen=True)
class SpeedLoopConfig:
    """The spine's speed loop gains (firmware/spine/crates/spine-core/src/speed_loop.rs)."""

    kp: float = 0.3              # throttle per m/s of error
    ki: float = 0.1              # throttle per (m/s x s)
    integral_limit: float = 0.3  # the most throttle the integral may add
    brake_gain: float = 0.5      # brake per m/s of overspeed past coast_band
    coast_band: float = 0.2      # m/s too fast that coasting handles
    stopped_speed: float = 0.05  # m/s: slower counts as stopped
    hold_brake: float = 0.3      # brake held while stopped with a zero target


@dataclass(frozen=True)
class Demand:
    """What a speed loop asks for (ours, or the spine's). Throttle and brake: never both."""

    throttle: float
    brake: float
    reverse: bool


@dataclass(frozen=True)
class State:
    """The actuators after one step: what they were told, and what they did."""

    speed: float          # m/s, + forward
    accel: float          # m/s^2, this step
    steering: float       # rad: the wheels' real angle (offset included)
    steer_command: float  # rad: what was asked
    throttle: float       # 0..1, the real level
    throttle_command: float
    brake: float          # 0..1, the real level
    brake_command: float


def lag(value, target, tau, dt):
    """First-order lag: move value toward target with time constant tau (0: at once)."""
    if tau <= 0.0:
        return target
    return value + (target - value) * (1.0 - math.exp(-dt / tau))


def clamp(x, low, high):
    return min(high, max(low, x))


class SpeedLoop:
    """The spine's speed loop, ported: target and measured speed in, throttle and brake out."""

    def __init__(self, cfg=SpeedLoopConfig()):
        self.cfg = cfg
        self.integral = 0.0
        self.reverse = False

    def update(self, target, measured, dt):
        c = self.cfg
        stopped = abs(measured) < c.stopped_speed
        want_reverse = target < 0.0
        # The gear only changes while stopped; until then, brake.
        if target != 0.0 and want_reverse != self.reverse:
            self.integral = 0.0
            if stopped:
                self.reverse = want_reverse
            else:
                return Demand(0.0, clamp(max(c.hold_brake, c.brake_gain * abs(measured)),
                                         0.0, 1.0), self.reverse)
        sign = -1.0 if self.reverse else 1.0
        t, m = target * sign, measured * sign
        # A stop: brake until stopped, then hold; never coast (the spine's own rule).
        if t <= 0.0:
            self.integral = 0.0
            brake = c.hold_brake if stopped else clamp(
                max(c.hold_brake, c.brake_gain * (m - c.coast_band)), 0.0, 1.0)
            return Demand(0.0, brake, self.reverse)
        error = t - m
        self.integral = clamp(self.integral + c.ki * error * dt, 0.0, c.integral_limit)
        overspeed = -error - c.coast_band
        if overspeed > 0.0:
            self.integral = 0.0
            return Demand(0.0, clamp(c.brake_gain * overspeed, 0.0, 1.0), self.reverse)
        return Demand(clamp(c.kp * error + self.integral, 0.0, 1.0), 0.0, self.reverse)


class Actuators:
    """The modelled car: the speed loop, then throttle, brake, drag and the steering."""

    def __init__(self, cfg=ActuatorConfig(), loop=SpeedLoopConfig()):
        self.cfg = cfg
        self.loop = SpeedLoop(loop)
        self.speed = 0.0
        self.throttle = 0.0
        self.brake = 0.0
        self.motor = 0.0      # the steering motor's angle (before the linkage and offset)
        self.setpoint = 0.0   # what the motor is driving to (moves past the deadband only)
        self.wheels = 0.0     # after the linkage's lag

    def step(self, speed_command, steer_command, dt):
        """Step ego's speed and angle: the speed loop (ours, in Python), then the actuators."""
        if dt <= 0.0:
            raise ValueError(f'dt must be positive, not {dt}')
        return self.drive(self.loop.update(speed_command, self.speed, dt), steer_command, dt)

    def drive(self, d, steer_command, dt):
        """Drive the actuators alone: a throttle, brake and gear Demand, and a steering target."""
        c = self.cfg
        if dt <= 0.0:
            raise ValueError(f'dt must be positive, not {dt}')

        # Throttle and brake: the demand, through each actuator's lag.
        self.throttle = lag(self.throttle, d.throttle, c.throttle_lag, dt)
        self.brake = lag(self.brake, d.brake, c.brake_lag, dt)
        pushing = self.throttle if self.throttle > c.throttle_deadband else 0.0
        push = pushing * c.max_accel * (-1.0 if d.reverse else 1.0)
        before = self.speed
        v = before + push * dt
        # The brake and drag oppose the motion, and can only stop the car, never reverse it.
        resist = (self.brake * c.max_brake + c.drag * abs(v)) * dt
        v = max(0.0, v - resist) if v > 0.0 else min(0.0, v + resist)
        self.speed = v

        # Steering: deadband, then the motor's rate limit, then the linkage's lag.
        target = clamp(steer_command, -c.max_steering, c.max_steering)
        if abs(target - self.setpoint) > c.steer_deadband:
            self.setpoint = target
        step = c.steer_rate * dt
        self.motor += clamp(self.setpoint - self.motor, -step, step)
        self.wheels = lag(self.wheels, self.motor, c.steer_lag, dt)
        steering = clamp(self.wheels + c.steer_offset, -c.max_steering, c.max_steering)

        return State(speed=v, accel=(v - before) / dt, steering=steering,
                     steer_command=steer_command, throttle=self.throttle,
                     throttle_command=d.throttle, brake=self.brake, brake_command=d.brake)


class Ideal:
    """The old behaviour: Gazebo's own limits on the speed, and an instant steer."""

    MAX_ACCEL = 1.5   # m/s^2: aav.gazebo.xacro's max_acceleration, until 15 Oct
    MIN_ACCEL = -3.0  # m/s^2: its min_acceleration

    def __init__(self, cfg=ActuatorConfig()):
        self.cfg = cfg
        self.speed = 0.0

    def step(self, speed_command, steer_command, dt):
        if dt <= 0.0:
            raise ValueError(f'dt must be positive, not {dt}')
        before = self.speed
        self.speed += clamp(speed_command - before, self.MIN_ACCEL * dt, self.MAX_ACCEL * dt)
        steering = clamp(steer_command, -self.cfg.max_steering, self.cfg.max_steering)
        nan = float('nan')
        return State(speed=self.speed, accel=(self.speed - before) / dt, steering=steering,
                     steer_command=steer_command, throttle=nan, throttle_command=nan,
                     brake=nan, brake_command=nan)
