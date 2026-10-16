"""state.py: the CARLA car's readings as our topics want them."""

import math

from aav_carla import frames, state
import pytest

ORIGIN = frames.SpawnFrame(0.0, 0.0, 0.0)
DATUM = (45.3860, -75.6960)


def test_base_link_is_behind_the_middle():
    # A car at CARLA (10, 0), facing CARLA's +x: base_link 1.4 m behind its middle.
    s = state.car_state((10.0, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 0.0),
                        ORIGIN, rear_axle_x=-1.4)
    assert (s.x, s.y, s.yaw, s.speed) == pytest.approx((8.6, 0.0, 0.0, 2.0))


def test_facing_carlas_right_is_facing_our_south():
    s = state.car_state((0.0, 0.0, 0.0), (0.0, 0.0, 90.0), (0.0, 3.0, 0.0), (0.0, 0.0, 0.0),
                        ORIGIN, rear_axle_x=0.0)
    assert s.yaw == pytest.approx(-math.pi / 2)
    assert s.speed == pytest.approx(3.0)
    assert s.lateral == pytest.approx(0.0, abs=1e-12)


def test_turning_left_slides_the_rear_axle_less():
    # The middle moves straight on, the car turns left at 0.5 rad/s: the rear axle 1.4 m
    # behind swings right (negative) at 0.7 m/s.
    s = state.car_state((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                        (0.0, 0.0, -math.degrees(0.5)), ORIGIN, rear_axle_x=-1.4)
    assert s.yaw_rate == pytest.approx(0.5)
    assert s.lateral == pytest.approx(-0.7)


def test_the_antenna_round_the_datum():
    s = state.CarState(x=100.0, y=0.0, yaw=math.pi / 2, speed=0.0, lateral=0.0, yaw_rate=0.0)
    lat, lon, alt = state.antenna(s, [0.8, 0.0, 1.5], *DATUM)
    e, n, _ = frames.geodetic_to_enu(*DATUM, 0.0, lat, lon, 0.0)
    assert (e, n) == pytest.approx((100.0, 0.8), abs=1e-6)     # 0.8 m north of base_link
    assert alt == pytest.approx(1.5)


def test_the_pacer_waits_for_the_wall_clock():
    p = state.Pacer()
    assert p.wait(10.0, 1000.0) == 0.0          # the first step
    assert p.wait(10.5, 1000.1) == pytest.approx(0.4)
    assert p.wait(11.0, 1001.0) == 0.0           # behind: no wait
    assert p.wait(0.05, 1001.1) == 0.0           # the world restarted
    assert p.wait(0.15, 1001.12) == pytest.approx(0.08)
    assert p.wait(1.0, 1010.0) == 0.0            # far behind: start again
    assert p.start_sim == 1.0
    assert state.Pacer(realtime=False).wait(99.0, 0.0) == 0.0


def test_helpers():
    c = state.covariance_diagonal([1, 2, 3])
    assert c == [1.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 3.0]
    assert state.finite(1.0, 2.0) and not state.finite(1.0, float('nan'))
