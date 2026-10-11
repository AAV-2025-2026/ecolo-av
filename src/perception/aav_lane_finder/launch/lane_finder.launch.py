"""
The lane finder, on the front camera's pictures.

  ros2 launch aav_lane_finder lane_finder.launch.py [debug_image:=false]

  /camera/image_raw, /camera/camera_info -> lane_finder -> /lane_geometry

Lane keeping is two launch files: this one finds the lane, and aav_lane_geometry's
lane_follower.launch.py steers by it (control_interface, on /cmd_vel/ai).
bench.launch.py lane:=true starts both.

The camera's place on the car (camera_left_link) and the wheelbase come from
aav_description's vehicle.yaml; the rest from config/lane_finder.yaml.
"""

import os

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    car = vehicle.load()
    camera = car['sensors']['camera_left_link']
    share = FindPackageShare('aav_lane_finder').find('aav_lane_finder')
    return LaunchDescription([
        DeclareLaunchArgument('debug_image', default_value='false',
                              description="/lane_geometry/image: the bird's-eye view, and "
                                          'what the finder found in it'),
        Node(package='aav_lane_finder', executable='lane_finder', name='lane_finder',
             output='screen',
             parameters=[os.path.join(share, 'config', 'lane_finder.yaml'),
                         {'camera_xyz': [float(v) for v in camera['xyz']],
                          'camera_rpy': [float(v) for v in camera['rpy']],
                          'wheelbase': float(car['vehicle']['wheelbase']),
                          'debug_image': LaunchConfiguration('debug_image')}]),
    ])
