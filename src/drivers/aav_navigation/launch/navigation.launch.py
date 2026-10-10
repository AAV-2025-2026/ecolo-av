"""
Nav2 as one more driver: goals in, /cmd_vel/nav (TwistStamped) out to twist_mux.

  ros2 launch aav_navigation navigation.launch.py [map:=<path to map yaml>]
      [collision_monitor:=false] [use_sim_time:=false] [autostart:=true]

Starts only the Nav2 servers a car needs (not nav2_bringup's full list: no AMCL, since
robot_localization does localization, no docking or route server):

  map_server        the map (default: maps/empty.yaml, everything free)
  planner_server    SmacPlannerHybrid: drivable paths for a car
  controller_server Regulated Pure Pursuit -> cmd_vel_nav
  behavior_server   wait, backup, drive_on_heading (no spin)
  bt_navigator      navigate_to_pose, navigate_through_poses (behavior_trees/*_car.xml)
  waypoint_follower follow_waypoints, follow_gps_waypoints (lat/lon via /fromLL)
  velocity_smoother cmd_vel_nav -> /cmd_vel/nav (or -> collision_monitor -> /cmd_vel/nav)
  lifecycle_manager brings them all up

The car's footprint and turning radius come from aav_description/config/vehicle.yaml.
Send a goal: RViz "2D Goal Pose" (publishes /goal_pose), or
  ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 20.0, y: 5.0}}}}"
"""

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare
from nav2_common.launch import RewrittenYaml


def nodes(context):
    share = FindPackageShare('aav_navigation').perform(context)
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context).lower() == 'true'
    collision_monitor = LaunchConfiguration('collision_monitor').perform(context).lower() == 'true'

    rewrites = vehicle.nav2_rewrites(vehicle.load()['vehicle'])
    rewrites.update({
        'yaml_filename': LaunchConfiguration('map').perform(context),
        'default_nav_to_pose_bt_xml': f'{share}/behavior_trees/navigate_to_pose_car.xml',
        'default_nav_through_poses_bt_xml':
            f'{share}/behavior_trees/navigate_through_poses_car.xml',
        'use_sim_time': str(use_sim_time),
    })
    params = ParameterFile(
        RewrittenYaml(source_file=f'{share}/config/nav2.yaml', param_rewrites=rewrites,
                      convert_types=True),
        allow_substs=True)

    smoothed = 'cmd_vel_smoothed' if collision_monitor else '/cmd_vel/nav'
    servers = [
        ('nav2_map_server', 'map_server', []),
        ('nav2_planner', 'planner_server', []),
        ('nav2_controller', 'controller_server', [('cmd_vel', 'cmd_vel_nav')]),
        ('nav2_behaviors', 'behavior_server', [('cmd_vel', 'cmd_vel_nav')]),
        ('nav2_bt_navigator', 'bt_navigator', []),
        ('nav2_waypoint_follower', 'waypoint_follower', []),
        ('nav2_velocity_smoother', 'velocity_smoother',
         [('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', smoothed)]),
    ]
    if collision_monitor:
        servers.append(('nav2_collision_monitor', 'collision_monitor', []))

    actions = [
        Node(package=pkg, executable=exe, name=exe, output='screen',
             parameters=[params], remappings=remaps)
        for pkg, exe, remaps in servers
    ]
    actions.append(Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time,
                     'autostart': (LaunchConfiguration('autostart').perform(context).lower()
                                   == 'true'),
                     'node_names': [name for _, name, _ in servers]}],
    ))
    return actions


def generate_launch_description():
    empty_map = PathJoinSubstitution([FindPackageShare('aav_navigation'), 'maps', 'empty.yaml'])
    return LaunchDescription([
        DeclareLaunchArgument('map', default_value=empty_map,
                              description='Map YAML (see maps/README.md)'),
        DeclareLaunchArgument('collision_monitor', default_value='false',
                              description='Insert collision_monitor (needs /radar/points)'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        OpaqueFunction(function=nodes),
    ])
