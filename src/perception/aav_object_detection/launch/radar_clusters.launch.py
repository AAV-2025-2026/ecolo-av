"""
Radar clustering: DBSCAN groups the radar's points into objects, with a box round each.

  ros2 launch aav_object_detection radar_clusters.launch.py              # the real radar
  ros2 launch aav_object_detection radar_clusters.launch.py mock:=true   # pretend points
  (pixi run radar-demo is the second one, with RViz.)

Subscribes  /sensors/radar/points          sensor_msgs/PointCloud2 (aav_sensors starts the radar)
Publishes   /perception/radar/clusters        sensor_msgs/PointCloud2: the clustered points, coloured
            /perception/radar/cluster_boxes   visualization_msgs/MarkerArray: a box round each cluster

You can set: mock (pretend radar points, from ti_ros2_driver's mock_radar_publisher),
eps (metres: points this close join a cluster), minimum_points (the smallest cluster),
radar_rviz.
"""

from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    arg = LaunchConfiguration
    rviz = get_package_share_path('aav_object_detection') / 'rviz/mmwave_single_frame_dbscan.rviz'
    return LaunchDescription([
        DeclareLaunchArgument('mock', default_value='false'),
        DeclareLaunchArgument('eps', default_value='0.8'),
        DeclareLaunchArgument('minimum_points', default_value='15'),
        DeclareLaunchArgument('radar_rviz', default_value='false',
                              description='RViz with the 2025-26 radar layout'),
        Node(
            package='ti_ros2_driver', executable='mock_radar_publisher', name='mock_radar',
            parameters=[{'topic': '/sensors/radar/points', 'frame_id': 'radar_link', 'mode': 'static'}],
            condition=IfCondition(arg('mock')),
        ),
        Node(
            package='aav_object_detection', executable='dbscan', name='radar_clusters',
            parameters=[{
                'eps': ParameterValue(arg('eps'), value_type=float),
                'minimum_points': ParameterValue(arg('minimum_points'), value_type=int),
                'bounding_boxes': True,
                'target_frame': 'radar_link',
                'name_box': 'radar_clusters',
            }],
            remappings=[('/ti_mmwave/radar_scan_pcl', '/sensors/radar/points'),
                        ('dbscan_output', '/perception/radar/clusters'),
                        ('dbscan_box', '/perception/radar/cluster_boxes')],
            output='screen',
        ),
        Node(package='rviz2', executable='rviz2', arguments=['-d', str(rviz)],
             condition=IfCondition(arg('radar_rviz'))),
    ])
