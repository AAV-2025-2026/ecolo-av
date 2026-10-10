"""
Perception on the car, next to car.launch.py.

Run it on the computer the camera and the radar plug into (the Orin).

  ros2 launch aav_bringup perception.launch.py [camera:=true] [detector:=true]
      [radar_clusters:=true]

  camera          aav_sensors cameras.launch.py: usb_cam -> /camera/image_raw (Linux only)
  detector        aav_yolo: YOLO on /camera/image_raw -> /perception/detections, and the
                  stop-sign watcher -> /perception/stop (twist_mux's stop_sign lock)
  radar_clusters  aav_object_detection: DBSCAN on /radar/points (car.launch.py's radar part
                  starts the radar)

The detector needs PyTorch or TensorRT: on the Orin, JetPack's (docs/perception.md); on a
laptop, the ml environment. Bench mode starts all of this with stand-ins instead
(bench.launch.py perception:=true). When car.launch.py next changes, these become parts in
its machine files.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def include(package, launch_file, condition, **args):
    share = FindPackageShare(package).find(package)
    return IncludeLaunchDescription(
        os.path.join(share, 'launch', launch_file), condition=condition,
        launch_arguments={k: str(v) for k, v in args.items()}.items())


def generate_launch_description():
    on = LaunchConfiguration
    return LaunchDescription([
        DeclareLaunchArgument('camera', default_value='true'),
        DeclareLaunchArgument('detector', default_value='true'),
        DeclareLaunchArgument('radar_clusters', default_value='true'),
        include('aav_sensors', 'cameras.launch.py', IfCondition(on('camera'))),
        include('aav_yolo', 'detector.launch.py', IfCondition(on('detector')),
                labels='stop sign'),
        Node(package='aav_yolo', executable='stop_sign_watcher', name='stop_sign_watcher',
             condition=IfCondition(on('detector'))),
        include('aav_object_detection', 'radar_clusters.launch.py',
                IfCondition(on('radar_clusters'))),
    ])
