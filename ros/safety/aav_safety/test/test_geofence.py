"""Geofence: the fence's shapes, the stopping distance, and when the lock goes on and off."""

import math

from aav_safety.geofence import (Circle, Geofence, LOST, NEAR, OK, OUTSIDE, Polygon, Pose,
                                 Settings, STARTING, stopping_distance)
import pytest

# A 2 m x 1 m car, base_link 0.5 m from the back.
CAR = [(1.5, 0.5), (1.5, -0.5), (-0.5, -0.5), (-0.5, 0.5)]
SQUARE = Polygon([(-10, -10), (10, -10), (10, 10), (-10, 10)])


def settled(fence=None, radius=None, settings=Settings(), x=0.0, y=0.0, yaw=0.0):
    """A geofence that has had 4 s of good poses at (x, y), standing still."""
    g = Geofence(CAR, settings, fence=fence, radius=radius)
    for i in range(41):
        g.update(i * 0.1, Pose(x, y, yaw, 0.0, 0.2))
    return g


def test_circle_and_polygon_depths():
    c = Circle(1.0, 2.0, 10.0)
    assert c.depth(1.0, 2.0) == pytest.approx(10.0)
    assert c.depth(11.0, 2.0) == pytest.approx(0.0)
    assert c.depth(1.0, 14.0) == pytest.approx(-2.0)
    assert SQUARE.depth(0.0, 0.0) == pytest.approx(10.0)
    assert SQUARE.depth(9.0, 0.0) == pytest.approx(1.0)
    assert SQUARE.depth(12.0, 0.0) == pytest.approx(-2.0)
    assert SQUARE.depth(13.0, 14.0) == pytest.approx(5.0 * -1)   # past a corner: 3-4-5
    # Either way round, and from a flat parameter.
    backwards = Polygon.from_flat([-10, 10, 10, 10, 10, -10, -10, -10])
    assert backwards.depth(9.0, 0.0) == pytest.approx(1.0)


def test_an_l_shaped_lot():
    ell = Polygon([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])
    assert ell.depth(15.0, 15.0) < 0.0          # the missing corner is outside
    assert ell.depth(5.0, 15.0) == pytest.approx(5.0)


