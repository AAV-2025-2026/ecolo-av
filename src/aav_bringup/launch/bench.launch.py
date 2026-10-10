"""
Bench mode: the real car's software on one computer, with stand-ins for the hardware.

  ros2 launch aav_bringup bench.launch.py [nav:=true] [teleop:=false] [rviz:=false]
      [perception:=false] [arm:=true] [foxglove:=false]
  pixi run bench                            (the same)
  pixi run -e ml bench perception:=true     (adds YOLO and the stop-sign watcher)

Above the hardware, everything is the car's own: spine_bridge and its CAN frames, the
EKFs with GPS, twist_mux, ego, the drivers and Nav2. Below it, stand-ins, on the same
topics and frames as the real devices:

  spine_sim                 the spine board and actuators: the firmware's own logic
                            (spine-core) on the CAN frames, driving a model car
  mock_imu, mock_gps,       the sensors, reading where the model car really is
  mock_battery, mock_camera
  mock_radar                pretend radar points, clustered by aav_object_detection

The model car starts at the map origin (the GPS datum), facing east. A stop sign stands
25 m ahead on the right (aav_bench/config/bench.yaml). arm:=true arms the spine after
12 s, once Nav2 is up, the way `ros2 service call /spine/arm std_srvs/srv/SetBool
"{data: true}"` does. Arming earlier, while everything starts, risks a gap in commands that
latches the spine again: its 200 ms watchdog doing its job.
"""

import os

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription,
                            OpaqueFunction, TimerAction)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import yaml


def share(package):
    return FindPackageShare(package).find(package)


def include(package, launch_file, **args):
    return IncludeLaunchDescription(
        os.path.join(share(package), 'launch', launch_file),
        launch_arguments={k: str(v) for k, v in args.items()}.items())


def launch_setup(context):
    flag = {n: LaunchConfiguration(n).perform(context).lower() == 'true'
            for n in ('nav', 'teleop', 'rviz', 'perception', 'arm', 'foxglove')}
    v = vehicle.load()['vehicle']
    bench_config = os.path.join(share('aav_bench'), 'config', 'bench.yaml')
    with open(os.path.join(share('aav_localization'), 'config', 'navsat.yaml')) as f:
        datum = yaml.safe_load(f)['navsat_transform']['ros__parameters']['datum']

    actions = [
        # The car's own software, as car.launch.py starts it.
        include('aav_description', 'description.launch.py'),
        include('aav_mux', 'mux.launch.py'),
        include('aav_ego', 'ego.launch.py'),
        include('aav_scripted', 'scripted.launch.py'),
        Node(package='imu_filter_madgwick', executable='imu_filter_madgwick_node',
             name='imu_filter_madgwick',
             parameters=[os.path.join(share('aav_sensors'), 'config', 'imu_filter.yaml')],
             remappings=[('imu/data_raw', '/imu/data_raw'), ('imu/data', '/imu/data'),
                         ('imu/mag', '/imu/mag')]),
        include('aav_localization', 'localization.launch.py', gps='true'),
        Node(package='aav_spine', executable='spine_bridge', name='spine_bridge',
             parameters=[os.path.join(share('aav_spine'), 'config', 'spine.yaml'),
                         vehicle.spine_params(v)]),

        # The stand-ins for the hardware.
        Node(package='aav_spine_sim', executable='spine_sim', name='spine_sim',
             parameters=[{'wheelbase': float(v['wheelbase']),
                          'max_steering': float(v['max_steering_angle'])}]),
        Node(package='aav_bench', executable='mock_imu', name='mock_imu',
             parameters=[bench_config]),
        Node(package='aav_bench', executable='mock_gps', name='mock_gps',
             parameters=[bench_config, {'datum': [float(d) for d in datum]}]),
        Node(package='aav_bench', executable='mock_battery', name='mock_battery',
             parameters=[bench_config]),
        Node(package='aav_bench', executable='mock_camera', name='mock_camera',
             parameters=[bench_config]),
        include('aav_object_detection', 'radar_clusters.launch.py', mock='true',
                minimum_points='5'),
    ]
    if flag['nav']:
        actions.append(include('aav_navigation', 'navigation.launch.py',
                               map=os.path.join(share('aav_navigation'), 'maps', 'empty.yaml')))
    if flag['teleop']:
        actions.append(include('aav_teleop', 'teleop.launch.py'))
    if flag['perception']:
        actions += [
            include('aav_yolo', 'detector.launch.py', labels='stop sign'),
            Node(package='aav_yolo', executable='stop_sign_watcher', name='stop_sign_watcher'),
        ]
    if flag['foxglove']:
        actions.append(Node(package='foxglove_bridge', executable='foxglove_bridge',
                            name='foxglove_bridge', parameters=[{'port': 8765}]))
    if flag['rviz']:
        actions.append(Node(
            package='rviz2', executable='rviz2', name='rviz2',
            arguments=['-d', os.path.join(share('aav_bringup'), 'rviz', 'drive.rviz')]))
    if flag['arm']:
        actions.append(TimerAction(period=12.0, actions=[ExecuteProcess(
            name='arm_spine', output='screen',
            cmd=['ros2', 'service', 'call', '/spine/arm', 'std_srvs/srv/SetBool',
                 '{data: true}'])]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('nav', default_value='true', description='Nav2'),
        DeclareLaunchArgument('teleop', default_value='false',
                              description='true if a joystick is plugged into this computer'),
        DeclareLaunchArgument('rviz', default_value='false'),
        DeclareLaunchArgument('perception', default_value='false',
                              description='YOLO and the stop-sign watcher (the ml environment)'),
        DeclareLaunchArgument('arm', default_value='true',
                              description='arm the spine after 12 s'),
        DeclareLaunchArgument('foxglove', default_value='false',
                              description='foxglove_bridge on port 8765'),
        OpaqueFunction(function=launch_setup),
    ])
