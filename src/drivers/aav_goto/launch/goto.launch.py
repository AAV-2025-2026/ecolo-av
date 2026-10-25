"""
The goto driver: an action server (/goto) that drives to one point and stops there.

  ros2 launch aav_goto goto.launch.py [use_sim_time:=false] [watchdog:=true]
  pixi run goto --sim --ahead 20          (the client: aav_goto goto_cli)

The braking (actuators max_brake), the wheelbase and the steering limit come from
aav_description/config/vehicle.yaml; the rest from config/goto.yaml. watchdog:=false where
no sensor watchdog runs (sim.launch.py watchdog:=false): it then doesn't wait for its lock.
"""

import os

from aav_description import vehicle
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import yaml


def goto_params(cfg):
    """Return the goto driver's numbers from the whole of vehicle.yaml."""
    v = cfg['vehicle']
    return {'max_brake': float(cfg['actuators']['max_brake']),
            'wheelbase': float(v['wheelbase']),
            'max_steering_angle': float(v['max_steering_angle'])}


def launch_setup(context):
    with open(os.path.join(get_package_share_directory('aav_goto'), 'config',
                           'goto.yaml')) as f:
        config = yaml.safe_load(f)['goto_driver']['ros__parameters']
    watchdog = LaunchConfiguration('watchdog').perform(context).lower()
    if watchdog not in ('true', 'false'):
        raise ValueError(f'watchdog:={watchdog}: use true or false')
    if watchdog == 'false':
        config['watchdog_timeout'] = 0.0
    return [Node(
        package='aav_goto',
        executable='goto_driver',
        name='goto_driver',
        # goto.yaml as a dict, not the file: a named entry in a file beats a global
        # parameter set later (sim.launch.py's use_sim_time), as in ego.launch.py.
        parameters=[dict(config), goto_params(vehicle.load()),
                    {'use_sim_time': LaunchConfiguration('use_sim_time')}],
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('watchdog', default_value='true',
                              description="false where no sensor watchdog runs: don't wait "
                                          'for its lock'),
        OpaqueFunction(function=launch_setup),
    ])
