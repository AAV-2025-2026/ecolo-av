from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory('camera_decode'),
        'config',
        'cameras.yaml'
    )

    return LaunchDescription([
        # Declare args 
        DeclareLaunchArgument('show_window', default_value='false',
                              description='Show YOLO detection window'),

        # Camera decoder nodes
        Node(
            package='camera_decode',
            executable='camera_decoder_node',
            name='camera_decode_node_cam1',
            parameters=[config_file],
            output='screen'
        ),
        Node(
            package='camera_decode',
            executable='camera_decoder_node',
            name='camera_decode_node_cam2',
            parameters=[config_file],
            output='screen'
        ),

        # Stop sign detector node
        Node(
            package='camera_decode',
            executable='stop_sign_node',
            name='stop_sign_node',
            parameters=[
                config_file,
                {'show_window': LaunchConfiguration('show_window')}
            ],
            output='screen'
        ),
    ])
