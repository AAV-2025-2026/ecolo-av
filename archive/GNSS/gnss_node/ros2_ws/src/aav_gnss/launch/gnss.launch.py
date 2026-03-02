import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # 1. Declare Launch Arguments
    email_arg = DeclareLaunchArgument(
        'email',
        default_value='your_email@example.com',
        description='Email for rtk2go authentication'
    )

    mount_arg = DeclareLaunchArgument(
        'mountpoint',
        default_value='CanalTerris',
        description='RTK Mountpoint'
    )

    # 2. Assign Launch Configurations
    email = LaunchConfiguration('email')
    mountpoint = LaunchConfiguration('mountpoint')

    return LaunchDescription([
        email_arg,
        mount_arg,

        # Start the RTK Stream Manager
        ExecuteProcess(
            cmd=[[
                "trap 'kill $! 2>/dev/null; exit' INT TERM EXIT; ",

                # Start the infinite reconnect loop
                "while true; do ",
                "if ping -c 1 -W 2 8.8.8.8 > /dev/null; then ",
                "str2str -in ntrip://", email, ":none@rtk2go.com:2101/", mountpoint, " -out tcpsvr://:4000 & ",
                "wait $!; ",
                "fi; ",
                "sleep 5 & wait $!; ",
                "done"
            ]],
            output='screen',
            name='rtk_manager',
            shell=True
        ),

        # Start the GNSS Python Node
        Node(
            package='aav_gnss',
            executable='gnss_node',
            name='gnss_node',
            output='screen',
            parameters=[
                {'port': '/dev/zed_f9r'},
                {'baud': 115200},
                {'frame_id': 'gps'},
                {'rtk_port': 4000}
            ]
        )
    ])
