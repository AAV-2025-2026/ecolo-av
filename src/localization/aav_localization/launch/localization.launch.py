"""Localization: the local EKF feeds the global EKF; GPS comes in through navsat_transform.

  ros2 launch aav_localization localization.launch.py [gps:=true]
      [start_x:=0.0] [start_y:=0.0] [start_yaw:=0.0] [use_sim_time:=false]

  /vehicle/odom, /imu/data ──> ekf_local ──> /odometry/local, TF odom -> base_link
  /vehicle/odom, /imu/data, /odometry/gps ──> ekf_global ──> /odometry/global, TF map -> odom
  /gps/fix, /odometry/global ──> navsat_transform ──> /odometry/gps, /gps/filtered

start_x, start_y, start_yaw: where the car is when this starts, in the map frame
(metres east and north of the datum, yaw in radians counter-clockwise from east).
Park on the marked start spot and these are its numbers.

Without GPS (gps:=false: the bench, indoors, phase 0-1) only ekf_local runs and a
static map -> odom identity stands in, so map-frame tools still work.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def ekf_services(node_name):
    # Both EKFs create set_pose, enable, reset and toggle with relative names; give each
    # its own so they don't collide on /set_pose.
    return [(s, f'{node_name}/{s}') for s in ('set_pose', 'enable', 'reset', 'toggle')]


def global_ekf(context):
    x, y, yaw = (float(LaunchConfiguration(n).perform(context))
                 for n in ('start_x', 'start_y', 'start_yaw'))
    config = PathJoinSubstitution([FindPackageShare('aav_localization'), 'config'])
    initial_state = [x, y, 0.0, 0.0, 0.0, yaw] + [0.0] * 9
    return [Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_global',
        parameters=[PathJoinSubstitution([config, 'ekf_global.yaml']),
                    {'initial_state': initial_state,
                     'use_sim_time': LaunchConfiguration('use_sim_time')}],
        remappings=[('odometry/filtered', '/odometry/global')] + ekf_services('ekf_global'),
        condition=IfCondition(LaunchConfiguration('gps')),
    )]


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('aav_localization'), 'config'])
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}
    return LaunchDescription([
        DeclareLaunchArgument('gps', default_value='true'),
        DeclareLaunchArgument('start_x', default_value='0.0'),
        DeclareLaunchArgument('start_y', default_value='0.0'),
        DeclareLaunchArgument('start_yaw', default_value='0.0'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),

        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_local',
            parameters=[PathJoinSubstitution([config, 'ekf_local.yaml']), use_sim_time],
            remappings=[('odometry/filtered', '/odometry/local')] + ekf_services('ekf_local'),
        ),
        OpaqueFunction(function=global_ekf),
        Node(
            package='robot_localization',
            executable='navsat_transform_node',
            name='navsat_transform',
            parameters=[PathJoinSubstitution([config, 'navsat.yaml']), use_sim_time],
            remappings=[('imu', '/imu/data'),
                        ('gps/fix', '/gps/fix'),
                        ('gps/filtered', '/gps/filtered'),
                        ('odometry/gps', '/odometry/gps'),
                        ('odometry/filtered', '/odometry/global')],
            condition=IfCondition(LaunchConfiguration('gps')),
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='map_to_odom_no_gps',
            arguments=['--frame-id', 'map', '--child-frame-id', 'odom'],
            parameters=[use_sim_time],
            condition=UnlessCondition(LaunchConfiguration('gps')),
        ),
    ])
