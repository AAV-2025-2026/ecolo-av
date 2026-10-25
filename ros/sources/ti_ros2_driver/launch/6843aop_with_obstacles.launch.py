from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    cfg_dir = get_package_share_path('ti_ros2_driver') / 'cfg'
    return LaunchDescription(
        [
            Node(
                package='ti_ros2_driver',
                namespace='ti_radar_0',
                executable='pcl_pub',
                parameters=[
                    {'cfg_path': str(cfg_dir / 'base.cfg')},
                    {'command_port': '/dev/aav/radar_cmd'},
                    {'data_port': '/dev/aav/radar_data'},
                    {'frame_id': 'radar_link'},
                    {'topic': 'ti_mmwave_0'},
                    {'roi': '-0.5_0.5; 0.2_10.0; -0.2_1.0'},
                    {'publish_target_tracker': False},
                    {'output_RD_heatmap': False},
                    {'output_RA_heatmap': False},
                    {'debug_mode': False},
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
        ]
    )
