"""
foxglove.launch.py, and how the sim, the bench, CARLA and the car start it.

Each test runs a launch file's own setup with some arguments, and looks at what it would
start. Nothing starts: no ROS, no bridge. The stand-ins keep the bridge on this computer
and may send goals; the car's listens on its network and only watches. Every one gets the
WiFi topic list (docs/foxglove.md).
"""

import importlib.util
import os
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext
from launch.actions import IncludeLaunchDescription
from launch.utilities import perform_substitutions
from launch_ros.actions import Node
from launch_ros.utilities import evaluate_parameters
import pytest
import yaml


def load(package, name):
    path = os.path.join(get_package_share_directory(package), 'launch', name)
    spec = importlib.util.spec_from_file_location(name.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FOXGLOVE = load('aav_bringup', 'foxglove.launch.py')
CONFIG = os.path.join(get_package_share_directory('aav_bringup'), 'config',
                      'foxglove_bridge.yaml')
# Every argument foxglove.launch.py takes: a caller passes them all.
ARGUMENTS = {'foxglove_address', 'foxglove_port', 'use_sim_time', 'foxglove_control',
             'foxglove_topics', 'foxglove_preview'}


def context_for(launch_file, **args):
    """Return a launch context with the file's defaults, and these arguments on top."""
    context = LaunchContext()
    for declared in launch_file.generate_launch_description().get_launch_arguments():
        context.launch_configurations[declared.name] = perform_substitutions(
            context, declared.default_value)
    context.launch_configurations.update(args)
    return context


def started(launch_file, **args):
    return launch_file.launch_setup(context_for(launch_file, **args))


def foxglove_include(actions):
    """Return the arguments foxglove.launch.py is included with, or None."""
    for a in actions:
        if isinstance(a, IncludeLaunchDescription):
            # Loading the file expands its path; it also checks that the file loads.
            a.launch_description_source.get_launch_description(LaunchContext())
            if os.path.basename(a.launch_description_source.location) == 'foxglove.launch.py':
                return dict(a.launch_arguments)
    return None


def node(actions, name):
    return next(a for a in actions if isinstance(a, Node) and a._Node__node_name == name)


def settings(actions):
    """Return the bridge's parameters: its file's, then the launch file's on top."""
    found = {}
    for p in evaluate_parameters(LaunchContext(), node(actions, 'foxglove_bridge')
                                 ._Node__parameters):
        if isinstance(p, dict):
            found.update(p)
        else:
            with open(p) as f:
                found.update(yaml.safe_load(f)['foxglove_bridge']['ros__parameters'])
    return found


def allowed(whitelist, topic):
    return any(re.fullmatch(pattern, topic) for pattern in whitelist)


def test_the_defaults_are_this_computer_only_with_the_wifi_list():
    fox = settings(started(FOXGLOVE))
    assert (fox['address'], fox['port']) == ('127.0.0.1', 8765)
    assert 'clientPublish' in fox['capabilities']
    assert fox['sysinfo_topic'].startswith('/system/')


@pytest.mark.parametrize('topic', [
    '/sensors/camera/front_left/image_raw', '/sensors/camera/rear/image_raw/compressed',
    '/perception/detections/image', '/perception/lane/image',
    '/perception/camera/front_left/preview', '/sensors/lidar/points',
    '/sensors/lidar/packets', '/local_costmap/costmap_raw', '/local_costmap/lidar_layer',
    '/global_costmap/static_layer_raw_updates', '/global_costmap/costmap_raw_updates'])
def test_the_wifi_list_leaves_out_the_big_topics(topic):
    whitelist = settings(started(FOXGLOVE))['topic_whitelist']
    assert not allowed(whitelist, topic)
    assert allowed(settings(started(FOXGLOVE, foxglove_topics='all'))['topic_whitelist'],
                   topic)


@pytest.mark.parametrize('topic', [
    '/perception/camera/front_left/preview/compressed', '/sensors/lidar/scan', '/tf',
    '/robot_description', '/vehicle/status', '/local_costmap/costmap', '/plan',
    '/global_costmap/costmap', '/local_costmap/costmap_updates', '/local_costmap/footprint',
    '/diagnostics', '/sensors/gps/fix', '/perception/detections'])
def test_the_wifi_list_keeps_the_small_ones(topic):
    assert allowed(settings(started(FOXGLOVE))['topic_whitelist'], topic)


def test_watch_only_publishes_nothing():
    fox = settings(started(FOXGLOVE, foxglove_control='false'))
    assert not {'clientPublish', 'parameters', 'services'} & set(fox['capabilities'])
    assert not allowed(fox['client_topic_whitelist'], '/safety/estop')
    fox = settings(started(FOXGLOVE))
    assert allowed(fox['client_topic_whitelist'], '/goal_pose')
    assert not allowed(fox['client_topic_whitelist'], '/ego/actuator_cmd')


def test_a_preview_is_a_throttle_and_a_jpeg_republisher():
    actions = started(FOXGLOVE, foxglove_preview='front_left', use_sim_time='true')
    throttle = node(actions, 'preview_throttle_front_left')
    assert [str(x) for x in throttle._Node__arguments] == [
        'messages', '/sensors/camera/front_left/image_raw', '1.0',
        '/perception/camera/front_left/preview']
    jpeg = node(actions, 'preview_jpeg_front_left')
    remaps = {str(a[0][0].text): str(a[1][0].text) for a in jpeg._Node__remappings}
    assert remaps == {'in': '/perception/camera/front_left/preview',
                      'out': '/perception/camera/front_left/preview',
                      'out/compressed': '/perception/camera/front_left/preview/compressed'}
    assert len([a for a in started(FOXGLOVE) if isinstance(a, Node)]) == 1  # no preview


@pytest.mark.parametrize('args, match', [
    ({'foxglove_topics': 'some'}, 'foxglove_topics:=some'),
    ({'foxglove_preview': 'roof'}, "'roof'")])
def test_bad_values_stop_the_launch(args, match):
    with pytest.raises(ValueError, match=match):
        started(FOXGLOVE, **args)


def test_the_sim_keeps_it_on_this_computer_with_the_cameras_preview():
    sim = load('aav_bringup', 'sim.launch.py')
    assert foxglove_include(started(sim)) is None
    sent = foxglove_include(started(sim, foxglove='true', world='road'))
    assert set(sent) == ARGUMENTS
    assert (sent['foxglove_address'], sent['use_sim_time'], sent['foxglove_control'],
            sent['foxglove_topics'], sent['foxglove_preview']) == (
        '127.0.0.1', 'true', 'true', 'wifi', 'front_left')
    # The empty world renders no camera: nothing to preview.
    assert foxglove_include(started(sim, foxglove='true'))['foxglove_preview'] == ''


def test_the_bench_keeps_it_on_this_computer():
    sent = foxglove_include(started(load('aav_bringup', 'bench.launch.py'), foxglove='true'))
    assert set(sent) == ARGUMENTS
    assert (sent['foxglove_address'], sent['use_sim_time'], sent['foxglove_preview']) == (
        '127.0.0.1', 'false', 'front_left')


def test_carla_keeps_it_on_this_computer():
    carla = load('aav_bringup', 'carla.launch.py')
    sent = foxglove_include(started(carla, foxglove='true'))
    assert set(sent) == ARGUMENTS
    assert (sent['foxglove_address'], sent['foxglove_port'], sent['foxglove_preview']) == (
        '127.0.0.1', '8765', 'front_left')
    sent = foxglove_include(started(carla, foxglove='true', cameras='false'))
    assert sent['foxglove_preview'] == ''


def test_the_car_listens_on_its_network_and_only_watches():
    sent = foxglove_include(started(load('aav_bringup', 'car.launch.py'), machine='orin'))
    assert set(sent) == ARGUMENTS
    assert (sent['foxglove_address'], sent['foxglove_control'], sent['foxglove_topics'],
            sent['foxglove_preview']) == ('0.0.0.0', 'false', 'wifi', '')
    assert foxglove_include(started(load('aav_bringup', 'car.launch.py'),
                                    machine='motor_pi')) is None
