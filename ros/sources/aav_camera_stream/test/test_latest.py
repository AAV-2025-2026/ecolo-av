"""The newest-frame slot, the rate meter, the delay statistics, the stamp."""

import threading

from aav_camera_stream.latest import Delays, Latest, Rate, stamp_ns
import pytest


def test_take_gets_the_newest_and_counts_the_dropped():
    slot = Latest()
    for i in range(5):
        slot.put(i)
    assert slot.take(0.1) == 4
    assert slot.dropped == 4
    assert slot.take(0.01) is None          # nothing newer yet


def test_take_waits_for_a_put():
    slot = Latest()
    threading.Timer(0.05, slot.put, args=('frame',)).start()
    assert slot.take(2.0) == 'frame'
    assert slot.dropped == 0


def test_rate():
    now = [0.0]
    rate = Rate(window=5.0, clock=lambda: now[0])
    for _ in range(16):
        rate.tick()
        now[0] += 1.0 / 15
    assert rate.hz() == pytest.approx(15.0, rel=0.01)
    now[0] += 10.0
    assert rate.hz() == 0.0


def test_delays():
    d = Delays(keep=100)
    assert d.summary() is None
    for i in range(1, 101):
        d.add(i / 1000.0)
    s = d.summary()
    assert s['n'] == 100
    assert s['median'] == pytest.approx(0.0505)
    assert s['p95'] == pytest.approx(0.095)
    assert s['max'] == pytest.approx(0.100)
    d.add(1.0)                               # the oldest goes
    assert d.summary()['n'] == 100 and d.count == 101


def test_stamp_is_arrival_minus_delay():
    # On the car the node's clock is the wall clock.
    assert stamp_ns(10_000_000_000, 10_050_000_000, 10_050_000_000, 0.15) == 9_850_000_000


def test_stamp_on_a_simulators_clock():
    # The simulator's clock is 1000 s behind the wall: the stamp moves with it.
    wall, sim = 2_000_000_000_000, 1_000_000_000_000
    assert stamp_ns(wall - 30_000_000, sim, wall, 0.1) == sim - 30_000_000 - 100_000_000


def test_stamp_never_before_zero():
    assert stamp_ns(0, 0, 0, 1.0) == 0
