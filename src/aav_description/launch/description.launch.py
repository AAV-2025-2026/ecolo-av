"""Publish the car's frames: robot_state_publisher from the URDF.

  ros2 launch aav_description description.launch.py [sim:=true] [use_sim_time:=true]

joint_state_publisher fills in the joints nobody measures (wheel spin) and merges
the measured steering angles that aav_spine publishes on /vehicle/joint_states.
In Gazebo, the simulator publishes /joint_states itself, so turn it off there.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    sim = LaunchConfiguration('sim')
    use_sim_time = LaunchConfiguration('use_sim_time')
    xacro_file = PathJoinSubstitution(
        [FindPackageShare('aav_description'), 'urdf', 'aav.urdf.xacro'])
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' sim:=', sim]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='false',
                              description='Add the Gazebo plugins to the URDF'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('joint_state_publisher', default_value='true',
                              description='Publish joints nobody else publishes'),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description,
                         'use_sim_time': use_sim_time}],
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            parameters=[{'source_list': ['vehicle/joint_states'],
                         'use_sim_time': use_sim_time}],
            condition=IfCondition(LaunchConfiguration('joint_state_publisher')),
        ),
    ])
