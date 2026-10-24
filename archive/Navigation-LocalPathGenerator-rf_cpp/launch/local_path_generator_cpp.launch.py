from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package="local_path_generator_cpp",
            executable="local_path_generator_node",
            name="local_path_generator",
            output="screen",
        )
    ])
