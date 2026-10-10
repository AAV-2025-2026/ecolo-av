"""
The real car. One launch file for every machine; a machine file picks the parts.

  ros2 launch aav_bringup car.launch.py machine:=orin
      [gps:=true] [map:=<map yaml>] [start_x:=0] [start_y:=0] [start_yaw:=0]

machine: config/machines/<machine>.yaml lists which parts run on that computer
(orin, motor_pi, laptop, all). Every machine uses the same ROS_DOMAIN_ID, so the
parts find each other over the network; see docs/platforms.md.

Parts and what they start:
  description     robot_state_publisher (+ joint_state_publisher): the car's frames
  mux, ego        twist_mux -> /cmd_vel -> ego -> /ego/actuator_cmd
  teleop          joystick -> /cmd_vel/joy, e-stop button -> /estop
  scripted        /scripted_drive action -> /cmd_vel/scripted
  imu, gps,       sensor drivers (on the machine the device is plugged into)
  radar, battery
  localization    ekf_local, ekf_global, navsat_transform
  navigation      Nav2 -> /cmd_vel/nav
  spine           backend: CAN spine (ros2_socketcan + spine_bridge)
  legacy_uart     backend: today's ESP32 over UART (the Pi wired to it)
  legacy_encoder  today's wheel encoder over UDP
  foxglove        foxglove_bridge on port 8765, for Foxglove Studio on a laptop
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import yaml

PARTS = ('description', 'mux', 'ego', 'teleop', 'scripted', 'imu', 'gps', 'radar', 'battery',
         'localization', 'navigation', 'spine', 'legacy_uart', 'legacy_encoder', 'foxglove')


def include(context, package, launch_file, **args):
    share = FindPackageShare(package).perform(context)
    return IncludeLaunchDescription(
        os.path.join(share, 'launch', launch_file),
        launch_arguments={k: str(v).lower() if isinstance(v, bool) else str(v)
                          for k, v in args.items()}.items())


def launch_setup(context):
    machine = LaunchConfiguration('machine').perform(context)
    share = FindPackageShare('aav_bringup').perform(context)
    with open(os.path.join(share, 'config', 'machines', f'{machine}.yaml')) as f:
        parts = yaml.safe_load(f)['parts']
    unknown = set(parts) - set(PARTS)
    if unknown:
        raise RuntimeError(f'{machine}.yaml: unknown parts {sorted(unknown)}')

    def on(name):
        return bool(parts.get(name, False))

    def arg(name):
        return LaunchConfiguration(name).perform(context)

    actions = []
    if on('description'):
        actions.append(include(context, 'aav_description', 'description.launch.py'))
    if on('mux'):
        actions.append(include(context, 'aav_mux', 'mux.launch.py'))
    if on('ego'):
        actions.append(include(context, 'aav_ego', 'ego.launch.py'))
    if on('teleop'):
        actions.append(include(context, 'aav_teleop', 'teleop.launch.py'))
    if on('scripted'):
        actions.append(include(context, 'aav_scripted', 'scripted.launch.py'))
    if any(on(s) for s in ('imu', 'gps', 'radar', 'battery')):
        actions.append(include(context, 'aav_sensors', 'sensors.launch.py',
                               imu=on('imu'), gps=on('gps'), radar=on('radar'),
                               battery=on('battery')))
    if on('localization'):
        actions.append(include(context, 'aav_localization', 'localization.launch.py',
                               gps=arg('gps'), start_x=arg('start_x'), start_y=arg('start_y'),
                               start_yaw=arg('start_yaw')))
    if on('navigation'):
        nav_args = {'map': arg('map')} if arg('map') else {}
        actions.append(include(context, 'aav_navigation', 'navigation.launch.py', **nav_args))
    if on('spine'):
        actions.append(include(context, 'aav_spine', 'spine.launch.py'))
    if on('legacy_uart') or on('legacy_encoder'):
        actions.append(include(context, 'aav_legacy', 'legacy.launch.py',
                               uart=on('legacy_uart'), encoder=on('legacy_encoder')))
    if on('foxglove'):
        actions.append(Node(package='foxglove_bridge', executable='foxglove_bridge',
                            name='foxglove_bridge', parameters=[{'port': 8765}]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('machine', default_value='all',
                              description='config/machines/<machine>.yaml'),
        DeclareLaunchArgument('gps', default_value='true',
                              description='false: no GPS anywhere (odometry only)'),
        DeclareLaunchArgument('map', default_value='',
                              description='Map YAML for Nav2 (default: the empty map)'),
        DeclareLaunchArgument('start_x', default_value='0.0'),
        DeclareLaunchArgument('start_y', default_value='0.0'),
        DeclareLaunchArgument('start_yaw', default_value='0.0',
                              description='Heading at start, rad counter-clockwise from east'),
        OpaqueFunction(function=launch_setup),
    ])
