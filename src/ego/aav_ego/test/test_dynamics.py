import math

from aav_ego import dynamics as d
from aav_ego.dynamics import Body
import pytest

CAR = Body()                     # 181 kg, the guesses in vehicle.yaml
PERSON = 80.0                    # kg


def test_a_load_slows_speeding_up_and_braking():
    loaded = Body(payload=PERSON)
    # The same motor and brakes move 261 kg instead of 181: a = F / m.
    assert d.speed_up_limit(CAR) == pytest.approx(1.5)
    assert d.speed_up_limit(loaded) == pytest.approx(1.5 * 181 / 261)
    assert d.braking_limit(loaded) == pytest.approx(3.0 * 181 / 261)
    assert d.energy(loaded, 1.0) == pytest.approx(130.5)


def test_the_tyres_cap_what_the_motor_and_brakes_can_do():
    slippery = Body(tyre_grip=0.1)               # ice: 0.98 m/s^2 at most
    assert d.speed_up_limit(slippery) == pytest.approx(0.981)
    assert d.braking_limit(slippery) == pytest.approx(0.981)


def test_the_mass_doesnt_change_the_speed_a_turn_allows():
    assert d.lateral_limit(Body(payload=PERSON)) == d.lateral_limit(CAR)
    assert d.curve_speed(Body(mass=400.0), 0.35) == d.curve_speed(CAR, 0.35)


def test_sliding_and_tipping():
    assert d.sliding_accel(CAR) == pytest.approx(0.7 * 9.81)
    # Half the track over the height: 0.385 / 0.55 of g.
    assert d.tipping_accel(CAR) == pytest.approx(9.81 * 0.385 / 0.55)
    # Comfort (2.0) is well under half of either, with today's guesses...
    assert d.lateral_limit(CAR) == 2.0
    # ...but a high centre of mass on a narrow track makes tipping the limit.
    tall = Body(cg_height=1.2)
    assert d.lateral_limit(tall) == pytest.approx(9.81 * 0.385 / 1.2 / d.MARGIN)
    assert d.lateral_limit(tall) < 2.0


def test_curve_speed():
    assert d.curve_speed(CAR, 0.0) == math.inf
    # Full lock: 2.86 m, so v = sqrt(2.0 x 2.86) = 2.4 m/s. Left or right, the same.
    k = math.tan(0.5) / 1.57
    assert d.curve_speed(CAR, k) == pytest.approx(math.sqrt(2.0 / k))
    assert d.curve_speed(CAR, -k) == d.curve_speed(CAR, k)
    assert 2.3 < d.curve_speed(CAR, k) < 2.5


def test_stopping_distance():
    # 0.4 s at 1 m/s before the brakes bite, then v^2 / 2a at 2 m/s^2.
    assert d.stopping_distance(CAR, 1.0, 2.0) == pytest.approx(0.4 + 0.25)
    assert d.stopping_distance(CAR, -1.0, 2.0) == pytest.approx(0.65)
    assert d.stopping_distance(CAR, 0.0, 2.0) == 0.0


def test_the_log_lines_and_the_brake_warning():
    lines = d.describe(CAR, 1.57, 0.5, 1.0, 1.0, 2.0)
    assert lines[0] == 'body: 181 kg + 0 kg aboard'
    assert 'stops from 1 m/s in 0.65 m' in lines[2]
    assert not any('WARNING' in line for line in lines)
    # 120 kg aboard: the brakes give 3.0 x 181 / 301 = 1.80, under ego's 2.0.
    heavy = d.describe(Body(payload=120.0), 1.57, 0.5, 1.0, 1.0, 2.0)
    assert heavy[-1].startswith('WARNING: with 120 kg aboard the brakes give only 1.80')
