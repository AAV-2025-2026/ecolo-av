"""CARLA as the car (stub, never run): adapter plus topic remaps to our sensor names.

  ros2 launch aav_carla carla.launch.py [role_name:=ego_vehicle]

Expects a CARLA server and a ROS 2 bridge publishing carla/<role>/... topics (the
2024-25 team's carla_ros_bridge names). No official bridge supports Jazzy yet; see
docs/simulation.md. Use Gazebo (aav_gazebo) this year.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    role = LaunchConfiguration('role_name')
    return LaunchDescription([
        DeclareLaunchArgument('role_name', default_value='ego_vehicle'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(
            package='aav_carla',
            executable='carla_adapter',
            name='carla_adapter',
            parameters=[{'role_name': role,
                         'use_sim_time': LaunchConfiguration('use_sim_time')}],
        ),
        # CARLA's sensors -> our sensor topics, through topic_tools relay (no copying code).
        Node(package='topic_tools', executable='relay', name='carla_imu_relay',
             arguments=[['/carla/', role, '/imu'], '/imu/data_raw']),
        Node(package='topic_tools', executable='relay', name='carla_gnss_relay',
             arguments=[['/carla/', role, '/gnss'], '/gps/fix']),
    ])
