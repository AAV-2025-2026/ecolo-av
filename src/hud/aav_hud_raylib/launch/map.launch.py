"""
The big screen's map window (aav_hud_raylib): one window, which is also the ROS node `map`.

  ros2 launch aav_hud_raylib map.launch.py
  ros2 launch aav_hud_raylib map.launch.py fullscreen:=true

Nav2's map, the car on it, the plan and the goal, and the distance left. Topic names:
config/map.yaml, the one place they're written. The car's size: aav_description's
vehicle.yaml. It needs a screen: on a computer without one, it fails.
Keys: F follow the car / whole map, + - or the mouse wheel zoom, drag to move.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def map_node(fullscreen, condition):
    """Make the node, with or without --fullscreen (an argument, not a ROS parameter)."""
    vehicle = PathJoinSubstitution(
        [FindPackageShare('aav_description'), 'config', 'vehicle.yaml'])
    return Node(
        package='aav_hud_raylib',
        executable='map',
        name='map',
        arguments=['--vehicle', vehicle] + (['--fullscreen'] if fullscreen else []),
        parameters=[
            PathJoinSubstitution([FindPackageShare('aav_hud_raylib'), 'config', 'map.yaml']),
        ],
        output='screen',
        condition=condition,
    )


def generate_launch_description():
    fullscreen = LaunchConfiguration('fullscreen')
    return LaunchDescription([
        DeclareLaunchArgument('fullscreen', default_value='false',
                              description='Fill the screen (F11 switches too)'),
        map_node(True, IfCondition(fullscreen)),
        map_node(False, UnlessCondition(fullscreen)),
    ])
