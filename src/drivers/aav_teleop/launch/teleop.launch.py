"""
Joystick driver: /drivers/joy/joy -> /drivers/joy/cmd_vel, and an e-stop button.

The command is TwistStamped; the button publishes /safety/estop true.

  ros2 launch aav_teleop teleop.launch.py [estop_button:=true] [use_sim_time:=false]

The joystick is a driver like any other: it publishes a velocity command into
twist_mux and never talks to the wheels. Run it on the machine the USB receiver is
plugged into (any machine on the same ROS_DOMAIN_ID).

All three nodes run in the namespace /drivers/joy, so their relative topics land there:
joy_node's joy is /drivers/joy/joy, teleop_twist_joy's cmd_vel is /drivers/joy/cmd_vel.
Their config files name the nodes as /**/<node>, so they match in any namespace.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('aav_teleop'), 'config'])
    use_sim_time = {'use_sim_time': LaunchConfiguration('use_sim_time')}
    return LaunchDescription([
        DeclareLaunchArgument('estop_button', default_value='true',
                              description='Also map a button to /safety/estop (joy_teleop)'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            namespace='/drivers/joy',
            parameters=[PathJoinSubstitution([config, 'joy.yaml']), use_sim_time],
        ),
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='teleop_twist_joy_node',
            namespace='/drivers/joy',
            parameters=[PathJoinSubstitution([config, 'teleop_twist_joy.yaml']), use_sim_time],
        ),
        Node(
            package='joy_teleop',
            executable='joy_teleop',
            name='joy_teleop',
            namespace='/drivers/joy',
            parameters=[PathJoinSubstitution([config, 'estop_button.yaml']), use_sim_time],
            condition=IfCondition(LaunchConfiguration('estop_button')),
        ),
    ])
