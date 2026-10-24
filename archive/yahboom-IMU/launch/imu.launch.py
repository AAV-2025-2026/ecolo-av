from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='yahboom_imu_cpp',
            executable='imu_node',
            name='imu_node',
            output='screen',
            parameters=[
                {'port': '/dev/ttyUSB0'},
                {'baud_rate': 115200},
                {'frame_id': 'imu_link'},
            ]
        )
    ])