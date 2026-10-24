#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for LiDAR processing system."""
    
    # Get config file path
    config = os.path.join(
        get_package_share_directory('lidar_processing'),
        'config',
        'lidar_params.yaml'
    )
    
    # LiDAR subscriber node
    lidar_subscriber_node = Node(
        package='lidar_processing',
        executable='lidar_subscriber',
        name='lidar_subscriber',
        parameters=[config],
        output='screen'
    )
    
    return LaunchDescription([
        lidar_subscriber_node
    ])
