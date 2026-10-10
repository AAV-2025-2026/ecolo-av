"""
The whole stack in Gazebo: same nodes and configs as the car, simulated hardware.

  ros2 launch aav_bringup sim.launch.py [world:=empty|test_lot] [nav:=true]
      [teleop:=false] [gui:=true] [rviz:=true]

world:=empty pairs with the empty map (phase 2); world:=test_lot with
maps/example_lot.yaml (phase 3), chosen automatically. The car starts at the world
origin facing east, which is also the map origin (the datum).
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

MAPS = {'empty': 'empty.yaml', 'test_lot': 'example_lot.yaml'}


def include(context, package, launch_file, **args):
    share = FindPackageShare(package).perform(context)
    return IncludeLaunchDescription(
        os.path.join(share, 'launch', launch_file),
        launch_arguments={k: str(v) for k, v in args.items()}.items())


def launch_setup(context):
    world = LaunchConfiguration('world').perform(context)
    flag = {n: LaunchConfiguration(n).perform(context).lower() == 'true'
            for n in ('nav', 'teleop', 'rviz')}
    nav_share = FindPackageShare('aav_navigation').perform(context)
    actions = [
        include(context, 'aav_gazebo', 'gazebo.launch.py', world=world,
                gui=LaunchConfiguration('gui').perform(context)),
        include(context, 'aav_mux', 'mux.launch.py', use_sim_time='true'),
        include(context, 'aav_ego', 'ego.launch.py', use_sim_time='true'),
        include(context, 'aav_scripted', 'scripted.launch.py', use_sim_time='true'),
        # Only the IMU filter: Gazebo stands in for the drivers.
        Node(package='imu_filter_madgwick', executable='imu_filter_madgwick_node',
             name='imu_filter_madgwick',
             parameters=[os.path.join(FindPackageShare('aav_sensors').perform(context),
                                      'config', 'imu_filter.yaml'), {'use_sim_time': True}],
             remappings=[('imu/data_raw', '/imu/data_raw'), ('imu/data', '/imu/data')]),
        include(context, 'aav_localization', 'localization.launch.py', use_sim_time='true'),
    ]
    if flag['nav']:
        actions.append(include(context, 'aav_navigation', 'navigation.launch.py',
                               use_sim_time='true',
                               map=os.path.join(nav_share, 'maps', MAPS[world])))
    if flag['teleop']:
        actions.append(include(context, 'aav_teleop', 'teleop.launch.py', use_sim_time='true'))
    if flag['rviz']:
        actions.append(Node(
            package='rviz2', executable='rviz2', name='rviz2',
            arguments=['-d', os.path.join(FindPackageShare('aav_bringup').perform(context),
                                          'rviz', 'drive.rviz')],
            parameters=[{'use_sim_time': True}]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='empty', description='empty or test_lot'),
        DeclareLaunchArgument('nav', default_value='true'),
        DeclareLaunchArgument('teleop', default_value='false',
                              description='true if a joystick is plugged into this computer'),
        DeclareLaunchArgument('gui', default_value='true', description='Gazebo window'),
        DeclareLaunchArgument('rviz', default_value='true'),
        OpaqueFunction(function=launch_setup),
    ])
