"""Check the choice of spine_bridge: Rust or Python, and nothing else."""

from aav_spine import bridges
import pytest


def test_each_language_picks_its_package():
    assert bridges.package('rust') == 'aav_spine_bridge'
    assert bridges.package('python') == 'aav_spine'
    assert bridges.package(' Python ') == 'aav_spine'


def test_the_default_is_one_of_them():
    assert bridges.DEFAULT in bridges.PACKAGES


def test_anything_else_is_refused():
    with pytest.raises(ValueError, match='bridge:=cpp'):
        bridges.package('cpp')


def test_the_car_as_wired_today_reads_can_for_sensors_only():
    # Ben, 23 Oct: the ESP32 is driven through the Motor Pi; the Orin's CAN has sensors.
    assert bridges.DEFAULT_ACTUATORS == 'uart'
    assert bridges.role_for('uart') == 'sensors'
    assert bridges.role_for(' CAN ') == 'spine'
    with pytest.raises(ValueError, match='actuators:=pwm'):
        bridges.role_for('pwm')


def test_the_roles():
    assert bridges.ROLES[0] == 'spine'   # the node's own default: the bench and Gazebo
    assert set(bridges.ACTUATORS.values()) == set(bridges.ROLES)
    assert bridges.check_role('sensors') == 'sensors'
    with pytest.raises(ValueError, match='role:=drive'):
        bridges.check_role('drive')
