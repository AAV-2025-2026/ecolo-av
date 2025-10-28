from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='camera_streamer_pkg',
            executable='camera_receiver',
            name='camera_receiver',
            output='screen'
        )
    ])
