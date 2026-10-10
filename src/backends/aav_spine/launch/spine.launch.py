"""The real car on the CAN spine: ros2_socketcan + spine_bridge.

  ros2 launch aav_spine spine.launch.py [interface:=can0]

  /ego/actuator_cmd, /estop ──> spine_bridge ──> /to_can_bus ──> socket_can_sender ──> can0
  can0 ──> socket_can_receiver ──> /from_can_bus ──> spine_bridge ──> /vehicle/odom,
                                                                    /vehicle/status,
                                                                    /vehicle/joint_states
  Service /spine/arm (std_srvs/SetBool): the spine ignores DRIVE_CMD until armed.

Bring the interface up first (once per boot, on the Orin):
  sudo ip link set can0 up type can bitrate 500000
The frame layouts are firmware/can/aav.dbc.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from aav_description import vehicle


def generate_launch_description():
    socketcan = FindPackageShare('ros2_socketcan')
    interface = LaunchConfiguration('interface')
    v = vehicle.load()['vehicle']
    return LaunchDescription([
        DeclareLaunchArgument('interface', default_value='can0'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        # Lifecycle nodes; these launch files configure and activate them.
        IncludeLaunchDescription(
            PathJoinSubstitution([socketcan, 'launch', 'socket_can_receiver.launch.py']),
            launch_arguments={'interface': interface}.items()),
        IncludeLaunchDescription(
            PathJoinSubstitution([socketcan, 'launch', 'socket_can_sender.launch.py']),
            launch_arguments={'interface': interface}.items()),
        Node(
            package='aav_spine',
            executable='spine_bridge',
            name='spine_bridge',
            parameters=[
                PathJoinSubstitution([FindPackageShare('aav_spine'), 'config', 'spine.yaml']),
                vehicle.spine_params(v),
                {'use_sim_time': LaunchConfiguration('use_sim_time')},
            ],
        ),
    ])
