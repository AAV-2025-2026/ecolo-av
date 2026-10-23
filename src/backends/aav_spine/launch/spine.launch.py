"""
The real car on the CAN spine: ros2_socketcan + spine_bridge.

  ros2 launch aav_spine spine.launch.py [interface:=can0] [bridge:=rust|python]

  /control/car/actuator_cmd (the output mux), /safety/estop ──> spine_bridge ──> /can/tx
      ──> socket_can_sender ──> can0
  can0 ──> socket_can_receiver ──> /can/rx ──> spine_bridge ──> /vehicle/odom,
                                                                    /vehicle/status,
                                                                    /vehicle/joint_states
  Service /spine/arm (std_srvs/SetBool): the spine ignores DRIVE_CMD until armed.

bridge picks spine_bridge's language: rust (aav_spine_bridge, the default) or python (this
package's). The same node either way, with this package's config/spine.yaml.

Bring the interface up first (once per boot, on the Orin):
  sudo ip link set can0 up type can bitrate 500000
The frame layouts are firmware/can/aav.dbc.
"""

from aav_description import vehicle
from aav_spine import bridges
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def bridge(context):
    """spine_bridge, in the language bridge:= picks."""
    v = vehicle.load()['vehicle']
    return [Node(
        package=bridges.package(LaunchConfiguration('bridge').perform(context)),
        executable=bridges.EXECUTABLE,
        name='spine_bridge',
        parameters=[
            PathJoinSubstitution([FindPackageShare('aav_spine'), 'config', 'spine.yaml']),
            vehicle.spine_params(v),
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
        ],
    )]


def generate_launch_description():
    socketcan = FindPackageShare('ros2_socketcan')
    interface = LaunchConfiguration('interface')
    return LaunchDescription([
        DeclareLaunchArgument('interface', default_value='can0'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('bridge', default_value=bridges.DEFAULT,
                              description='spine_bridge in rust or python'),
        # Lifecycle nodes; these launch files configure and activate them. Their topics
        # (from_can_bus, to_can_bus) move to /can/rx and /can/tx through the launch files'
        # own *_topic arguments.
        IncludeLaunchDescription(
            PathJoinSubstitution([socketcan, 'launch', 'socket_can_receiver.launch.py']),
            launch_arguments={'interface': interface, 'from_can_bus_topic': '/can/rx'}.items()),
        IncludeLaunchDescription(
            PathJoinSubstitution([socketcan, 'launch', 'socket_can_sender.launch.py']),
            launch_arguments={'interface': interface, 'to_can_bus_topic': '/can/tx'}.items()),
        OpaqueFunction(function=bridge),
    ])
