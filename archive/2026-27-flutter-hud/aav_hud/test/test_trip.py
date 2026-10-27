"""Tests for trip.py: the Nav2 goal's progress, as the map page shows it."""

from aav_hud import trip
from aav_hud.route import distance, Waypoint
import pytest

try:
    from action_msgs.msg import GoalStatus
except ImportError:
    GoalStatus = None

A = Waypoint(45.3870, -75.6960, 1.5708)
B = Waypoint(45.3880, -75.6960, 1.5708)
CAR = (45.3860, -75.6960)


def test_no_route_yet():
    t = trip.Trip()
    assert not t.active
    assert t.event() == {'distance': 0.0, 'status': 'waiting_for_goal', 'waypoint': 0,
                         'waypoints': 0, 'message': ''}
    assert not t.cancel()


def test_a_route_from_sending_to_the_goal():
    t = trip.Trip([A, B])
    assert t.status == trip.SENDING and t.active
    assert t.answered(True)
    assert t.status == trip.NAVIGATING
    whole = distance(CAR, A[:2]) + distance(A[:2], B[:2])
    assert t.event(CAR)['distance'] == pytest.approx(whole, abs=0.1)
    assert t.event(CAR)['waypoint'] == 1
    assert t.feedback(1)
    assert not t.feedback(1)        # the same waypoint again: nothing new
    assert t.event(A[:2])['distance'] == pytest.approx(distance(A[:2], B[:2]), abs=0.1)
    assert t.event()['waypoint'] == 2
    t.finished(trip.STATUS_SUCCEEDED)
    assert t.event(CAR) == {'distance': 0.0, 'status': 'goal_reached', 'waypoint': 2,
                            'waypoints': 2, 'message': ''}
    assert not t.active


def test_rejected():
    t = trip.Trip([A])
    assert t.answered(False)
    assert t.status == trip.REJECTED and not t.active
    assert 'still starting' in t.event()['message']


def test_cancel_while_sending_cancels_once_nav2_answers():
    t = trip.Trip([A, B])
    assert t.cancel()
    assert t.status == trip.CANCELING
    assert not t.answered(True)     # the HUD must cancel the goal it just got
    t.finished(trip.STATUS_CANCELED)
    assert t.status == trip.CANCELED and not t.active


def test_missed_waypoints_keep_the_true_distance():
    t = trip.Trip([A, B])
    t.answered(True)
    t.feedback(1)
    t.finished(trip.STATUS_SUCCEEDED, missed=1)
    e = t.event(CAR)
    assert e['status'] == 'missed_waypoints'
    assert e['message'] == 'missed 1 of 2 waypoints'
    assert e['distance'] == pytest.approx(distance(CAR, B[:2]), abs=0.1)


def test_aborted_says_why():
    t = trip.Trip([A])
    t.answered(True)
    t.finished(trip.STATUS_ABORTED, error='no valid path')
    assert t.event()['status'] == 'aborted'
    assert t.event()['message'] == 'no valid path'
    t.finished(trip.STATUS_ABORTED)
    assert 'newer goal' in t.message
    t.finished(0)
    assert t.message == 'goal status 0'


def test_nav2_not_running():
    t = trip.Trip([A], status=trip.NO_NAV2)
    assert not t.active
    assert t.event()['status'] == 'nav2_not_running'


def test_feedback_stays_in_range():
    t = trip.Trip([A, B])
    t.feedback(99)
    assert t.index == 2
    assert t.distance(CAR) == 0.0


@pytest.mark.skipif(GoalStatus is None, reason='needs ROS sourced: colcon test')
def test_codes_match_goal_status():
    assert GoalStatus.STATUS_SUCCEEDED == trip.STATUS_SUCCEEDED
    assert GoalStatus.STATUS_CANCELED == trip.STATUS_CANCELED
    assert GoalStatus.STATUS_ABORTED == trip.STATUS_ABORTED
