"""Gazebo Harmonic as the car: world, the car from the URDF, the bridge and the adapter.

  ros2 launch aav_gazebo gazebo.launch.py [world:=empty|test_lot] [gui:=true]

  /ego/actuator_cmd ──> gazebo_adapter ──> /gazebo/cmd_vel ──bridge──> Ackermann system
  Gazebo odometry, IMU, NavSat ──bridge──> gazebo_adapter ──> /vehicle/odom,
                                           /imu/data_raw, /gps/fix, /vehicle/status
  Gazebo joints ──bridge──> /joint_states;  Gazebo clock ──bridge──> /clock

Everything else (sensors filter, localization, Nav2, mux, ego) runs as on the car,
with use_sim_time:=true. aav_bringup sim.launch.py starts the lot.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

from aav_description import vehicle


def generate_launch_description():
    share = FindPackageShare('aav_gazebo')
    world = PathJoinSubstitution([share, 'worlds', [LaunchConfiguration('world'), '.sdf']])
    # -r: start running; -s: server only (no GUI window)
    gz_args = [PythonExpression(["'-r' if '", LaunchConfiguration('gui'), "' == 'true' else '-r -s'"]),
               ' ', world]
    v = vehicle.load()['vehicle']
    sim_time = {'use_sim_time': True}
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='empty', description='empty or test_lot'),
        DeclareLaunchArgument('gui', default_value='true'),
        IncludeLaunchDescription(
            PathJoinSubstitution([FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py']),
            launch_arguments={'gz_args': gz_args, 'on_exit_shutdown': 'true'}.items()),
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
