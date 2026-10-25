"""
street_router: street routes from an offline router, as Nav2 GPS waypoints (docs/routes.md).

  pixi run -e routes router                          # the router, in another terminal
  ros2 launch aav_routes street_router.launch.py
  ros2 topic pub --once /drivers/nav/route/destination geographic_msgs/msg/GeoPointStamped \
    "{position: {latitude: 45.3983, longitude: -75.6838}}"
  ros2 service call /drivers/nav/route/follow std_srvs/srv/Trigger     # then Nav2 drives it

For real streets later; the test lot first. Settings: config/street_router.yaml.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='aav_routes',
            executable='street_router',
            name='street_router',
            output='screen',
            parameters=[
                PathJoinSubstitution(
                    [FindPackageShare('aav_routes'), 'config', 'street_router.yaml']),
                {'use_sim_time': LaunchConfiguration('use_sim_time')},
            ],
        ),
    ])
