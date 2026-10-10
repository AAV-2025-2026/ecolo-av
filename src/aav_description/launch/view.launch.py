"""
Look at the car model and its frames in RViz, with sliders for the joints.

  ros2 launch aav_description view.launch.py

Edit config/vehicle.yaml, rebuild (colcon build --packages-select aav_description,
or use --symlink-install), and relaunch to see the change. Each sensor shows as
an orange box with its axes; red is x (forward), green y (left), blue z (up).
"""

from launch import LaunchDescription
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('aav_description')
    robot_description = ParameterValue(
        Command(['xacro ', PathJoinSubstitution([share, 'urdf', 'aav.urdf.xacro'])]),
        value_type=str)
    return LaunchDescription([
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description}]),
        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui'),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', PathJoinSubstitution([share, 'rviz', 'view.rviz'])]),
    ])
