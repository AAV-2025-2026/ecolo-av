"""
The sensor watchdog: stops Nav2 and the AI slot when a sensor they need dies or lies.

  ros2 launch aav_safety watchdog.launch.py inputs:=odom,imu,gps,local,global
      [use_sim_time:=false]

inputs: the names in config/sensor_watchdog.yaml to watch, comma-separated; each profile
passes the sensors it has (sim.launch.py, bench.launch.py, car.launch.py with Nav2).
twist_mux's sensors lock (aav_mux config/twist_mux.yaml) reads its
/safety/sensor_watchdog/lock. docs/simulation.md ("Sensor failures on purpose").
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def watchdog(context):
    names = [n.strip() for n in LaunchConfiguration('inputs').perform(context).split(',')
             if n.strip()]
    config = FindPackageShare('aav_safety').perform(context) + '/config/sensor_watchdog.yaml'
    sim_time = LaunchConfiguration('use_sim_time').perform(context).lower() == 'true'
    # inputs isn't in the file, so this dict adds it rather than losing to the file.
    return [Node(package='aav_safety', executable='sensor_watchdog', name='sensor_watchdog',
                 output='screen',
                 parameters=[config, {'inputs': names, 'use_sim_time': sim_time}])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('inputs', default_value='odom,imu,gps,local,global',
                              description='which of config/sensor_watchdog.yaml to watch'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        OpaqueFunction(function=watchdog),
    ])
