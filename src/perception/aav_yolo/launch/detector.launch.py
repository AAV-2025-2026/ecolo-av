"""
The YOLO detector, on the camera's images.

  pixi run detect                                    # the stock model, on /camera/image_raw
  pixi run detect picture:=src/perception/aav_yolo/test/stop_sign.jpg   # a test picture
  pixi run detect model:=models/best.pt labels:="stop sign"

What you can set:
  model       the model file (.pt, .mlpackage or .engine). Default: models/yolo11n.pt
  device      auto (the GPU if there is one), cpu, mps or cuda:0
  confidence  the lowest score kept, 0 to 1
  labels      the labels to keep, comma-separated; empty keeps them all
  image       the camera topic to read
  picture     an image or video file, published as the camera (image_publisher), for tests

The detector runs as `python3 -m aav_yolo.detector`: the python3 of the environment that
started the launch, so the ml environment's PyTorch is the one it finds.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

ROOT = os.environ.get('PIXI_PROJECT_ROOT', os.getcwd())


def generate_launch_description():
    arg = LaunchConfiguration
    picture = PythonExpression(["'", arg('picture'), "' != ''"])
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value=os.path.join(ROOT, 'models', 'yolo11n.pt')),
        DeclareLaunchArgument('device', default_value='auto'),
        DeclareLaunchArgument('confidence', default_value='0.5'),
        DeclareLaunchArgument('labels', default_value=''),
        DeclareLaunchArgument('image', default_value='/camera/image_raw'),
        DeclareLaunchArgument('picture', default_value=''),
        Node(
            package='image_publisher', executable='image_publisher_node', name='test_camera',
            parameters=[{'filename': arg('picture'), 'publish_rate': 10.0,
                         'frame_id': 'camera_left_link'}],
            remappings=[('image_raw', arg('image')), ('camera_info', '/camera/camera_info')],
            condition=IfCondition(picture),
        ),
        ExecuteProcess(
            name='yolo_detector', output='screen', emulate_tty=True,
            cmd=['python3', '-m', 'aav_yolo.detector', '--ros-args',
                 '-p', ['model:=', arg('model')],
                 '-p', ['device:=', arg('device')],
                 '-p', ['confidence:=', arg('confidence')],
                 '-p', ['labels:="', arg('labels'), '"'],
                 '-r', ['image:=', arg('image')],
                 '-r', 'detections:=/perception/detections',
                 '-r', 'detections/image:=/perception/detections/image'],
        ),
    ])
