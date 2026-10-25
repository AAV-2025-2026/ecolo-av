from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    default_control = os.path.join(get_package_share_directory('aav_speed_control'), 'config', 'control_params.yaml')
    default_bridge = os.path.join(get_package_share_directory('aav_uart_bridge'), 'config', 'bridge_params.yaml')

    control_params = LaunchConfiguration('control_params')
    bridge_params = LaunchConfiguration('bridge_params')

    return LaunchDescription([
        DeclareLaunchArgument('control_params', default_value=default_control),
        DeclareLaunchArgument('bridge_params', default_value=default_bridge),
        Node(
            package='aav_speed_control',
            executable='wheel_encoder_udp',
            name='wheel_encoder_udp',
            output='screen',
            parameters=[control_params],
        ),
        Node(
            package='aav_speed_control',
            executable='speed_estimator',
            name='speed_estimator',
            output='screen',
            parameters=[control_params],
        ),
        Node(
            package='aav_speed_control',
            executable='speed_pid',
            name='speed_pid',
            output='screen',
            parameters=[control_params],
        ),
        Node(
            package='aav_uart_bridge',
            executable='ackermann_uart_bridge',
            name='aav_uart_bridge',
            output='screen',
            parameters=[bridge_params],
        ),
    ])
