"""The RC driver's rules (TODO 48): the sticks to a command, only on RC via ROS. No ROS."""

import math

from aav_rc.rc_drive import (Limits, RcDrive, Sticks, SWITCH_COMPUTER, SWITCH_NONE,
                             SWITCH_RC_DIRECT, SWITCH_RC_VIA_ROS, twist)
import pytest

LIM = Limits(max_speed=1.0, max_reverse_speed=0.5, max_steering_angle=0.5, wheelbase=1.57)


def via_ros(throttle=0.0, steering=0.0, brake=False):
    return Sticks(SWITCH_RC_VIA_ROS, throttle, steering, brake)


def test_full_stick_is_max_speed_and_full_lock_as_a_turn_rate():
    v, w = twist(via_ros(1.0, 1.0), LIM)
    assert v == 1.0
    assert w == pytest.approx(1.0 * math.tan(0.5) / 1.57)     # 0.35 rad/s, left
    v, w = twist(via_ros(0.5, -0.5), LIM)
    assert v == 0.5 and w == pytest.approx(0.5 * math.tan(-0.25) / 1.57)


def test_reverse_is_slower_and_the_gear_brake_stops():
    assert twist(via_ros(-1.0), LIM) == (-0.5, 0.0)
    assert twist(via_ros(1.0, 1.0, brake=True), LIM) == (0.0, 0.0)
    # Out of range or not a number: clamped, or nothing.
    assert twist(via_ros(3.0), LIM)[0] == 1.0
    assert twist(via_ros(float('nan'), float('nan')), LIM) == (0.0, 0.0)


def test_it_drives_only_on_rc_via_ros():
    d = RcDrive(LIM)
    assert d.command(0.0) is None                      # never heard
    for switch in (SWITCH_NONE, SWITCH_COMPUTER, SWITCH_RC_DIRECT):
        d.heard(Sticks(switch, 1.0, 0.0, False), 1.0)
        assert d.command(1.0) is None, switch
    d.heard(via_ros(0.0), 2.0)
    assert d.command(2.0) == (0.0, 0.0)                # centred sticks: zeros, published
    d.heard(via_ros(0.5), 2.02)
    assert d.command(2.02) == (0.5, 0.0)


def test_leaving_rc_via_ros_sends_one_zero():
    d = RcDrive(LIM)
    d.heard(via_ros(0.5), 1.0)
    assert d.command(1.0) == (0.5, 0.0)
    d.heard(Sticks(SWITCH_RC_DIRECT, 1.0, 0.0, False), 1.02)
    assert d.command(1.02) == (0.0, 0.0)
    assert d.command(1.04) is None
    d.heard(Sticks(SWITCH_COMPUTER, 1.0, 0.0, False), 1.06)
    assert d.command(1.06) is None


def test_quiet_on_rc_via_ros_holds_a_stop():
    d = RcDrive(LIM)
    d.heard(via_ros(0.8), 1.0)
    assert d.command(1.1) == (0.8, 0.0)                # 0.1 s old: still fresh
    assert d.command(1.3) == (0.0, 0.0)                # stale: a stop, and again
    assert d.command(5.0) == (0.0, 0.0)
    d.heard(Sticks(SWITCH_COMPUTER, 0.0, 0.0, False), 5.1)
    assert d.command(5.1) == (0.0, 0.0)                # back, on computer: the last zero
    assert d.command(5.12) is None
