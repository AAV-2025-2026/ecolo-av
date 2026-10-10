"""
Scripted driver: an action server that drives a speed profile into /cmd_vel/scripted.

  ros2 launch aav_scripted scripted.launch.py
  ros2 action send_goal /scripted_drive aav_interfaces/action/ScriptedDrive \
    "{target_speed: 1.0, acceleration: 0.5, deceleration: 1.0, hold_time: 5.0}" --feedback
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='aav_scripted',
            executable='scripted_driver',
            name='scripted_driver',
            parameters=[
                PathJoinSubstitution(
                    [FindPackageShare('aav_scripted'), 'config', 'scripted.yaml']),
                {'use_sim_time': LaunchConfiguration('use_sim_time')},
            ],
        ),
    ])
