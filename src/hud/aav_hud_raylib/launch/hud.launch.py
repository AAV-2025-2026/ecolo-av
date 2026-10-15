"""
The in-car screen in Rust (aav_hud_raylib): one window, which is also the ROS node `hud`.

  ros2 launch aav_hud_raylib hud.launch.py
  ros2 launch aav_hud_raylib hud.launch.py fullscreen:=true

Topic names: config/hud.yaml, the one place they're written. It needs a screen: on a
computer without one, it fails.
Not in car.launch.py yet: the Flutter app (aav_hud) stays until this one matches it.
To add it there later, include this file under the machine with the screen.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def hud_node(fullscreen, condition):
    """Make the node, with or without --fullscreen (an argument, not a ROS parameter)."""
    return Node(
        package='aav_hud_raylib',
        executable='hud',
        name='hud',
        arguments=['--fullscreen'] if fullscreen else [],
        parameters=[
            PathJoinSubstitution([FindPackageShare('aav_hud_raylib'), 'config', 'hud.yaml']),
        ],
        output='screen',
        condition=condition,
    )


def generate_launch_description():
    fullscreen = LaunchConfiguration('fullscreen')
    return LaunchDescription([
        DeclareLaunchArgument('fullscreen', default_value='false',
                              description='Fill the screen (F11 switches too)'),
        hud_node(True, IfCondition(fullscreen)),
        hud_node(False, UnlessCondition(fullscreen)),
    ])
