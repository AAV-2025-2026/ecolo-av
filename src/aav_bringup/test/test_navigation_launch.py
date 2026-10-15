"""
aav_navigation's navigation.launch.py: reversing, and sim.launch.py's faster Nav2.

Each test runs the launch file's own setup with some arguments, then reads the settings
each Nav2 server would get: the rewritten copy of nav2.yaml, as the server would load it.
Nothing starts: no ROS, no Nav2. The car is forward only; reversing:=true (Gazebo, the
bench) lets Nav2 plan, follow and back up in reverse, at vehicle.yaml's max_reverse_speed.
"""

import importlib.util
import os

from aav_description import vehicle
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext
from launch.actions import IncludeLaunchDescription
from launch.utilities import perform_substitutions
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
import pytest
import yaml


def load(package, name):
    path = os.path.join(get_package_share_directory(package), 'launch', name)
    spec = importlib.util.spec_from_file_location(name.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NAV = load('aav_navigation', 'navigation.launch.py')
SIM = load('aav_bringup', 'sim.launch.py')
CAR = load('aav_bringup', 'car.launch.py')
BENCH = load('aav_bringup', 'bench.launch.py')
REVERSE = float(vehicle.load()['vehicle']['max_reverse_speed'])


def context_for(launch_file, **args):
    """Return a launch context with the file's defaults, and these arguments on top."""
    context = LaunchContext()
    for declared in launch_file.generate_launch_description().get_launch_arguments():
        context.launch_configurations[declared.name] = perform_substitutions(
            context, declared.default_value)
    context.launch_configurations.update(args)
    return context


def settings(**args):
    """Return {server: its ros__parameters}, from the file each Nav2 server would load."""
    context = context_for(NAV, map='/maps/empty.yaml', **args)
    found = {}
    for a in NAV.nodes(context):
        if not isinstance(a, Node):
            continue
        name = a._Node__node_name
        for p in a._Node__parameters:
            if isinstance(p, ParameterFile):
                with open(p.evaluate(context)) as f:
                    found[name] = yaml.safe_load(f)[name]['ros__parameters']
    return found


def sent_to_navigation(launch_file, **args):
    """Return the arguments a bringup file gives navigation.launch.py."""
    for a in launch_file.launch_setup(context_for(launch_file, **args)):
        if isinstance(a, IncludeLaunchDescription):
            # Loading the file expands its path.
            a.launch_description_source.get_launch_description(LaunchContext())
            if os.path.basename(a.launch_description_source.location) == 'navigation.launch.py':
                return dict(a.launch_arguments)
    raise AssertionError('navigation.launch.py is not included')


def test_forward_only_by_default():
    s = settings()
    assert s['planner_server']['GridBased']['motion_model_for_search'] == 'DUBIN'
    assert s['controller_server']['FollowPath']['allow_reversing'] is False
    assert s['controller_server']['MPPI']['vx_min'] == 0.0
    assert s['velocity_smoother']['min_velocity'][0] == 0.0
    trees = s['bt_navigator']
    assert trees['default_nav_to_pose_bt_xml'].endswith('navigate_to_pose_car.xml')
    assert trees['default_nav_through_poses_bt_xml'].endswith('navigate_through_poses_car.xml')


def test_reversing_plans_follows_and_backs_up_at_the_cars_reverse_speed():
    s = settings(reversing='true')
    assert s['planner_server']['GridBased']['motion_model_for_search'] == 'REEDS_SHEPP'
    assert s['controller_server']['FollowPath']['allow_reversing'] is True
    assert s['controller_server']['MPPI']['vx_min'] == pytest.approx(-REVERSE)
    assert s['velocity_smoother']['min_velocity'] == pytest.approx([-REVERSE, 0.0, -1.0])
    trees = s['bt_navigator']
    assert trees['default_nav_to_pose_bt_xml'].endswith('navigate_to_pose_car_reversing.xml')
    assert trees['default_nav_through_poses_bt_xml'].endswith(
        'navigate_through_poses_car_reversing.xml')
    for key in ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml'):
        assert os.path.isfile(trees[key]), trees[key]


def test_a_faster_nav2_keeps_reversing_slow():
    s = settings(reversing='true', max_speed='3')
    assert s['controller_server']['FollowPath']['desired_linear_vel'] == 3.0
    assert s['velocity_smoother']['max_velocity'][0] == 3.0
    assert s['velocity_smoother']['min_velocity'][0] == pytest.approx(-REVERSE)


def test_who_may_reverse():
    # Gazebo and the bench: yes. The car: no, until the team decides.
    assert sent_to_navigation(SIM)['reversing'] == 'true'
    assert sent_to_navigation(SIM, reversing='false')['reversing'] == 'false'
    assert sent_to_navigation(SIM, sim_speed='3')['max_speed'] == '3'
    assert sent_to_navigation(BENCH)['reversing'] == 'true'
    assert sent_to_navigation(CAR, machine='all')['reversing'] == 'false'
    assert sent_to_navigation(CAR, machine='all', reversing='true')['reversing'] == 'true'
