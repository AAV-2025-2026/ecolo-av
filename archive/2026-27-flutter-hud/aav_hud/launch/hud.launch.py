"""
The HUD's back end, for the touchscreen app (hud/flutter_pi).

  ros2 launch aav_hud hud.launch.py
  ros2 launch aav_hud hud.launch.py gps_topic:=/sensors/gps/fix    # raw GPS: no localization
  ros2 launch aav_hud hud.launch.py hud_port:=5123         # another port (a Mac's AirPlay)

Then start the app: it connects to 127.0.0.1:5000 (tools/flutter.sh run
--dart-define=HUD_BACKEND=http://127.0.0.1:5123 for another port). Parameters:
config/hud_server.yaml. The camera, in a browser on the same computer:
http://127.0.0.1:5000/camera/stream

The arguments start with hud_ because included launch files share their arguments:
bench.launch.py hud:=true and sim.launch.py hud_web:=true include this file, and a GPS launch
file has a `port`.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'gps_topic', default_value='/localization/gps/fix',
            description='Where the car on the map comes from: /localization/gps/fix or '
                        '/sensors/gps/fix'),
        DeclareLaunchArgument(
            'hud_host', default_value='127.0.0.1',
            description='Who may connect: 127.0.0.1 = this computer only, 0.0.0.0 = any'),
        DeclareLaunchArgument('hud_port', default_value='5000',
                              description="The back end's port"),
        Node(
            package='aav_hud',
            executable='hud_server',
            name='hud_server',
            parameters=[
                PathJoinSubstitution([FindPackageShare('aav_hud'), 'config', 'hud_server.yaml']),
                {'use_sim_time': LaunchConfiguration('use_sim_time'),
                 'host': ParameterValue(LaunchConfiguration('hud_host'), value_type=str),
                 'port': ParameterValue(LaunchConfiguration('hud_port'), value_type=int)},
            ],
            remappings=[('/localization/gps/fix', LaunchConfiguration('gps_topic'))],
        ),
    ])
