"""
Re-run localization (and optionally Nav2) on a recorded drive, on any laptop.

  ros2 launch aav_bringup replay.launch.py [nav:=false] [rviz:=true]
  ros2 bag play <bag> --clock --topics /vehicle/odom /imu/data_raw /gps/fix /tf_static

The bag (tools/record.sh) supplies the raw inputs and the clock; this file runs the
same IMU filter and EKFs as the car, so a config change can be tried on yesterday's
drive. To replay a drive's COMMANDS into the car instead, see tools/replay_commands.sh.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def launch_setup(context):
    def share(p):
        return FindPackageShare(p).perform(context)

    def include(package, launch_file, **args):
        return IncludeLaunchDescription(
            os.path.join(share(package), 'launch', launch_file),
            launch_arguments={**args, 'use_sim_time': 'true'}.items())

    actions = [
        include('aav_description', 'description.launch.py'),
        Node(package='imu_filter_madgwick', executable='imu_filter_madgwick_node',
             name='imu_filter_madgwick',
             parameters=[os.path.join(share('aav_sensors'), 'config', 'imu_filter.yaml'),
                         {'use_sim_time': True}],
             remappings=[('imu/data_raw', '/imu/data_raw'), ('imu/data', '/imu/data')]),
        include('aav_localization', 'localization.launch.py'),
    ]
    if LaunchConfiguration('nav').perform(context).lower() == 'true':
        actions.append(include('aav_navigation', 'navigation.launch.py'))
    if LaunchConfiguration('rviz').perform(context).lower() == 'true':
        actions.append(Node(package='rviz2', executable='rviz2', name='rviz2',
                            arguments=['-d', os.path.join(share('aav_bringup'), 'rviz',
                                                          'drive.rviz')],
                            parameters=[{'use_sim_time': True}]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('nav', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true'),
        OpaqueFunction(function=launch_setup),
    ])
