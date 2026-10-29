"""The legacy bridge's speed loop (speed_control): feed-forward plus PI, throttle or brake."""

import math

from aav_legacy.speed_control import SpeedControl, SpeedControlConfig
import pytest

C = SpeedControlConfig()
DT = 0.02  # s: the bridge's 50 Hz


class Car:
    """The plant: the same shape as aav_gazebo's actuator model, with its own numbers."""

    def __init__(self, max_accel=1.5, max_brake=3.0, drag=0.1, lag=0.1):
        self.max_accel, self.max_brake, self.drag, self.lag = max_accel, max_brake, drag, lag
        self.speed = self.position = self.throttle = self.brake = 0.0

    def step(self, throttle, brake, dt=DT):
        k = 1.0 - math.exp(-dt / self.lag)
        self.throttle += (throttle - self.throttle) * k
        self.brake += (brake - self.brake) * k
        v = self.speed + self.throttle * self.max_accel * dt
        v = max(0.0, v - (self.brake * self.max_brake + self.drag * v) * dt)
        self.position += (self.speed + v) / 2 * dt
        self.speed = v


def ramp(top=1.0, accel=0.5, decel=1.0, hold=6.0):
    """Return ego's speed profile for a short A to B: up, hold, down to 0, 2 s standing."""
    targets, v = [], 0.0
    while v < top:
        v = min(top, v + accel * DT)
        targets.append(v)
    targets += [top] * int(hold / DT)
    while v > 0.0:
        v = max(0.0, v - decel * DT)
        targets.append(v)
    return targets + [0.0] * int(2.0 / DT)


def drive(car, loop, targets, feedback=True):
    planned = 0.0
    for target in targets:
        p = loop.update(target, car.speed if feedback else None, DT)
        assert p.throttle == 0.0 or p.brake == 0.0
        car.step(p.throttle, p.brake)
        planned += target * DT
    return planned


def test_standing_still_with_a_zero_target_holds_the_brake():
    p = SpeedControl().update(0.0, 0.0, DT)
    assert (p.throttle, p.brake) == (0.0, C.hold_brake)


def test_open_loop_holds_a_speed_with_the_throttle_that_matches_drag():
    loop = SpeedControl()
    for _ in range(100):
        p = loop.update(1.0, None, DT)
    assert p.throttle == pytest.approx(C.drag * 1.0 / C.max_accel)
    assert p.brake == 0.0


def test_ego_speeding_up_is_sent_at_once_as_feed_forward():
    loop = SpeedControl(SpeedControlConfig(response_lag=0.0))
    v = 0.0
    for _ in range(50):              # 1 s at 0.5 m/s^2, the car keeping up exactly
        v += 0.5 * DT
        p = loop.update(v, v, DT)
    assert p.feedforward == pytest.approx(0.5, abs=0.01)
    assert p.throttle == pytest.approx((0.5 + C.drag * v) / C.max_accel, abs=0.01)


def test_a_car_lagging_as_expected_gets_no_extra_brake():
    lag = SpeedControlConfig().response_lag
    cases = ((SpeedControlConfig(), False), (SpeedControlConfig(response_lag=0.0), True))
    for cfg, extra in cases:
        loop = SpeedControl(cfg)
        for _ in range(100):
            loop.update(3.0, 3.0, DT)
        v, car = 3.0, 3.0
        for _ in range(40):          # ego slows at 1.5 m/s^2; the car follows response_lag behind
            v -= 1.5 * DT
            car += (v - car) * DT / lag
            p = loop.update(v, car, DT)
        planned = (1.5 - C.drag * car) / C.max_brake
        assert (p.brake > planned * 1.2) == extra


def test_feedback_reaches_the_speed_when_the_car_is_weaker_than_the_model():
    car = Car(max_accel=1.0, drag=0.2)     # 2/3 the push, twice the drag
    loop = SpeedControl()
    drive(car, loop, [1.0] * int(10.0 / DT))
    assert car.speed == pytest.approx(1.0, abs=0.02)


def test_without_feedback_the_weaker_car_falls_short():
    car = Car(max_accel=1.0, drag=0.2)
    drive(car, SpeedControl(), [1.0] * int(10.0 / DT), feedback=False)
    assert car.speed < 0.6             # why the loop is worth closing


def test_a_to_b_stops_near_where_ego_planned():
    car = Car()
    planned = drive(car, SpeedControl(), ramp())
    assert car.speed == 0.0
    assert car.position == pytest.approx(planned, abs=0.15)


def test_a_to_b_with_a_weak_brake_still_stops_close():
    car = Car(max_brake=2.0)                # a third weaker than the model
    planned = drive(car, SpeedControl(), ramp())
    assert car.speed == 0.0
    assert car.position == pytest.approx(planned, abs=0.25)


def test_slowing_gently_coasts_rather_than_braking():
    loop = SpeedControl()
    for _ in range(50):
        loop.update(1.0, 1.0, DT)
    v = 1.0
    for _ in range(25):              # -0.1 m/s^2: drag (0.1 x 1) does it alone
        v -= 0.1 * DT
        p = loop.update(v, v, DT)
    assert (p.throttle, p.brake) == (0.0, 0.0)


def test_the_integral_stays_within_its_limit_while_the_throttle_is_pinned():
    loop = SpeedControl()
    for _ in range(500):             # 10 s asking 3 m/s of a car stuck at 0
        p = loop.update(3.0, 0.0, DT)
    assert p.throttle == 1.0
    assert abs(p.integral) <= C.integral_limit


def test_a_target_below_zero_brakes_to_a_stop():
    p = SpeedControl().update(-1.0, 1.0, DT)
    assert p.throttle == 0.0 and p.brake > 0.0


def test_reset_forgets_the_feed_forward_and_the_integral():
    loop = SpeedControl()
    for i in range(50):
        loop.update(0.02 * i, 0.0, DT)
    loop.reset()
    assert (loop.integral, loop.feedforward, loop.last_target) == (0.0, 0.0, None)


def test_a_time_step_of_zero_is_refused():
    with pytest.raises(ValueError):
        SpeedControl().update(1.0, 1.0, 0.0)
