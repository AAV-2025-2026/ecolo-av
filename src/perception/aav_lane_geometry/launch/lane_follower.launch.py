"""
Lane keeping (2025-26): the steering half, as a driver on twist_mux's AI slot.

  ros2 launch aav_lane_geometry lane_follower.launch.py [fake:=false]

  /lane_geometry (LaneGeometry) -> control_interface -> /cmd_vel/ai (TwistStamped, priority 10)

The half that finds the lane lines in the camera picture is aav_lane_finder's
lane_finder.launch.py: it publishes /lane_geometry. fake:=true runs the 2025-26 team's
fake_lane_geometry_pub instead (a pretend straight lane, no camera). Every other driver
outranks /cmd_vel/ai, so a person, a test script or Nav2 always wins.

The scripts run through python3, not their `#!/usr/bin/env python3` line: on a Mac,
/usr/bin/env drops the library path that their messages need (docs/mac.md).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('fake', default_value='false',
                              description='a pretend straight lane on /lane_geometry'),
        Node(package='aav_lane_geometry', executable='control_interface.py',
             name='control_interface', prefix='python3', output='screen'),
        Node(package='aav_lane_geometry', executable='fake_lane_geometry_pub.py',
             name='fake_lane_geometry_pub', prefix='python3',
             condition=IfCondition(LaunchConfiguration('fake'))),
    ])
