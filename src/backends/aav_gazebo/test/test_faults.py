import math
from types import SimpleNamespace

from aav_gazebo import faults
from aav_gazebo.faults import Fault
import pytest


def reading(value):
    return SimpleNamespace(value=value, stamp=0)


def test_ok_passes_on_and_stop_sends_nothing():
    f = Fault('imu')
    msg = reading(1.0)
    assert f.apply(msg) is msg
    f.switch('stop')
    assert f.apply(reading(2.0)) is None


def test_freeze_repeats_the_last_good_message_as_a_copy():
    f = Fault('odom')
    f.apply(reading(1.0))
    f.switch('freeze')
    out = f.apply(reading(2.0))
    assert out.value == 1.0
    out.stamp = 99                       # the adapter restamps it: the held one stays
    assert f.apply(reading(3.0)).stamp == 0


def test_freeze_before_anything_sends_nothing():
    f = Fault('camera')
    f.switch('freeze')
    assert f.apply(reading(1.0)) is None


def test_nan_and_jump_change_a_copy():
    def to_nan(m):
        m.value = float('nan')

    def north(m):
        m.value = faults.jumped(m.value)

    f = Fault('gps')
    msg = reading(45.0)
    f.switch('nan')
    assert math.isnan(f.apply(msg, nan=to_nan, jump=north).value)
    f.switch('jump')
    out = f.apply(msg, nan=to_nan, jump=north)
    assert (out.value - 45.0) * faults.METRES_PER_DEGREE == pytest.approx(faults.JUMP_NORTH)
    assert msg.value == 45.0


def test_the_relayed_bridge_moves_only_the_front_left_picture():
    bridge = [{'ros_topic_name': faults.CAMERA}, {'ros_topic_name': '/sensors/camera/rear'}]
    out = faults.relayed(bridge)
    assert [e['ros_topic_name'] for e in out] == [faults.CAMERA_RELAYED, '/sensors/camera/rear']
    assert bridge[0]['ros_topic_name'] == faults.CAMERA


def test_each_sensor_has_only_its_own_faults():
    assert faults.check('gps', 'jump') is None
    assert 'no' in faults.check('imu', 'jump')
    assert 'no sensor' in faults.check('lidar', 'stop')
    with pytest.raises(ValueError):
        Fault('radar').switch('nan')


def test_every_sensor_has_one_node_for_its_fault():
    assert set(faults.NODES) == set(faults.SENSORS)
    assert faults.NODES['odom'] == 'gazebo_adapter'          # the wheels go with the car
    assert len(set(faults.NODES.values())) == len(faults.NODES)
