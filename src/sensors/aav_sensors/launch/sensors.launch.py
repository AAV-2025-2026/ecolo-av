"""
Sensor drivers: each publishes raw data in its own frame; nothing here fuses anything.

  ros2 launch aav_sensors sensors.launch.py [imu:=true] [gps:=true] [radar:=false]
                                            [battery:=false] [imu_driver:=cpp]

  IMU     imu_node -> /imu/data_raw -> imu_filter_madgwick -> /imu/data
          imu_node is yahboom_imu_cpp (C++), or with imu_driver:=rust its twin
          aav_imu_yahboom (Rust): the same node name, parameters and topics.
  GPS     ublox_dgnss (u-blox over USB) -> ublox_nav_sat_fix_hp -> /gps/fix (NavSatFix)
  radar   ti_ros2_driver pcl_pub -> /radar/points (PointCloud2, frame radar_link)
  battery battery_monitor -> /battery_status (BatteryState)

Frames (imu_link, gps_link, radar_link) come from aav_description; run its
description.launch.py too, or nothing can place these readings on the car.
Run this file on the machine the sensors are plugged into.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (AndSubstitution, EqualsSubstitution, LaunchConfiguration,
                                  PathJoinSubstitution)
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode
from launch_ros.substitutions import FindPackageShare


# u-blox receiver settings, as in ublox_dgnss's ublox_rover_hpposllh_navsatfix.launch.py
# (0.7.4) except the rate. The NavSatFix node needs HPPOSLLH, STATUS and COV.
UBLOX_PARAMS = {
    'DEVICE_FAMILY': 'F9P',             # TODO confirm the team's receiver (F9P, F9R or X20P)
    'DEVICE_SERIAL_STRING': '',         # '' = the first u-blox found on USB
    'FRAME_ID': 'gps_link',
    'CFG_USBOUTPROT_NMEA': False,
    'CFG_RATE_MEAS': 200,               # ms between measurements: 5 Hz. TODO tune
    'CFG_RATE_NAV': 1,                  # one solution per measurement
    'CFG_MSGOUT_UBX_NAV_HPPOSLLH_USB': 1,
    'CFG_MSGOUT_UBX_NAV_STATUS_USB': 1,
    'CFG_MSGOUT_UBX_NAV_COV_USB': 1,
    'CFG_MSGOUT_UBX_NAV_PVT_USB': 1,
}


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('aav_sensors'), 'config'])
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}

    def enabled(name):
        return IfCondition(LaunchConfiguration(name))

    return LaunchDescription([
        DeclareLaunchArgument('imu', default_value='true'),
        DeclareLaunchArgument('gps', default_value='true'),
        DeclareLaunchArgument('radar', default_value='false'),
        DeclareLaunchArgument('battery', default_value='false'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('imu_driver', default_value='cpp',
                              description='cpp: yahboom_imu_cpp; rust: aav_imu_yahboom'),

        # IMU: one of two drivers that take the same config/imu.yaml.
        *[Node(
            package=package,
            executable='imu_node',
            name='imu_node',
            parameters=[PathJoinSubstitution([config, 'imu.yaml']), use_sim_time],
            condition=IfCondition(AndSubstitution(
                LaunchConfiguration('imu'),
                EqualsSubstitution(LaunchConfiguration('imu_driver'), driver))),
        ) for driver, package in (('cpp', 'yahboom_imu_cpp'), ('rust', 'aav_imu_yahboom'))],
        Node(
            package='imu_filter_madgwick',
            executable='imu_filter_madgwick_node',
            name='imu_filter_madgwick',
            parameters=[PathJoinSubstitution([config, 'imu_filter.yaml']), use_sim_time],
            remappings=[('imu/data_raw', '/imu/data_raw'), ('imu/data', '/imu/data'),
                        ('imu/mag', '/imu/mag')],
            condition=enabled('imu'),
        ),

        # GPS: the driver and the NavSatFix converter, in one process.
        ComposableNodeContainer(
            name='gps_container',
            namespace='',
            package='rclcpp_components',
            executable='component_container_mt',
            composable_node_descriptions=[
                ComposableNode(
                    package='ublox_dgnss_node',
                    plugin='ublox_dgnss::UbloxDGNSSNode',
                    name='ublox_dgnss',
                    parameters=[UBLOX_PARAMS, use_sim_time],
                ),
                ComposableNode(
                    package='ublox_nav_sat_fix_hp_node',
                    plugin='ublox_nav_sat_fix_hp::UbloxNavSatHpFixNode',
                    name='ublox_nav_sat_fix_hp',
                    parameters=[use_sim_time],
                    remappings=[('fix', '/gps/fix')],
                ),
            ],
            condition=enabled('gps'),
        ),

        # Radar (perception, later): out-of-box cfg, which publishes x forward, y left.
        Node(
            package='ti_ros2_driver',
            executable='pcl_pub',
            name='radar',
            parameters=[{
                'cfg_path': PathJoinSubstitution(
                    [FindPackageShare('ti_ros2_driver'), 'cfg', 'base.cfg']),
                'command_port': '/dev/aav/radar_cmd',
                'data_port': '/dev/aav/radar_data',
                'frame_id': 'radar_link',
                'topic': '/radar/points',
            }, use_sim_time],
            condition=enabled('radar'),
        ),

        # Battery monitor (Victron VE.Direct). Its `port` parameter defaults to the udev
        # name /dev/aav/battery.
        Node(
            package='battery_monitor',
            executable='battery_monitor',
            condition=enabled('battery'),
        ),
    ])
