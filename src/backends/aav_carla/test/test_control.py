"""control.py: ego's Ackermann command as a CARLA car's controls."""

import math

from aav_carla import control
import pytest

# Ours (vehicle.yaml) and a CARLA car about twice as long.
GEO = control.Geometry(wheelbase=1.57, max_steer=0.5, carla_wheelbase=2.9,
                       carla_max_steer=math.radians(70))


def radius(wheelbase, angle):
    return wheelbase / math.tan(angle)


def test_the_carla_car_turns_on_our_circle_and_the_other_way_round():
    ours = 0.3                                    # rad, left
    theirs = -GEO.carla_angle(ours)               # CARLA's angle is + right: undo
    assert theirs > ours                          # a longer car steers harder ...
    assert radius(2.9, theirs) == pytest.approx(radius(1.57, ours))   # ... for one circle


def test_left_is_negative_to_carla():
    assert GEO.carla_angle(0.2) < 0.0
    assert GEO.carla_steer(0.2) < 0.0
    assert GEO.carla_angle(0.0) == 0.0


def test_our_limit_comes_first_then_carlas():
    assert GEO.carla_angle(5.0) == GEO.carla_angle(0.5)
    tight = control.Geometry(1.57, 0.5, 2.9, math.radians(20))
    assert tight.carla_angle(-0.5) == pytest.approx(math.radians(20))
    assert tight.carla_steer(-0.5) == pytest.approx(1.0)


def test_the_measured_angle_comes_back_as_ours():
    for ours in (-0.4, -0.1, 0.0, 0.25, 0.5):
        deg = math.degrees(GEO.carla_angle(ours))
        assert GEO.our_angle(deg, deg) == pytest.approx(ours)


def test_ackermann_fills_in_our_acceleration_limit():
    a = control.ackermann(GEO, speed=1.0, steer=0.1)
    assert a.speed == 1.0
    assert a.acceleration == 1.5
    assert a.steer == pytest.approx(GEO.carla_angle(0.1))
    assert control.ackermann(GEO, 1.0, 0.0, acceleration=-0.7).acceleration == 0.7
    assert control.ackermann(GEO, -0.5, 0.0).speed == -0.5      # reverse passes through


def test_pick_car():
    have = ['vehicle.lincoln.mkz', 'vehicle.mini.cooper', 'walker.x']
    assert control.pick_car(have) == 'vehicle.mini.cooper'
    assert control.pick_car(have, 'vehicle.lincoln.mkz') == 'vehicle.lincoln.mkz'
    with pytest.raises(ValueError):
        control.pick_car(have, 'vehicle.tesla.model3')
    with pytest.raises(ValueError):
        control.pick_car(['walker.x'])


def test_the_speed_loop_speeds_up_holds_and_brakes():
    loop = control.SpeedLoop()
    throttle, brake, reverse = loop.step(2.0, 0.0, 0.05)
    assert throttle > 0.0 and brake == 0.0 and not reverse
    throttle, brake, _ = loop.step(1.0, 2.0, 0.05)
    assert throttle == 0.0 and brake > 0.0
    assert loop.step(0.0, 0.0, 0.05) == (0.0, 1.0, False)
    assert loop.integral == 0.0


def test_the_speed_loop_reverses():
    loop = control.SpeedLoop()
    throttle, brake, reverse = loop.step(-0.5, 0.0, 0.05)
    assert reverse and throttle > 0.0 and brake == 0.0


def test_a_simple_car_reaches_the_target_speed():
    # A crude car: 3 m/s^2 at full throttle, 6 at full brake, a little drag.
    loop, v = control.SpeedLoop(), 0.0
    for _ in range(400):                          # 20 s
        p = control.pedals(GEO, loop, 2.0, 0.0, v, 0.05)
        v += (3.0 * p.throttle - 6.0 * p.brake - 0.1 * v) * 0.05
    assert v == pytest.approx(2.0, abs=0.1)


def test_the_estop_brakes_everything():
    s = control.stopped()
    assert (s.throttle, s.brake, s.steer, s.hand_brake) == (0.0, 1.0, 0.0, True)


def test_the_watchdog():
    w = control.Watchdog(timeout=0.2)
    assert not w.fresh(0.0)
    w.fed(1.0)
    assert w.fresh(1.2)
    assert not w.fresh(1.21)
