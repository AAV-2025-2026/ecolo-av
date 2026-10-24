from launch import LaunchDescription
from launch_ros.actions import Node



def generate_launch_description():
    return LaunchDescription([
        Node(
            package='ti_ros2_driver',
            executable='mock_radar_publisher',
            name='mock_radar_publisher',
            parameters=[
                {'topic': '/ti_radar_0/ti_mmwave_0'},
                {'frame_id': 'radar_link'},
                {'publish_rate_hz': 10.0},
                {'mode': 'moving'},
            ],
            output='screen',
            emulate_tty=True,
        ),
        Node(
            package='ti_ros2_driver',
            executable='obstacle_extractor',
            name='radar_obstacle_extractor',
            parameters=[
                {'input_topic': '/ti_radar_0/ti_mmwave_0'},
                {'output_topic': '/ti_radar_0/ti_mmwave_0_objects'},
                {'nav_output_topic': '/navigation_objects'},
                {'frame_id': 'radar_link'},
                {'cluster_tolerance': 0.75},
                {'z_tolerance': 0.75},
                {'min_cluster_size': 1},
                {'max_distance': 20.0},
                {'min_distance': 0.05},
                {'min_height': -1.0},
                {'max_height': 2.5},
            ],
            output='screen',
            emulate_tty=True,
        ),
    ])
