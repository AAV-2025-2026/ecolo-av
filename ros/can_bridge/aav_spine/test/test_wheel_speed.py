"""Check the front wheel speeds: pairing, freshness, the sign, and the rear-axle speed."""

import math

from aav_spine import can_codec as cc
from aav_spine import wheel_speed as ws
import pytest

L, R = cc.WHEEL_SPEED_L_ID, cc.WHEEL_SPEED_R_ID


def frame(speed, pulses=0, known=False):
    return {'wheel_speed': speed, 'pulse_count': pulses, 'direction_known': int(known)}


def test_publishes_once_per_pair():
    w = ws.FrontWheels(timeout=0.1)
    assert w.update(L, frame(1.0), 0.000)          # right never heard: publish alone
    assert not w.update(R, frame(1.0), 0.001)      # left was just published
    assert w.update(L, frame(1.0), 0.010)          # the pair is complete
    assert not w.update(R, frame(1.0), 0.011)
    assert w.update(L, frame(1.0), 0.020)


def test_a_silent_wheel_does_not_stop_the_other():
    w = ws.FrontWheels(timeout=0.1)
    w.update(L, frame(1.0), 0.0)
    w.update(R, frame(1.0), 0.0)
    assert w.update(L, frame(1.0), 0.5)            # right is stale: publish now
    reading = w.reading(0.5, 1.0)
    assert reading.left_fresh and not reading.right_fresh
    assert reading.mean() is None


def test_mean_of_two_fresh_wheels():
    w = ws.FrontWheels(timeout=0.1)
    w.update(L, frame(1.0, 10), 0.0)
    w.update(R, frame(1.2, 12), 0.0)
    reading = w.reading(0.05, 1.0)
    assert reading.mean() == pytest.approx(1.1)
    assert (reading.left_pulses, reading.right_pulses) == (10, 12)
    assert not reading.direction_measured


def test_magnitude_takes_the_drive_sign_but_a_measured_sign_stays():
    w = ws.FrontWheels(timeout=0.1)
    w.update(L, frame(0.8), 0.0)
    w.update(R, frame(-0.7, known=True), 0.0)
    reading = w.reading(0.0, -1.0)
    assert reading.left == pytest.approx(-0.8)
    assert reading.right == pytest.approx(-0.7)


def test_drive_sign():
    assert ws.drive_sign(-0.5, 1.0) == -1.0      # the spine's measurement wins
    assert ws.drive_sign(0.0, -1.0) == -1.0      # stopped: the command says which way
    assert ws.drive_sign(None, None) == 1.0


def test_rear_axle_speed():
    assert ws.rear_axle_speed(2.0, 0.0) == pytest.approx(2.0)
    assert ws.rear_axle_speed(2.0, 0.5) == pytest.approx(2.0 * math.cos(0.5))
    assert ws.rear_axle_speed(-1.0, -0.3) < 0.0
