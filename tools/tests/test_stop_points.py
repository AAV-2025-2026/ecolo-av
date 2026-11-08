"""The stop-point check's maths (tools/stop_points.py)."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stop_points import (along, at, Sample, slowing_start, Stop, stopped,  # noqa: E402
                         tolerance)


def test_slowing_starts_once_the_hold_was_reached():
    commands = [(0.0, 0.0), (1.0, 0.5), (2.0, 1.0), (3.0, 1.0), (3.1, 0.9), (4.0, 0.0)]
    assert slowing_start(commands, 1.0) == 3.1
    # The ramp up is never taken for the slowing.
    assert slowing_start([(0.0, 0.0), (1.0, 0.5)], 1.0) is None


def test_at_interpolates_and_stops_outside():
    track = [Sample(0.0, 0.0, 0.0, 0.0, 1.0), Sample(1.0, 1.0, 0.0, 0.0, 1.0)]
    assert at(track, 0.5).x == pytest.approx(0.5)
    assert at(track, 2.0) is None and at(track, -1.0) is None
    assert at(track, 0.0).x == 0.0


def test_stopped_needs_a_still_spell():
    track = [Sample(t / 10, t / 10, 0.0, 0.0, 0.0 if t in (5, 6) or t >= 10 else 1.0)
             for t in range(20)]
    s = stopped(track, 0.0, hold=0.5)
    assert s is not None and s.t == pytest.approx(1.0)


def test_along_the_heading():
    o = Sample(0.0, 1.0, 1.0, math.pi / 2, 1.0)
    assert along(o, Sample(1.0, 1.0, 3.0, 0.0, 0.0)) == pytest.approx(2.0)


def test_a_stop_passes_inside_its_tolerance():
    assert tolerance(1.0) == 0.25 and tolerance(5.0) == pytest.approx(0.5)
    good = Stop(speed=1.0, predicted=1.2, truth=1.35, localized=1.5, law=2.0)
    assert good.ok and good.localized_ok
    bad = Stop(speed=1.0, predicted=1.2, truth=1.6, localized=None, law=2.0)
    assert not bad.ok and bad.localized_ok is None
    assert 'predicted 1.20 m' in good.words()
