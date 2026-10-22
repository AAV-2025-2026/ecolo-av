import math

from aav_ego.ackermann import EgoModel, Limits, live_change, slew_speed, steering_angle
from aav_ego.ackermann import turn_rate
from aav_ego.dynamics import Body
import pytest

LIM = Limits(wheelbase=1.57, max_steering_angle=0.5, max_speed=2.0, max_reverse_speed=1.0,
             max_acceleration=1.0, max_deceleration=2.0, max_steering_rate=10.0)


def test_straight_is_zero_steering():
    assert steering_angle(1.0, 0.0, LIM, hold=0.3) == 0.0


def test_left_turn_is_positive():
    d = steering_angle(1.0, 0.2, LIM, hold=0.0)
    assert d == pytest.approx(math.atan(1.57 * 0.2))
    assert d > 0


def test_steering_is_clamped():
    assert steering_angle(0.5, 2.0, LIM, hold=0.0) == LIM.max_steering_angle
    assert steering_angle(0.5, -2.0, LIM, hold=0.0) == -LIM.max_steering_angle


def test_reverse_uses_the_bicycle_model():
    # Reversing with the wheels turned right swings the car counter-clockwise.
    d = steering_angle(-1.0, 0.2, LIM, hold=0.0)
    assert d < 0
    assert turn_rate(-1.0, d, LIM.wheelbase) == pytest.approx(0.2)


@pytest.mark.parametrize('v,w', [(1.0, 0.1), (0.3, -0.1), (-0.5, 0.05), (2.0, 0.4)])
def test_round_trip_for_feasible_turns(v, w):
    d = steering_angle(v, w, LIM, hold=0.0)
    assert turn_rate(v, d, LIM.wheelbase) == pytest.approx(w)


def test_standstill_holds_the_wheels():
    assert steering_angle(0.0, 0.5, LIM, hold=0.2) == 0.2


def test_speed_ramps_at_the_limits():
    assert slew_speed(0.0, 2.0, LIM, 0.1)[0] == pytest.approx(0.1)   # accelerate 1 m/s^2
    assert slew_speed(1.0, 0.0, LIM, 0.1)[0] == pytest.approx(0.8)   # decelerate 2 m/s^2


def test_direction_change_goes_through_zero():
    speed, _ = slew_speed(0.1, -1.0, LIM, 0.1)
    assert speed == pytest.approx(0.0)


def test_speed_is_capped_but_curvature_kept():
    m = EgoModel(LIM)
    for _ in range(100):
        speed, steering, _ = m.step((5.0, 0.5), 0.1)
    assert speed == pytest.approx(LIM.max_speed)
    assert steering == pytest.approx(min(math.atan(1.57 * 0.5 / 5.0), 0.5))


def test_stale_command_stops_the_car():
    m = EgoModel(LIM)
    for _ in range(30):
        m.step((1.0, 0.0), 0.1)
    for _ in range(30):
        speed, _, _ = m.step(None, 0.1)
    assert speed == 0.0


def test_steering_rate_is_limited():
    slow = Limits(max_steering_rate=0.5)
    m = EgoModel(slow)
    _, d, _ = m.step((1.0, 1.0), 0.1)
    assert d == pytest.approx(0.05)


def test_only_the_steering_rate_changes_while_running():
    assert live_change('max_steering_rate', 3.0) is None
    assert live_change('max_steering_rate', 6.0) is not None    # above the range
    assert live_change('max_steering_rate', 0.0) is not None
    assert live_change('max_steering_rate', 'fast') is not None
    assert 'start-up' in live_change('max_speed', 3.0)            # the speed cap stays put
    assert live_change('use_sim_time', True) is None               # not ego's to judge


def run(model, cmd, seconds, dt=0.02):
    for _ in range(int(round(seconds / dt))):
        out = model.step(cmd, dt)
    return out


def test_a_load_slows_speeding_up_never_braking():
    lim = Limits(max_speed=2.0, max_acceleration=1.0, max_deceleration=2.0)
    heavy = EgoModel(lim, Body(payload=181.0))     # twice the mass: the motor gives 0.75
    speed, _, accel = heavy.step((2.0, 0.0), 0.1)
    assert accel == pytest.approx(0.75) and speed == pytest.approx(0.075)
    run(heavy, (2.0, 0.0), 5.0)
    speed, _, accel = heavy.step((0.0, 0.0), 0.1)
    assert accel == 2.0                            # braking: never softened
    assert speed == pytest.approx(2.0 - 0.2)


def test_a_tight_turn_slows_the_car_and_keeps_the_turn():
    lim = Limits(max_speed=5.0, max_acceleration=10.0, max_deceleration=10.0,
                 max_steering_rate=10.0)
    model = EgoModel(lim, Body())
    # 4 m/s on a 4 m radius: 4 m/s^2 sideways, twice the 2.0 allowed.
    speed, steering, _ = run(model, (4.0, 1.0), 3.0)
    assert steering == pytest.approx(math.atan(1.57 / 4.0))
    assert speed == pytest.approx(math.sqrt(2.0 * 4.0), rel=1e-3)   # 2.83 m/s
    # Straight again: back to 4 m/s once the wheels have come back.
    speed, steering, _ = run(model, (4.0, 0.0), 3.0)
    assert steering == 0.0 and speed == pytest.approx(4.0)


def test_without_a_body_nothing_changes():
    lim = Limits(max_speed=5.0, max_acceleration=10.0, max_deceleration=10.0,
                 max_steering_rate=10.0)
    speed, _, _ = run(EgoModel(lim), (4.0, 1.0), 3.0)
    assert speed == pytest.approx(4.0)


def test_the_payload_changes_while_running():
    assert live_change('payload', 80) is None
    assert live_change('payload', 80.5) is None
    assert 'between' in live_change('payload', 500)
    assert 'between' in live_change('payload', -1)
    assert 'restart ego' in live_change('mass', 200.0)
    assert 'restart ego' in live_change('max_lateral_accel', 3.0)
