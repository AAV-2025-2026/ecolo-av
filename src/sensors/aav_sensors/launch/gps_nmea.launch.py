"""
Any GPS that speaks NMEA over serial, as /gps/fix: the fallback until the GPS is chosen (Q18).

  ros2 launch aav_sensors gps_nmea.launch.py [port:=/dev/aav/gps] [baud:=9600]

  nmea_navsat_driver -> /gps/fix (NavSatFix), frame gps_link

Most receivers send NMEA by default, u-blox ones too (9600 baud on a u-blox M8's UART,
38400 on an F9P's). sensors.launch.py's gps part starts this with gps_driver:=nmea; its
default is ublox_gps, for a u-blox (gps_driver:=ublox). Both run anywhere, Pixi too.
Untested with a receiver.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('port', default_value='/dev/aav/gps'),
        DeclareLaunchArgument('baud', default_value='9600'),
        Node(
            package='nmea_navsat_driver', executable='nmea_serial_driver', name='gps_nmea',
            parameters=[{
                'port': LaunchConfiguration('port'),
                'baud': ParameterValue(LaunchConfiguration('baud'), value_type=int),
                'frame_id': 'gps_link',
                'time_ref_source': 'gps',
                'useRMC': False,          # GGA: it carries the fix quality
            }],
            remappings=[('fix', '/gps/fix'), ('vel', '/gps/vel'),
                        ('time_reference', '/gps/time_reference')],
        ),
    ])
