"""
The command mux: every /drivers/<driver>/cmd_vel in, one /control/cmd_vel out (to ego).

  ros2 launch aav_mux mux.launch.py [use_sim_time:=true]

See config/twist_mux.yaml for the inputs and their priorities.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('aav_mux'), 'config', 'twist_mux.yaml'])
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            parameters=[config, {'use_sim_time': LaunchConfiguration('use_sim_time')}],
            remappings=[('cmd_vel_out', '/control/cmd_vel')],
        ),
    ])
