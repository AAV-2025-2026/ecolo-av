"""Tests for events.py: ROS messages to the payloads the Flutter app reads."""

import math
from pathlib import Path
import re
from types import SimpleNamespace

from aav_hud import events
import pytest

# Not pytest.importorskip: ROS's launch_testing pytest plugin turns a module-level skip
# into a skip of every test in the folder.
try:
    from aav_interfaces.msg import VehicleStatus
    from sensor_msgs.msg import NavSatStatus
except ImportError:
    VehicleStatus = None


def status(**fields):
    base = {'mode': 0, 'armed': False, 'estop_active': False, 'speed': 0.0,
            'steering_angle': 0.0, 'throttle': 0.0, 'brake': 0.0, 'faults': 0}
    base.update(fields)
    return SimpleNamespace(**base)


def fix(lat, lon, state=0):
    return SimpleNamespace(latitude=lat, longitude=lon, status=SimpleNamespace(status=state))


# The app's list of event names (Dart), next to this package in the repository.
APP_EVENTS = (Path(__file__).resolve().parents[4]
              / 'hud/flutter_pi/lib/components/sockets/hud_events.dart')


@pytest.mark.skipif(not APP_EVENTS.is_file(), reason='the app is not next to this package')
def test_the_app_listens_for_the_same_events():
    names = re.findall(r"static const \w+ = '([a-z_]+)';", APP_EVENTS.read_text())
    assert sorted(names) == sorted(events.EVENTS)


def test_no_event_says_mock_any_more():
    assert not [name for name in events.EVENTS if 'mock' in name]


def test_speed_keeps_the_sign():
    assert events.speed_event(status(speed=1.23456)) == {'speed': 1.23}
    assert events.speed_event(status(speed=-0.5)) == {'speed': -0.5}


@pytest.mark.parametrize('mode, armed, estop, speed, letter', [
    (2, True, False, 0.0, 'D'),     # the computer drives and may move
    (2, False, False, 0.0, 'P'),    # not armed
    (2, True, True, 0.0, 'P'),      # e-stop
    (0, True, False, 0.0, 'P'),     # a person drives, standing still
    (0, False, False, 1.0, 'D'),    # moving forward, whoever drives
    (2, True, False, -0.3, 'R'),
    (2, True, False, 0.04, 'D'),    # creeping counts as standing still
    (1, True, False, -0.04, 'P'),
])
def test_gear_letter(mode, armed, estop, speed, letter):
    assert events.gear(mode, armed, estop, speed) == letter


def test_vehicle_event_in_plain_words():
    e = events.vehicle_event(status(mode=2, armed=True, speed=1.5, steering_angle=0.12345,
                                    throttle=0.333, faults=1 | 8))
    assert e == {'mode': 'computer', 'armed': True, 'estop': False, 'gear': 'D',
                 'speed': 1.5, 'steering_angle': 0.123, 'throttle': 0.33, 'brake': 0.0,
                 'faults': ['cmd_timeout', 'steering_driver']}


def test_unknown_mode_and_fault_bits():
    e = events.vehicle_event(status(mode=7, faults=2048 | 1, estop_active=True))
    assert e['mode'] == 'unknown'
    assert e['estop'] is True
    assert e['faults'] == ['cmd_timeout', '0x0800']


def test_position():
    assert events.fix_position(fix(45.38, -75.69)) == (45.38, -75.69)
    # Jazzy's default status is STATUS_UNKNOWN (-2); navsat_transform accepts it too.
    assert events.fix_position(fix(45.38, -75.69, state=-2)) == (45.38, -75.69)
    assert events.position_event(45.38, -75.69) == {'latitude': 45.38, 'longitude': -75.69}


@pytest.mark.parametrize('bad', [
    fix(45.0, -75.0, state=-1),     # no fix
    fix(math.nan, -75.0),
    fix(45.0, math.inf),
    fix(91.0, 0.0),
    fix(0.0, 181.0),
])
def test_no_position_without_a_fix(bad):
    assert events.fix_position(bad) is None


def test_stop_sign():
    assert events.stop_sign_event(SimpleNamespace(data=True)) == {
        'detected': True, 'message': 'STOP'}
    assert events.stop_sign_event(SimpleNamespace(data=False))['detected'] is False


def battery(voltage, percentage, current):
    return SimpleNamespace(voltage=voltage, percentage=percentage, current=current)


def test_battery_in_volts_percent_and_amps():
    # The Victron monitor gives all three; BatteryState's charge goes from 0 to 1.
    assert events.battery_event(battery(48.4567, 0.5234, -12.345)) == {
        'voltage': 48.46, 'percentage': 52.3, 'current': -12.35}


def test_what_the_battery_monitor_does_not_measure_is_none():
    # The bench's mock_battery has no current; JSON has no NaN, so it must be None.
    e = events.battery_event(battery(49.0, math.nan, math.nan))
    assert e == {'voltage': 49.0, 'percentage': None, 'current': None}
    assert events.battery_event(battery(math.inf, 1.0, 0.0))['voltage'] is None


def test_throttle():
    t = events.Throttle(10.0)
    assert t.ready('a', 0.0)
    assert not t.ready('a', 0.05)
    assert t.ready('b', 0.05)       # each key has its own clock
    assert t.ready('a', 0.1)
    unlimited = events.Throttle(0.0)
    assert all(unlimited.ready('a', 0.0) for _ in range(3))


@pytest.mark.skipif(VehicleStatus is None, reason='needs ROS sourced: colcon test')
def test_tables_match_the_messages():
    names = [n for n in dir(type(VehicleStatus)) if n.isupper() and not n.startswith('_')]
    constants = {n: getattr(VehicleStatus, n) for n in names}
    modes = {v: n[len('MODE_'):].lower() for n, v in constants.items() if n.startswith('MODE_')}
    faults = {v: n[len('FAULT_'):].lower() for n, v in constants.items()
              if n.startswith('FAULT_')}
    assert modes == events.MODE_NAMES
    assert faults == events.FAULT_NAMES
    assert VehicleStatus.MODE_COMPUTER == events.MODE_COMPUTER
    assert NavSatStatus.STATUS_NO_FIX == events.NO_FIX
