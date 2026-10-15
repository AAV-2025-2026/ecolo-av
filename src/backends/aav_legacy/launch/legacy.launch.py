"""
Today's car (2025-26 hardware) as a backend, until the CAN spine exists.

  ros2 launch aav_legacy legacy.launch.py [uart:=true] [encoder:=true]

  /ego/actuator_cmd, /safety/estop ──> legacy_uart_bridge ──> 13-byte frames ──> ESP32
  Pico 2 wheel encoder ──UDP:10111──> encoder_udp ──> /vehicle/odom (speed only)

Run legacy_uart_bridge on the Pi wired to the ESP32's UART, encoder_udp anywhere
on the car's network. READ docs/firmware.md first: the ESP32 firmware has no
command timeout, so if this bridge dies the last throttle stays on.
"""

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('aav_legacy'), 'config', 'legacy.yaml'])
    v = vehicle.load()['vehicle']
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}
    return LaunchDescription([
        DeclareLaunchArgument('uart', default_value='true'),
        DeclareLaunchArgument('encoder', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='aav_legacy',
            executable='legacy_uart_bridge',
            name='legacy_uart_bridge',
            parameters=[config, {'max_steering_angle': float(v['max_steering_angle'])},
                        use_sim_time],
            condition=IfCondition(LaunchConfiguration('uart')),
        ),
        Node(
            package='aav_legacy',
            executable='encoder_udp',
            name='encoder_udp',
            parameters=[config, {'wheel_diameter': float(v['wheel_diameter']),
                                 'counts_per_rev': int(v['encoder_counts_per_rev'])},
                        use_sim_time],
            condition=IfCondition(LaunchConfiguration('encoder')),
        ),
    ])
