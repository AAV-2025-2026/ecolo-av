"""ego's lag lead: it helps on the car model, and every limit still holds after it."""

from aav_description.car_model import (ActuatorConfig, CarState, Command, speed_loop_profile,
                                       SpeedLoop, step)
from aav_ego.ackermann import EgoModel, Limits
from aav_ego.lag_lead import (check_mode, command_key, LagAwareWatch, LagLead, lead_wanted,
                              LeadLimits, LeadTimes)
import pytest

DT = 0.02
CFG = ActuatorConfig(throttle_dead_time=0.05, brake_dead_time=0.05, steer_dead_time=0.1)
TIMES = LeadTimes.from_config(CFG)


def test_lead_times_are_dead_time_plus_lag():
    assert TIMES.speed_up == pytest.approx(0.15)
    assert TIMES.slow_down == pytest.approx(0.25)
    assert TIMES.steer == pytest.approx(0.2)


@pytest.mark.parametrize('mode,sim,aware,want', [
    ('off', True, False, False), ('auto', False, False, False), ('auto', True, False, True),
    ('on', False, False, True), ('on', True, True, False), ('auto', True, True, False)])
def test_when_the_lead_runs(mode, sim, aware, want):
    assert lead_wanted(mode, sim, aware) is want


def test_modes_are_checked():
    assert check_mode('auto') is None
    assert 'one of' in check_mode('maybe')


def test_the_first_request_and_an_inactive_one_pass_unchanged():
    lead = LagLead(TIMES)
    assert lead.step(1.0, 0.2, DT) == (1.0, 0.2)
    assert lead.step(0.5, 0.1, DT, active=False) == (0.5, 0.1)
    assert lead.step(0.7, 0.0, DT) == (0.7, 0.0)     # reset: no kick


def test_a_steady_request_settles_to_itself():
    lead = LagLead(TIMES)
    lead.step(0.0, 0.0, DT)
    for _ in range(200):
        out = lead.step(1.0, 0.2, DT)
    assert out == pytest.approx((1.0, 0.2), abs=1e-6)


def test_speeding_up_asks_ahead_within_its_limit():
    lead = LagLead(TIMES, LeadLimits(max_speed_lead=0.3))
    lead.step(0.5, 0.0, DT)
    v, _ = lead.step(1.0, 0.0, DT)
    assert 0.5 < v <= lead.speed + 0.3 + 1e-9   # the filtered request, plus the limit
    peak = max(lead.step(1.0, 0.0, DT)[0] for _ in range(50))
    assert peak > 1.0                     # ahead of the request for a while
    assert peak <= 1.0 + 0.3


def test_a_slow_down_is_never_softened_and_never_reverses():
    lead = LagLead(TIMES)
    lead.step(1.0, 0.0, DT)
    for _ in range(100):
        v, _ = lead.step(0.4, 0.0, DT)
        assert 0.0 <= v <= 0.4
    lead.step(1.0, 0.0, DT)
    assert lead.step(0.0, 0.0, DT)[0] == 0.0     # a stop passes as a stop
    rev = LagLead(TIMES)
    rev.step(-0.3, 0.0, DT)
    for _ in range(20):
        assert rev.step(-0.5, 0.0, DT)[0] <= 0.0


def test_ego_limits_hold_after_the_lead():
    lim = Limits(max_speed=1.0, max_steering_angle=0.5, max_steering_rate=0.6,
                 max_acceleration=5.0, max_deceleration=5.0)
    model = EgoModel(lim)
    lead = LagLead(TIMES, LeadLimits(max_speed_lead=0.5, max_steer_lead=0.3))
    last = 0.0
    for i in range(300):
        v = 1.0 if i < 150 else 0.95          # at the cap, and just under it
        w = 1.0 * (1 if (i // 40) % 2 else -1)  # steering flips, beyond full lock
        speed, steering, _ = model.step((v, w), DT, lead.step)
        assert speed <= lim.max_speed + 1e-12
        assert abs(steering) <= lim.max_steering_angle + 1e-12
        assert abs(steering - last) <= lim.max_steering_rate * DT + 1e-12
        last = steering
    # A stop (no command) gets no lead: ego's own stop.
    plain = EgoModel(lim)
    plain.speed, model.speed = 1.0, 1.0
    assert model.step(None, DT, lead.step)[0] == plain.step(None, DT)[0]


def run(lead_on, profile='default'):
    """Ego (with or without the lead) driving the car model; return the speed error area."""
    lim = Limits(max_speed=2.0, max_acceleration=1.0, max_deceleration=2.0,
                 max_steering_rate=0.6)
    model = EgoModel(lim)
    lead = LagLead(TIMES, LeadLimits(filter_time=0.05))
    loop = SpeedLoop(speed_loop_profile(profile))
    car = CarState()
    plain_model = EgoModel(lim)      # what ego would send with no lag at all
    error = 0.0
    for i in range(400):
        v = min(1.5, 0.01 * i)        # the driver ramps up
        want, _, _ = plain_model.step((v, 0.0), DT)
        speed, steering, _ = model.step((v, 0.0), DT, lead.step if lead_on else None)
        car = step(CFG, car, Command(steer=steering, speed=speed), DT, loop)
        error += abs(car.v - want) * DT
    return error


def test_on_the_car_model_the_lead_follows_a_ramp_closer():
    assert run(True) < run(False)


def test_the_watch_finds_a_lag_aware_drivers_command():
    watch = LagAwareWatch(['nav', 'point'])
    key = command_key(10, 500, 0.8, 0.1)
    watch.sent('nav', key)
    assert watch.driving(key) is None            # not lag-aware yet
    watch.set_aware('nav', True)
    assert watch.driving(key) == 'nav'
    assert watch.driving(command_key(10, 501, 0.8, 0.1)) is None   # someone else's
    assert watch.driving(None) is None
    watch.set_aware('nav', False)
    assert watch.driving(key) is None
