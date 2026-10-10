"""turtlesim as the car: the quickest whole-loop test, on any laptop.

  ros2 launch aav_turtlesim turtlesim.launch.py

  /ego/actuator_cmd ──> turtlesim_adapter ──> /turtle1/cmd_vel ──> turtlesim
  /turtle1/pose ──> turtlesim_adapter ──> /vehicle/odom

The turtle steers like the car (same wheelbase, bicycle model). Its world is
11 x 11 units (metres here) and the car's turning circle is almost 6 m across,
so drive slowly.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from aav_description import vehicle


def generate_launch_description():
    v = vehicle.load()['vehicle']
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(package='turtlesim', executable='turtlesim_node', name='turtlesim',
             parameters=[use_sim_time]),
        Node(package='aav_turtlesim', executable='turtlesim_adapter', name='turtlesim_adapter',
             parameters=[{'wheelbase': float(v['wheelbase'])}, use_sim_time]),
    ])
