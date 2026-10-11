"""
ego: /cmd_vel (TwistStamped from twist_mux) -> /ego/actuator_cmd (AckermannDriveStamped).

  ros2 launch aav_ego ego.launch.py [use_sim_time:=false]

The wheelbase, the steering limit and the reverse speed come from
aav_description/config/vehicle.yaml; the other limits from config/ego.yaml.
"""

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    v = vehicle.load()['vehicle']
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='aav_ego',
            executable='ego',
            name='ego',
            parameters=[
                PathJoinSubstitution([FindPackageShare('aav_ego'), 'config', 'ego.yaml']),
                vehicle.ego_params(v),
                {'use_sim_time': LaunchConfiguration('use_sim_time')},
            ],
        ),
    ])
