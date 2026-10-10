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
                # The cfg file for the radar: see cfg/rules.txt
                {'cfg_path': str(share / 'cfg/base.cfg')},
                # The udev names (tools/udev/99-aav.rules). Without the rules, find the
                # ports with `ls -l /dev/serial/by-id`.
                {'command_port': '/dev/aav/radar_cmd'},
                {'data_port': '/dev/aav/radar_data'},
                {'frame_id': 'radar_link'},  # frame id of published topic
                {'topic': 'ti_mmwave_0'},  # published topic name
                # Optional 3D region of interest: x -0.5..0.5, y 0.2..10.0, z -0.2..1.0.
                # Axes are separated by ";", lower and upper limits by "_".
                {'roi': '-0.5_0.5; 0.2_10.0; -0.2_1.0'},
                # Optional: publish the target tracker as compact point clouds (3d_tracking
                # binary mode only)
                {'publish_target_tracker': False},
                # Optional: output the Range-Doppler and Range-Azimuth heat maps (out-of-box
                # binary mode only)
                {'output_RD_heatmap': False},
                {'output_RA_heatmap': False},
                {'debug_mode': False},  # Optional: debug mode
                # Optional: in debug mode, where the debug log goes
                {'debug_log_path': str(share / 'debug/result.json')},
            ],
            output='screen',
            emulate_tty=True,
        ),
    ])
