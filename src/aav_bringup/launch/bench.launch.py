"""
Bench mode: the real car's software on one computer, with stand-ins for the hardware.

  ros2 launch aav_bringup bench.launch.py [nav:=true] [teleop:=false] [rviz:=false]
      [perception:=false] [lane:=false|true|fake] [hud:=false] [arm:=true] [foxglove:=false]
      [start_y:=0.0] [start_yaw:=0.0] [bend_radius:=]
  pixi run bench                            (the same)
  pixi run -e ml bench perception:=true     (adds YOLO and the stop-sign watcher)
  pixi run bench lane:=true start_y:=0.3    (lane keeping, from 0.3 m left of the centre)

Above the hardware, everything is the car's own: spine_bridge and its CAN frames, the
EKFs with GPS, twist_mux, ego, the drivers and Nav2. Below it, stand-ins, on the same
topics and frames as the real devices:

  spine_sim                 the spine board and actuators: the firmware's own logic
                            (spine-core) on the CAN frames, driving a model car
  mock_imu, mock_gps,       the sensors, reading where the model car really is
  mock_battery, mock_camera
  mock_radar                pretend radar points, clustered by aav_object_detection

The model car starts at the map origin (the GPS datum), facing east, on the centre line
of a straight road; start_y and start_yaw move it. A stop sign stands 25 m ahead on the
right (aav_bench/config/bench.yaml). lane:=true runs lane keeping: lane_finder reads the
pretend camera, control_interface steers on /cmd_vel/ai. lane:=fake feeds control_interface
a pretend straight lane instead. arm:=true arms the spine after
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
            for n in ('nav', 'teleop', 'rviz', 'perception', 'hud', 'arm', 'foxglove')}
    lane = LaunchConfiguration('lane').perform(context).lower()
    if lane not in ('false', 'true', 'fake'):
        raise ValueError(f'lane:={lane}: use true (the lane finder), fake or false')
    start = {n: float(LaunchConfiguration(n).perform(context)) for n in ('start_y', 'start_yaw')}
    bend = LaunchConfiguration('bend_radius').perform(context)
    road = [{'bend_radius': float(bend)}] if bend else []
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
                          'max_steering': float(v['max_steering_angle']), **start}]),
        Node(package='aav_bench', executable='mock_imu', name='mock_imu',
             parameters=[bench_config]),
        Node(package='aav_bench', executable='mock_gps', name='mock_gps',
             parameters=[bench_config, {'datum': [float(d) for d in datum]}]),
        Node(package='aav_bench', executable='mock_battery', name='mock_battery',
             parameters=[bench_config]),
        Node(package='aav_bench', executable='mock_camera', name='mock_camera',
             parameters=[bench_config] + road),
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
    if lane in ('true', 'fake'):
        actions.append(include('aav_lane_geometry', 'lane_follower.launch.py',
                               fake=str(lane == 'fake').lower()))
    if lane == 'true':
        actions.append(include('aav_lane_finder', 'lane_finder.launch.py'))
    if flag['hud']:
        actions.append(include('aav_hud', 'hud.launch.py'))
    if flag['foxglove']:
        actions.append(Node(package='foxglove_bridge', executable='foxglove_bridge',
                            name='foxglove_bridge', parameters=[{'port': 8765}]))
    if flag['rviz']:
        actions.append(Node(
            package='rviz2', executable='rviz2', name='rviz2',
            arguments=['-d', os.path.join(share('aav_bringup'), 'rviz', 'bench.rviz')]))
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
        DeclareLaunchArgument('lane', default_value='false',
                              description='true: lane keeping (lane_finder and control_interface, '
                                          'on /cmd_vel/ai); fake: the same on a pretend lane'),
        DeclareLaunchArgument('hud', default_value='false',
                              description="the HUD's web server (aav_hud), on 127.0.0.1:5000"),
        DeclareLaunchArgument('arm', default_value='true',
                              description='arm the spine after 12 s'),
        DeclareLaunchArgument('foxglove', default_value='false',
                              description='foxglove_bridge on port 8765'),
        DeclareLaunchArgument('start_y', default_value='0.0',
                              description="m: start the car this far left of the road's centre"),
        DeclareLaunchArgument('start_yaw', default_value='0.0',
                              description='rad: start the car turned this far left of the road '
                                          '(the EKFs still start facing east)'),
        DeclareLaunchArgument('bend_radius', default_value='',
                              description='m: bend the bench road from 30 m on, + left, - right '
                                          '(empty: bench.yaml, straight)'),
        OpaqueFunction(function=launch_setup),
    ])
