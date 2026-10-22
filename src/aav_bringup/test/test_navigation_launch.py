"""
aav_navigation's navigation.launch.py: reversing, sim.launch.py's faster Nav2, the ghost.

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


def test_regulated_pure_pursuit_unless_mppi_is_asked_for():
    rpp = settings()['controller_server']['FollowPath']
    assert rpp['plugin'].endswith('::RegulatedPurePursuitController')
    s = settings(controller='mppi', reversing='true', max_speed='3')
    follow = s['controller_server']['FollowPath']
    assert follow['plugin'] == 'nav2_mppi_controller::MPPIController'
    # The car's turning circle reaches MPPI's Ackermann model too, through RewrittenYaml.
    v = vehicle.load()['vehicle']
    assert follow['AckermannConstraints']['min_turning_r'] == pytest.approx(
        vehicle.min_turning_radius(v), abs=1e-3)
    assert follow['vx_min'] == pytest.approx(-REVERSE)
    assert follow['vx_max'] == 3.0
    assert follow['enforce_path_inversion'] is True
    assert s['velocity_smoother']['max_velocity'][0] == 3.0
    assert sent_to_navigation(SIM)['controller'] == 'rpp'
    assert sent_to_navigation(SIM, controller='mppi')['controller'] == 'mppi'


def test_who_may_reverse():
    # Gazebo and the bench: yes. The car: no, until the team decides.
    assert sent_to_navigation(SIM)['reversing'] == 'true'
    assert sent_to_navigation(SIM, reversing='false')['reversing'] == 'false'
    assert sent_to_navigation(SIM, sim_speed='3')['max_speed'] == '3'
    assert sent_to_navigation(BENCH)['reversing'] == 'true'
    assert sent_to_navigation(CAR, machine='all')['reversing'] == 'false'
    assert sent_to_navigation(CAR, machine='all', reversing='true')['reversing'] == 'true'


def whole_file(**args):
    """Return the whole rewritten nav2.yaml the servers load: the costmaps' keys too."""
    context = context_for(NAV, map='/maps/empty.yaml', **args)
    for a in NAV.nodes(context):
        if isinstance(a, Node) and a._Node__node_name == 'controller_server':
            for p in a._Node__parameters:
                if isinstance(p, ParameterFile):
                    with open(p.evaluate(context)) as f:
                        return yaml.safe_load(f)
    raise AssertionError('no controller_server')


def local_costmap(**args):
    return whole_file(**args)['local_costmap']['local_costmap']['ros__parameters']


def ghost_nodes(**args):
    """Return the ghost_obstacle nodes navigation.launch.py starts with these arguments."""
    context = context_for(NAV, map='/maps/empty.yaml', **args)
    return [a for a in NAV.nodes(context)
            if isinstance(a, Node) and a._Node__node_name == 'ghost_obstacle']


def test_no_ghost_unless_asked_for():
    # The radar alone, so collision_monitor runs: and reads no ghost.
    monitor = settings(radar='true')['collision_monitor']
    assert 'ghost' not in monitor['observation_sources']
    assert 'ghost_layer' not in local_costmap()['plugins']
    assert ghost_nodes() == []


def test_the_ghost_adds_its_own_layer_and_source_beside_the_real_sensors():
    s = settings(radar='true', lidar='true', ghost='true')
    assert s['collision_monitor']['observation_sources'] == ['radar', 'lidar', 'ghost']
    assert s['collision_monitor']['ghost']['topic'] == '/safety/ghost/scan'
    local = local_costmap(radar='true', lidar='true', ghost='true')
    assert local['plugins'].index('ghost_layer') < local['plugins'].index('inflation_layer')
    # Its own layer reads only the ghost: its clearing can't touch the radar's or lidar's.
    assert local['ghost_layer']['observation_sources'] == 'ghost'
    assert local['ghost_layer']['ghost']['topic'] == '/safety/ghost/scan'
    assert local['obstacle_layer']['observation_sources'] == 'radar'
    assert local['lidar_layer']['observation_sources'] == 'lidar'
    assert len(ghost_nodes(ghost='true')) == 1


def test_the_ghost_alone_brings_collision_monitor():
    context = context_for(NAV, map='/maps/empty.yaml', ghost='true')
    names = [a._Node__node_name for a in NAV.nodes(context) if isinstance(a, Node)]
    assert 'collision_monitor' in names


def test_who_may_have_a_ghost():
    # Off everywhere unless asked for; the launch argument reaches Nav2.
    assert sent_to_navigation(SIM)['ghost'] == 'false'
    sim = sent_to_navigation(SIM, ghost='true')
    assert (sim['ghost'], sim['collision_monitor']) == ('true', 'true')
    assert sent_to_navigation(CAR, machine='all')['ghost'] == 'false'
    car = sent_to_navigation(CAR, machine='all', ghost='true')
    assert (car['ghost'], car['collision_monitor']) == ('true', 'true')


def bench_lidar_parts(**args):
    """Return (the mock_lidar node's parameters, sensors.launch.py's arguments) from bench."""
    mock, sensors = None, None
    for a in BENCH.launch_setup(context_for(BENCH, **args)):
        if isinstance(a, Node) and a._Node__node_name == 'mock_lidar':
            # Normalised: each name and value is a tuple of substitutions.
            context = LaunchContext()
            mock = {perform_substitutions(context, k): v
                    for k, v in a._Node__parameters[-1].items()}
        elif isinstance(a, IncludeLaunchDescription):
            a.launch_description_source.get_launch_description(LaunchContext())
            if os.path.basename(a.launch_description_source.location) == 'sensors.launch.py':
                sensors = dict(a.launch_arguments)
    return mock, sensors


def test_the_bench_lidar_feeds_the_cars_own_driver_and_nav2():
    assert bench_lidar_parts() == (None, None)
    assert sent_to_navigation(BENCH)['lidar'] == 'false'
    mock, sensors = bench_lidar_parts(lidar='true')
    # mock_lidar sends where the stock driver listens: this computer, not the real 2368.
    assert sensors['lidar'] == 'true' and sensors['lidar_ip'] == '127.0.0.1'
    assert sensors['lidar_port'] == '2369' == str(mock['port'])
    assert sensors['imu'] == sensors['gps'] == 'false'      # the bench's mocks stand there
    assert sent_to_navigation(BENCH, lidar='true')['lidar'] == 'true'
