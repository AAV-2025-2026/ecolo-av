#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([

        # ==============================
        # Arduino Serial → Raw CAN
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_serial_publisher',
            name='radar_serial_publisher',
            output='screen',
            parameters=[
                {'serial_port': '/dev/ttyACM0'},
                {'baud_rate': 115200}
            ]
        ),

        # ==============================
        # Delphi ESR 2.5 Decoder
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_decoder',
            name='radar_decoder',
            output='screen'
        ),

        # ==============================
        # Foxglove PointCloud
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_pointcloud',
            name='radar_pointcloud',
            output='screen'
        ),

        # ==============================
        # RViz Markers (optional)
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_markers',
            name='radar_markers',
            output='screen'
        ),

        # ==============================
        # Diagnostics (HIGHLY RECOMMENDED)
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_diagnostics',
            name='radar_diagnostics',
            output='screen'
        ),

        # ==============================
        # EKF Tracker (optional sanity check)
        # ==============================
        Node(
            package='radar_tracking_pkg',
            executable='radar_ekf_tracker',
            name='radar_ekf_tracker',
            output='screen'
        ),

        # ==============================
        # Multi-target tracker (EXPERIMENTAL)
        # Uncomment when needed
        # ==============================
        # Node(
        #     package='radar_tracking_pkg',
        #     executable='radar_multi_tracker',
        #     name='radar_multi_tracker',
        #     output='screen'
        # ),
    ])

