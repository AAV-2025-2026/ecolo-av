"""
The sensor mux and the output mux: where the data comes from, and where the commands go.

  ros2 launch aav_io_mux io_mux.launch.py target:=car|gazebo|bench|turtle|carla
      [source:=real|sim|bench|replay]

  target   who plays the car: the output mux sends ego's commands to
           /control/<target>/actuator_cmd. Empty: no output mux (a replay drives nothing)
  source   where the sensor data must come from; empty: the target's own (car: real;
           gazebo, turtle, carla: sim; bench: bench). A source the target can't take is
           refused here: the real car only ever runs on real data

Every profile launch file includes this with its own target (turtle, sim, bench, car,
carla), so `pixi run sim` and the rest start both muxes as before.
"""

from aav_io_mux.provenance import choose
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context):
    target, source = choose(LaunchConfiguration('target').perform(context).strip(),
                            LaunchConfiguration('source').perform(context).strip())
    actions = [Node(package='aav_io_mux', executable='sensor_mux', name='sensor_mux',
                    parameters=[{'source': source}])]
    if target:
        actions.append(Node(package='aav_io_mux', executable='output_mux', name='output_mux',
                            parameters=[{'target': target}]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('target', default_value='',
                              description='car, gazebo, bench, turtle or carla: who plays the '
                                          'car (empty: no output mux)'),
        DeclareLaunchArgument('source', default_value='',
                              description="real, sim, bench or replay (empty: the target's)"),
        OpaqueFunction(function=launch_setup),
    ])
