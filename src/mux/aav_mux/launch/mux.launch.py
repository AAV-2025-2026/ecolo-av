"""
The command mux: every /drivers/<driver>/cmd_vel in, one /control/cmd_vel out (to ego).

  ros2 launch aav_mux mux.launch.py [use_sim_time:=true] [sensor_lock:=true]

See config/twist_mux.yaml for the inputs and their priorities.

sensor_lock:=true (the default) keeps the sensors lock fail-safe: Nav2 and the AI slot are
held unless aav_safety's sensor_watchdog says "false" at least once a second. Start the
watchdog wherever this runs with it (sim, bench and car launch files do). sensor_lock:=false
is for profiles that run no watchdog (the turtle): the lock's timeout becomes 0, so a lock
that nobody publishes stays open, as before.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def mux(context):
    config = PathJoinSubstitution([FindPackageShare('aav_mux'), 'config', 'twist_mux.yaml'])
    lock = LaunchConfiguration('sensor_lock').perform(context).lower()
    if lock not in ('true', 'false'):
        raise ValueError(f'sensor_lock:={lock}: use true or false')
    # After the file, so it wins (docs/conventions.md, "A launch override that silently
    # loses").
    override = [] if lock == 'true' else [{'locks.sensors.timeout': 0.0}]
    return [Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[config, *override, {'use_sim_time': LaunchConfiguration('use_sim_time')}],
        remappings=[('cmd_vel_out', '/control/cmd_vel')],
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('sensor_lock', default_value='true',
                              description="true: Nav2 and the AI slot need sensor_watchdog's "
                                          "heartbeat; false: no watchdog runs (the turtle)"),
        OpaqueFunction(function=mux),
    ])
