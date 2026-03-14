from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='maincar',
            namespace='ui',
            executable='ui_flask',
            name='flask_node'
        ),
        Node(
            package='maincar',
            namespace='ui',
            executable='ui_mock_publish',
            name='mock_data_publishing_node'
        )
    ])
