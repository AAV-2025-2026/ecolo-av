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
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import yaml

with open(os.path.join(get_package_share_directory('aav_ego'), 'config', 'ego.yaml')) as f:
    CONFIG_MAX_SPEED = float(yaml.safe_load(f)['ego']['ros__parameters']['max_speed'])


def ego_node(context):
    v = vehicle.load()['vehicle']
    params = [
        PathJoinSubstitution([FindPackageShare('aav_ego'), 'config', 'ego.yaml']),
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
    return [Node(package='aav_ego', executable='ego', name='ego', parameters=params)]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('max_speed', default_value='',
                              description="m/s: a lower forward speed cap than ego.yaml's"),
        OpaqueFunction(function=ego_node),
    ])
