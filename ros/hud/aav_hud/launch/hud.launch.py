"""
The in-car screen in Rust (aav_hud): one window, which is also the ROS node `hud`.

  ros2 launch aav_hud hud.launch.py
  ros2 launch aav_hud hud.launch.py fullscreen:=true
  ros2 launch aav_hud hud.launch.py fullscreen:=true monitor:=HDMI-1

monitor: the screen it opens on, by name (as xrandr says) or number (0 = the first);
empty = wherever the desktop puts it. `ros2 run aav_hud hud --list-monitors`
lists them. On the car, tools/car_screen.sh starts it at boot (docs/car-screens.md).

Topic names: config/hud.yaml, the one place they're written. It needs a screen: on a
computer without one, it fails.
Not in car.launch.py: the screens start on their own (aav-hud.service).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def hud_node(context):
    """Make the node; --fullscreen and --monitor are arguments, not ROS parameters."""
    arguments = []
    if IfCondition(LaunchConfiguration('fullscreen')).evaluate(context):
        arguments.append('--fullscreen')
    monitor = LaunchConfiguration('monitor').perform(context).strip()
    if monitor:
        arguments += ['--monitor', monitor]
    return [Node(
        package='aav_hud',
        executable='hud',
        name='hud',
        arguments=arguments,
        parameters=[
            PathJoinSubstitution([FindPackageShare('aav_hud'), 'config', 'hud.yaml']),
        ],
        output='screen',
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('fullscreen', default_value='false',
                              description='Fill the screen (F11 switches too)'),
        DeclareLaunchArgument('monitor', default_value='',
                              description='The monitor, by name (HDMI-1) or number (0); '
                                          'empty: wherever the desktop puts it'),
        OpaqueFunction(function=hud_node),
    ])