def test_bad_fences_are_refused():
    for bad in ([(0, 0), (1, 1)], [(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 0), (float('nan'), 1)]):
        with pytest.raises(ValueError):
            Polygon(bad)
    with pytest.raises(ValueError):
        Polygon.from_flat([0, 0, 1, 0, 1])
    for r in (0.0, -1.0, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            Circle(0.0, 0.0, r)
    with pytest.raises(ValueError):
        Geofence(CAR)
    with pytest.raises(ValueError):
        Geofence(CAR, radius=0.0)
    with pytest.raises(ValueError):
        Settings(braking=0.0)
    with pytest.raises(ValueError):
        Settings(margin=float('nan'))


def test_stopping_distance_is_rss():
    assert stopping_distance(0.0, 0.6, 1.0) == 0.0
    assert stopping_distance(1.0, 0.6, 1.0) == pytest.approx(1.1)
    assert stopping_distance(-2.0, 0.5, 2.0) == pytest.approx(2.0)


def test_locked_until_a_settled_pose():
    g = Geofence(CAR, fence=SQUARE)
    assert g.check(0.0)[:2] == (True, STARTING)
    g.update(0.0, Pose(0, 0, 0, 0, 0.2))
    assert g.check(1.0)[:2] == (True, STARTING)
    g.update(3.0, Pose(0, 0, 0, 0, 0.2))
    assert g.check(3.0)[:2] == (False, OK)


def test_a_circle_is_placed_where_the_car_first_stands_still():
    g = Geofence(CAR, radius=20.0)
    for i in range(40):
        g.update(i * 0.1, Pose(100.0, 50.0, 0.0, 1.0, 0.2))   # moving: not yet
    assert g.fence is None and g.check(4.0)[0]
    g.update(4.0, Pose(100.0, 50.0, 0.0, 0.0, 0.2))
    assert (g.fence.cx, g.fence.cy) == (100.0, 50.0)
    assert g.check(4.0)[:2] == (False, OK)


def test_lost_when_stale_unsure_or_nan_and_back_when_good():
    g = settled(fence=SQUARE)
    assert not g.check(4.0)[0]
    assert g.check(5.5)[:2] == (True, LOST)                   # 1.5 s without a pose
    g.update(6.0, Pose(0, 0, 0, 0, 5.0))                      # 5 m unsure
    assert g.check(6.0)[:2] == (True, LOST)
    g.update(6.1, Pose(float('nan'), 0, 0, 0, 0.2))
    assert g.check(6.1)[:2] == (True, LOST)
    for i in range(31):                                       # 3 s of good poses again
        g.update(6.2 + i * 0.1, Pose(0, 0, 0, 0, 0.2))
    assert g.check(9.25)[:2] == (False, OK)


def test_the_faster_the_car_the_earlier_it_stops():
    s = Settings()
    # Facing east (+x) at x = 5: the front corners are at 6.5, 3.5 m from the edge.
    slow = settled(fence=SQUARE, x=5.0)
    slow.update(4.1, Pose(5.0, 0.0, 0.0, 0.5, 0.2))
    assert slow.check(4.1)[:2] == (False, OK)
    # At 2 m/s: 2*0.6 + 4/2 = 3.2 m on, so 0.3 m from the edge: well inside margin + std.
    fast = settled(fence=SQUARE, x=5.0)
    fast.update(4.1, Pose(5.0, 0.0, 0.0, 2.0, 0.2))
    assert fast.check(4.1)[:2] == (True, NEAR)
    assert s.margin == 1.0


def test_the_spread_widens_the_margin():
    g = settled(fence=SQUARE, x=6.5)        # front corners 2.0 m from the edge
    g.update(4.1, Pose(6.5, 0.0, 0.0, 0.0, 0.5))
    assert not g.check(4.1)[0]               # needs 1.0 + 0.5
    g.update(4.2, Pose(6.5, 0.0, 0.0, 0.0, 1.5))
    assert g.check(4.2)[:2] == (True, NEAR)  # needs 1.0 + 1.5


def test_reversing_looks_behind():
    g = settled(fence=SQUARE, x=-6.0)        # rear corners at -6.5: 3.5 m from the edge
    g.update(4.1, Pose(-6.0, 0.0, 0.0, -2.0, 0.2))
    assert g.check(4.1)[:2] == (True, NEAR)
    g.update(4.2, Pose(-6.0, 0.0, 0.0, 2.0, 0.2))   # forward, away from that edge
    assert g.check(4.2)[:2] == (False, OK)


def test_heading_turns_the_car():
    g = settled(fence=SQUARE, y=6.0, yaw=math.pi / 2)    # facing north, front at y = 7.5
    g.update(4.1, Pose(0.0, 6.0, math.pi / 2, 2.0, 0.2))
    assert g.check(4.1)[:2] == (True, NEAR)


def test_near_lets_go_only_further_in():
    g = settled(fence=SQUARE, x=7.4)          # front 1.1 m from the edge: needs 1.2
    g.update(4.1, Pose(7.4, 0.0, 0.0, 0.0, 0.2))
    assert g.check(4.1)[:2] == (True, NEAR)
    g.update(4.2, Pose(7.2, 0.0, 0.0, 0.0, 0.2))  # 1.3 m: past 1.2, not past 1.7
    assert g.check(4.2)[0]
    g.update(4.3, Pose(6.7, 0.0, 0.0, 0.0, 0.2))  # 1.8 m
    assert g.check(4.3)[:2] == (False, OK)


def test_outside_latches_until_a_person_clears_it_inside():
    g = settled(fence=SQUARE)
    g.update(4.1, Pose(11.0, 0.0, 0.0, 0.0, 0.2))
    assert g.check(4.1)[:2] == (True, OUTSIDE)
    assert g.clear(4.1)[0] is False             # still outside
    g.update(4.2, Pose(0.0, 0.0, 0.0, 0.0, 0.2))   # driven back in
    locked, state, why = g.check(4.2)
    assert (locked, state) == (True, OUTSIDE) and 'clear' in why
    assert g.clear(4.2)[0] is True
    assert g.check(4.2)[:2] == (False, OK)
    assert g.clear(4.3) == (True, 'nothing to clear')


def test_clear_needs_a_good_pose():
    g = settled(fence=SQUARE)
    g.update(4.1, Pose(11.0, 0.0, 0.0, 0.0, 0.2))
    g.check(4.1)
    g.update(4.2, Pose(0.0, 0.0, 0.0, 0.0, 9.0))
    assert g.clear(4.2)[0] is False
