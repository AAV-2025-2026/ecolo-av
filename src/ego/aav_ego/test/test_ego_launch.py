"""ego.launch.py's speed caps: max_speed only lowers; sim_max_speed only in a simulator."""

import importlib.util
from pathlib import Path

import pytest

try:
    from launch import LaunchContext
    from launch_ros.actions import Node
    LAUNCH = Path(__file__).resolve().parents[1] / 'launch' / 'ego.launch.py'
    spec = importlib.util.spec_from_file_location('ego_launch', LAUNCH)
    ego_launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ego_launch)   # reads ego.yaml from the installed share
    HAVE_ROS = True
except Exception:   # noqa: BLE001 - no ROS, or the package isn't installed
    HAVE_ROS = False

pytestmark = pytest.mark.skipif(not HAVE_ROS, reason='needs ROS and the built workspace')


def nodes(**config):
    context = LaunchContext()
    context.launch_configurations.update({'use_sim_time': 'false', **config})
    return ego_launch.ego_node(context)


def test_no_caps_by_default():
    (node,) = nodes()
    assert isinstance(node, Node)


def test_max_speed_can_only_lower():
    nodes(max_speed='0.3')
    with pytest.raises(ValueError):
        nodes(max_speed='2.0')


def test_sim_max_speed_is_refused_on_the_car():
    with pytest.raises(ValueError, match='simulators only'):
        nodes(sim_max_speed='3.0')


def test_sim_max_speed_in_a_simulator():
    nodes(use_sim_time='true', sim_max_speed='3.0')
    with pytest.raises(ValueError):
        nodes(use_sim_time='true', sim_max_speed='9.0')
