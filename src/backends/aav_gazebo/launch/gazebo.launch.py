"""
Gazebo Harmonic as the car: world, the car from the URDF, the bridge and the adapter.

  ros2 launch aav_gazebo gazebo.launch.py [world:=empty|test_lot] [gui:=true] [follow:=true]

  /ego/actuator_cmd ──> gazebo_adapter ──> /gazebo/cmd_vel ──bridge──> Ackermann system
  Gazebo odometry, IMU, NavSat ──bridge──> gazebo_adapter ──> /vehicle/odom,
                                           /sensors/imu/data_raw, /sensors/gps/fix, /vehicle/status
  Gazebo joints ──bridge──> /joint_states;  Gazebo clock ──bridge──> /clock

Everything else (sensors filter, localization, Nav2, mux, ego) runs as on the car,
with use_sim_time:=true. aav_bringup sim.launch.py starts the lot.

On a Mac, Gazebo's window can't run in the same program as the simulator, so it starts
as a second program here: `pixi run sim` works the same on a Mac and on Linux.
follow:=true points the window's camera at the car once the window is up.
"""

import sys

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import (AndSubstitution, LaunchConfiguration, PathJoinSubstitution,
                                  PythonExpression)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

MAC = sys.platform == 'darwin'

# Point the window's camera at the car, close behind it and to its right. Wait for the
# car to appear first: asked too early, the camera ends up looking at nothing. Then keep
# asking until the window answers (it takes a few seconds to start).
CAR = '"aav"'
FOLLOW = ('for i in $(seq 1 60); do gz model --list 2> /dev/null | grep -q -- "- aav$" && '
          'break; sleep 1; done; '
          'for i in $(seq 1 30); do '
          'gz service -s /gui/follow --reqtype gz.msgs.StringMsg --reptype gz.msgs.Boolean '
          f"--timeout 2000 --req 'data: {CAR}' > /dev/null 2>&1 && "
          'gz service -s /gui/follow/offset --reqtype gz.msgs.Vector3d '
          "--reptype gz.msgs.Boolean --timeout 2000 --req 'x: -3.5, y: -2.5, z: 1.8' "
          '> /dev/null 2>&1 && exit 0; sleep 1; done')


def generate_launch_description():
    share = FindPackageShare('aav_gazebo')
    world = PathJoinSubstitution([share, 'worlds', [LaunchConfiguration('world'), '.sdf']])
    gui = LaunchConfiguration('gui')
    # -r: start running; -s: server only (no window). On a Mac the window is always its
    # own program (below).
    gz_args = ['-r -s ', world] if MAC else [
        PythonExpression(["'-r' if '", gui, "' == 'true' else '-r -s'"]), ' ', world]
    window = [ExecuteProcess(cmd=['gz', 'sim', '-g'], name='gz_window', output='screen',
                             condition=IfCondition(gui))] if MAC else []
    v = vehicle.load()['vehicle']
    sim_time = {'use_sim_time': True}
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='empty', description='empty or test_lot'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('follow', default_value='true',
                              description="point the window's camera at the car"),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py']),
            launch_arguments={'gz_args': gz_args, 'on_exit_shutdown': 'true'}.items()),
        *window,
        ExecuteProcess(cmd=[FOLLOW], shell=True, name='follow_car',
                       condition=IfCondition(AndSubstitution(gui, LaunchConfiguration('follow')))),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('aav_description'), 'launch',
                                  'description.launch.py']),
            launch_arguments={'sim': 'true', 'use_sim_time': 'true',
                              'joint_state_publisher': 'false'}.items()),
        Node(package='ros_gz_sim', executable='create', name='spawn_aav', output='screen',
             arguments=['-topic', 'robot_description', '-name', 'aav', '-z', '0.05']),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='gz_bridge',
             parameters=[{'config_file': PathJoinSubstitution([share, 'config', 'bridge.yaml'])},
                         sim_time]),
        Node(package='aav_gazebo', executable='gazebo_adapter', name='gazebo_adapter',
             parameters=[{'wheelbase': float(v['wheelbase'])}, sim_time]),
    ])
