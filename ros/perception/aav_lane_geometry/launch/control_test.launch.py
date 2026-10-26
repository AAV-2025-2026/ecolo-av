from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    mode = LaunchConfiguration('mode')
    invert_offset_sign = LaunchConfiguration('invert_offset_sign')
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='straight'),
        DeclareLaunchArgument('invert_offset_sign', default_value='true'),
        Node(
            package='aav_lane_geometry',
            executable='control_interface.py',
            name='control_interface',
            prefix='python3',
            output='screen',
            parameters=[{'invert_offset_sign': invert_offset_sign}],
        ),
        Node(
            package='aav_lane_geometry',
            executable='fake_lane_geometry_pub.py',
            name='fake_lane_geometry_pub',
            prefix='python3',
            output='screen',
            parameters=[{'mode': mode}],
        ),
    ])
