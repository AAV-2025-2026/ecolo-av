from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')
    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value='share/aav_uart_bridge/config/bridge_params.yaml',
            description='Path to bridge parameter YAML file',
        ),
        Node(
            package='aav_uart_bridge',
            executable='ackermann_uart_bridge',
            name='aav_uart_bridge',
            output='screen',
            parameters=[params_file],
        ),
    ])
