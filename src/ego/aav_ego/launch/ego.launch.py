"""
ego: /control/cmd_vel (TwistStamped from twist_mux) -> /ego/actuator_cmd (AckermannDriveStamped).

  ros2 launch aav_ego ego.launch.py [use_sim_time:=false] [max_speed:=0.3]

max_speed (m/s) caps the forward speed below config/ego.yaml's, for a first drive on
stands; empty (the default) keeps ego.yaml's. It can only lower the cap, never raise it.

Wheelbase and steering limit come from aav_description/config/vehicle.yaml; the
speed and rate limits from config/ego.yaml.
"""

import os

from aav_description import vehicle
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import yaml

with open(os.path.join(get_package_share_directory('aav_ego'), 'config', 'ego.yaml')) as f:
    CONFIG = yaml.safe_load(f)['ego']['ros__parameters']
CONFIG_MAX_SPEED = float(CONFIG['max_speed'])
SIM_MAX_SPEED = 5.0  # m/s: sim_max_speed's ceiling, about 18 km/h


def ego_node(context):
    v = vehicle.load()['vehicle']
    params = [
        # ego.yaml as a dict, not the file: the file names the node (ego:), and a named
        # entry beats the later caps below whenever the launch also sets a global
        # parameter (sim.launch.py's use_sim_time). As dicts, the last one wins.
        dict(CONFIG),
        vehicle.ego_params(v),
        {'use_sim_time': LaunchConfiguration('use_sim_time')},
    ]
    cap = context.launch_configurations.get('max_speed', '').strip()
    if cap:
        limit = float(cap)
        if not 0.0 < limit <= CONFIG_MAX_SPEED:
            raise ValueError(f'max_speed:={cap} must be above 0 and at most '
                             f'{CONFIG_MAX_SPEED} m/s (config/ego.yaml)')
        params.append({'max_speed': limit})
    sim = context.launch_configurations.get('sim_max_speed', '').strip()
    if sim:
        # Above ego.yaml's cap, so only ever in a simulator: refused on wall-clock time.
        if LaunchConfiguration('use_sim_time').perform(context).lower() != 'true':
            raise ValueError('sim_max_speed:= is for simulators only (use_sim_time:=true)')
        limit = float(sim)
        if not 0.0 < limit <= SIM_MAX_SPEED:
            raise ValueError(f'sim_max_speed:={sim} must be above 0 and at most '
                             f'{SIM_MAX_SPEED} m/s')
        params.append({'max_speed': limit})
    return [Node(package='aav_ego', executable='ego', name='ego', parameters=params)]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('max_speed', default_value='',
                              description="m/s: a lower forward speed cap than ego.yaml's"),
        DeclareLaunchArgument('sim_max_speed', default_value='',
                              description='m/s: a higher cap, in a simulator only '
                                          '(sim.launch.py sim_speed:=)'),
        OpaqueFunction(function=ego_node),
    ])
