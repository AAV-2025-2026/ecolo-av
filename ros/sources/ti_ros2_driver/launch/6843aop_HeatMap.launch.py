from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_path('ti_ros2_driver')
    return LaunchDescription([
        Node(
            package='ti_ros2_driver',
            namespace='ti_radar_0',
            executable='pcl_pub',
            parameters=[
                {'cfg_path': str(share / 'cfg/RADheatmap.cfg')},  # cfg file for the radar
                # The udev names (tools/udev/99-aav.rules). Without the rules, find the
                # ports with `ls -l /dev/serial/by-id`.
                {'command_port': '/dev/aav/radar_cmd'},
                {'data_port': '/dev/aav/radar_data'},
                {'frame_id': 'radar_link'},  # frame id of published topic
                {'topic': 'ti_mmwave_0'},  # published topic name
                {'output_RD_heatmap': True},  # output the Range-Doppler heat map
                {'output_RA_heatmap': True},  # output the Range-Azimuth heat map
                {'debug_mode': False},  # debug mode
                # In debug mode, where the debug log goes
                {'debug_log_path': str(share / 'debug/result_1.json')},
            ],
            output='screen',
            emulate_tty=True,
        ),
    ])
