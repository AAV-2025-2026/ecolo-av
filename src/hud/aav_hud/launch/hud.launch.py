"""
The HUD's back end, for the touchscreen app (hud/flutter_pi).

  ros2 launch aav_hud hud.launch.py
  ros2 launch aav_hud hud.launch.py gps:=/gps/fix    # raw GPS: no localization running

Then start the app: it connects to 127.0.0.1:5000. Parameters: config/hud_server.yaml.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'gps', default_value='/gps/filtered',
            description='Where the car on the map comes from: /gps/filtered or /gps/fix'),
        Node(
            package='aav_hud',
            executable='hud_server',
            name='hud_server',
            parameters=[
                PathJoinSubstitution([FindPackageShare('aav_hud'), 'config', 'hud_server.yaml']),
                {'use_sim_time': LaunchConfiguration('use_sim_time')},
            ],
            remappings=[('/gps/filtered', LaunchConfiguration('gps'))],
        ),
    ])
