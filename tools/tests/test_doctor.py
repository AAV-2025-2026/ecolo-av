"""Tests for tools/doctor.py's word on the 2025-26 software, still on the car."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import doctor  # noqa: E402


def test_the_old_car_on_domain_0_says_how_to_watch_it():
    status, detail = doctor.old_car_line({0: ['/carla/ego_vehicle/imu', '/battery_status'],
                                          10: []})
    assert status == 'OK'
    assert 'domain 0: 2 topics, such as /battery_status, /carla/ego_vehicle/imu' in detail
    assert 'export ROS_DOMAIN_ID=0 (ours stays 42)' in detail
    assert 'domain 10' not in detail


def test_nothing_on_either_domain_is_a_warning():
    status, detail = doctor.old_car_line({0: [], 10: []})
    assert status == 'WARN'
    assert 'domain 0 or 10' in detail
