"""The stop point: where a full brake now stops the car, from the shared car model."""

from dataclasses import replace

from aav_description.car_model import ActuatorConfig, CarState
from aav_ego.stop_ahead import s_of_v, stop_point
import pytest

CFG = ActuatorConfig()


def test_a_parked_car_stops_where_it_is():
    stop = stop_point(CFG, CarState())
    assert stop.found and stop.distance == 0.0 and stop.time == 0.0
    assert (stop.x, stop.y) == (0.0, 0.0)


@pytest.mark.parametrize('v', [0.5, 1.0, 2.0, 4.0])
def test_the_stop_matches_the_designs_curve(v):
    # S(v) = v tau + v^2 / 2a, with tau the brake's dead time and about its lag: the drag
    # only shortens it. docs/designs/2026-11-05_how-the-car-stops.md.
    stop = stop_point(CFG, CarState(v=v))
    assert stop.found
    shortest = v * v / (2.0 * CFG.max_brake)
    longest = s_of_v(v, CFG.brake_dead_time + CFG.brake_lag + 0.05, CFG.max_brake)
    assert shortest < stop.distance < longest
    assert stop.x == pytest.approx(stop.distance, rel=1e-6)   # straight ahead
    assert stop.y == pytest.approx(0.0, abs=1e-9)


def test_a_dead_time_moves_the_stop_further():
    late = replace(CFG, brake_dead_time=0.3)
    assert stop_point(late, CarState(v=1.0)).distance == pytest.approx(
        stop_point(CFG, CarState(v=1.0)).distance + 0.3, abs=0.03)


def test_wheels_turned_left_stop_it_to_the_left():
    turning = CarState(v=2.0, steer=0.3, steer_setpoint=0.3, steer_motor=0.3,
                       steer_linkage=0.3)
    stop = stop_point(CFG, turning)
    assert stop.y > 0.05 and stop.yaw > 0.0
    assert stop.distance > stop.x


def test_backwards_it_stops_behind():
    stop = stop_point(CFG, CarState(v=-1.0))
    assert stop.found and stop.x < 0.0 and stop.distance > 0.0


def test_the_throttle_still_pushing_runs_it_further():
    pushing = CarState(v=1.0, throttle_level=1.0)
    assert stop_point(CFG, pushing).distance > stop_point(CFG, CarState(v=1.0)).distance


def test_a_car_with_no_brake_is_not_found():
    coasting = replace(CFG, max_brake=0.0, drag=0.0)
    stop = stop_point(coasting, CarState(v=1.0), max_time=2.0)
    assert not stop.found and stop.time >= 2.0


def test_the_state_passed_in_is_not_changed():
    state = CarState(x=5.0, y=1.0, yaw=0.4, v=1.0)
    stop = stop_point(CFG, state)
    assert state.v == 1.0 and state.x == 5.0
    assert stop.x == pytest.approx(stop.distance)   # base_link: from (0, 0), facing +x
