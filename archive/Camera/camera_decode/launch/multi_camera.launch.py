from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory('camera_decode'),
        'config',
        'cameras.yaml'
    )
    
    return LaunchDescription([
        Node(
            package='camera_decode',
            executable='camera_decoder_node',
            name='camera_decode_node_cam1',
            parameters=[config_file],
            output='screen'
        # )
        ),
        Node(
            package='camera_decode',
            executable='camera_decoder_node',
            name='camera_decode_node_cam2',
            parameters=[config_file],
            output='screen'
        )
    ])
