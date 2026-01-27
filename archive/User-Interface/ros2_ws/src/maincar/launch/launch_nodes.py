from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='maincar',
            executable='ui_mock_publish',
            namespace='ui_mock_publish_1',
        ),
        Node(
            package='maincar',
            executable='ui_flask',
            namespace='ui_flask_1',
        ),
    ])
