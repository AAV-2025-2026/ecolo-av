"""
Nav2 as one more driver: goals in, /drivers/nav/cmd_vel (TwistStamped) out to twist_mux.

  ros2 launch aav_navigation navigation.launch.py [map:=<path to map yaml>]
      [radar:=false] [lidar:=false] [collision_monitor:=<radar or lidar>]
      [camera_obstacles:=false] [ghost:=false]
      [reversing:=false] [max_speed:=] [controller:=rpp] [use_sim_time:=false]
      [autostart:=true]

Starts only the Nav2 servers a car needs (not nav2_bringup's full list: no AMCL, since
robot_localization does localization, no docking or route server):

  map_server        the map (default: maps/empty.yaml, everything free)
  planner_server    SmacPlannerHybrid: drivable paths for a car
  controller_server Regulated Pure Pursuit -> cmd_vel_nav; controller:=mppi for MPPI
                    instead, with its Ackermann model (docs/controllers.md)
  behavior_server   wait, backup, drive_on_heading (no spin)
  bt_navigator      navigate_to_pose, navigate_through_poses (behavior_trees/*_car*.xml)
  waypoint_follower follow_waypoints, follow_gps_waypoints (lat/lon via /fromLL)
  velocity_smoother cmd_vel_nav -> /drivers/nav/cmd_vel
                    (or -> /control/cmd_vel_smoothed -> collision_monitor)
  collision_monitor /control/cmd_vel_smoothed -> /drivers/nav/cmd_vel, stopping for radar
                    or lidar points ahead; its state and stop zone under
                    /safety/collision_monitor/
  lidar_scan        with lidar:=true (aav_lidar): the roof lidar's
                    cloud -> /sensors/lidar/scan (what stands between the road and just
                    over the roof, all the way round), for the costmap and collision_monitor
  lifecycle_manager brings them all up

Obstacles, from where the sensors are:
  radar:=true             where a radar publishes /sensors/radar/points (the bench; the car
                          with its radar part; Gazebo's road world): the local costmap's
                          obstacle layer reads it, so Nav2 stops for what the radar sees
  lidar:=true             where a lidar publishes /sensors/lidar/points (Gazebo's road and
                          test_lot worlds; the car's VLP-16, where car.launch.py's lidar
                          part runs): lidar_scan flattens it, the local
                          costmap's lidar_layer reads it, and collision_monitor too
  collision_monitor       radar or lidar unless set: it stops the car for radar or lidar
                          points in the stop zone ahead, whatever the costmap says. A
                          silent radar or lidar stops Nav2 too
  camera_obstacles:=true  the local costmap's camera layer reads aav_yolo camera_obstacles
                          (the detectors' boxes on the road). Off until the cameras are
                          calibrated (Q22)
  ghost:=true             a pretend person (aav_ghost ghost_obstacle, docs/ghost-obstacles.md):
                          its own costmap layer and collision_monitor source, so it only
                          adds. No ghost until someone places one: pixi run ghost ahead 10

Reversing (docs/learn-nav2.md): nothing senses what is behind the car, so it is off unless
asked for:
  reversing:=false        forward only: Dubins paths, no reversing in the controller, the
                          velocity smoother's lowest speed 0, the trees without BackUp
  reversing:=true         Reeds-Shepp paths (forward and back), Regulated Pure Pursuit
                          follows them backwards, down to -max_reverse_speed, and the trees
                          back up 1 m when stuck (behavior_trees/*_car_reversing.xml).
                          Gazebo and the bench turn it on; car.launch.py leaves it off

The car's footprint, turning radius and reverse speed come from
aav_description/config/vehicle.yaml.
Send a goal: RViz "2D Goal Pose" (publishes /goal_pose), or
  ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 20.0, y: 5.0}}}}"
"""

import tempfile

from aav_description import vehicle
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare
from nav2_common.launch import RewrittenYaml
import yaml


# The local costmap's parameters, as a whole path for RewrittenYaml: a leaf key such as
# `enabled` would change every key of that name in nav2.yaml.
LOCAL = 'local_costmap.local_costmap.ros__parameters.'


def flag(context, name):
    return LaunchConfiguration(name).perform(context).lower() == 'true'


def tuned_copy(source, v, reversing, max_speed, radar, lidar, ghost=False, controller='rpp'):
    """Return a temporary copy of nav2.yaml, tuned by vehicle.nav2_tuned (no ROS there)."""
    with open(source) as f:
        cfg = vehicle.nav2_tuned(yaml.safe_load(f), v, reversing, max_speed, radar, lidar,
                                 ghost, controller)
    out = tempfile.NamedTemporaryFile('w', prefix='nav2_', suffix='.yaml', delete=False)
    with out:
        yaml.safe_dump(cfg, out)
    return out.name


def nodes(context):
    share = FindPackageShare('aav_navigation').perform(context)
    use_sim_time = flag(context, 'use_sim_time')
    radar = flag(context, 'radar')
    lidar = flag(context, 'lidar')
    ghost = flag(context, 'ghost')
    # Empty: wherever a sensor (or the ghost) can feed it.
    monitor = LaunchConfiguration('collision_monitor').perform(context).strip().lower()
    collision_monitor = (radar or lidar or ghost) if monitor == '' else monitor == 'true'
    camera = flag(context, 'camera_obstacles')
    reversing = flag(context, 'reversing')

    v = vehicle.load()['vehicle']
    trees = '_car_reversing.xml' if reversing else '_car.xml'
    rewrites = vehicle.nav2_rewrites(v, reversing)
    rewrites.update({
        'yaml_filename': LaunchConfiguration('map').perform(context),
        'default_nav_to_pose_bt_xml': f'{share}/behavior_trees/navigate_to_pose{trees}',
        'default_nav_through_poses_bt_xml':
            f'{share}/behavior_trees/navigate_through_poses{trees}',
        LOCAL + 'obstacle_layer.enabled': str(radar).lower(),
        LOCAL + 'camera_layer.enabled': str(camera).lower(),
    })
    # A copy of nav2.yaml with the values RewrittenYaml can't write (lists: the velocity
    # smoother's limits, collision_monitor's sources, the costmap's layers), the
    # controller, and max_speed:= (sim.launch.py sim_speed:=). In the file, not as
    # per-node dicts after it: nav2.yaml names its nodes, and a named entry beats a later
    # dict when the launch sets a global parameter (sim.launch.py's use_sim_time).
    speed = LaunchConfiguration('max_speed').perform(context).strip()
    controller = LaunchConfiguration('controller').perform(context).strip().lower()
    source = tuned_copy(f'{share}/config/nav2.yaml', v, reversing,
                        float(speed) if speed else None, radar, lidar, ghost, controller)
    params = ParameterFile(
        RewrittenYaml(source_file=source, param_rewrites=rewrites, convert_types=True),
        allow_substs=True)

    smoothed = '/control/cmd_vel_smoothed' if collision_monitor else '/drivers/nav/cmd_vel'
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
        # Its marker topic is private (~/collision_points_marker): move it next to the
        # rest of what it publishes, under /safety/collision_monitor/.
        servers.append(('nav2_collision_monitor', 'collision_monitor', [
            ('/collision_monitor/collision_points_marker',
             '/safety/collision_monitor/collision_points_marker')]))

    # use_sim_time is passed on its own: RewrittenYaml only rewrites keys that already
    # exist, and nav2.yaml has none, so as a rewrite it was silently dropped.
    actions = [
        Node(package=pkg, executable=exe, name=exe, output='screen',
             parameters=[params, {'use_sim_time': use_sim_time}],
             remappings=remaps)
        for pkg, exe, remaps in servers
    ]
    if lidar:
        # Not a lifecycle node: it runs from the start, Nav2's servers or not.
        actions.append(Node(package='aav_lidar', executable='lidar_scan', name='lidar_scan',
                            output='screen',
                            parameters=[params, {'use_sim_time': use_sim_time}]))
    if ghost:
        # Not a lifecycle node either. Its own file, then use_sim_time: the file doesn't
        # set it, so the dict adds it rather than losing to the file.
        config = FindPackageShare('aav_ghost').perform(context) + '/config/ghost_obstacle.yaml'
        actions.append(Node(package='aav_ghost', executable='ghost_obstacle',
                            name='ghost_obstacle', output='screen',
                            parameters=[config, {'use_sim_time': use_sim_time}]))
    actions.append(Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time,
                     'autostart': flag(context, 'autostart'),
                     'node_names': [name for _, name, _ in servers]}],
    ))
    return actions


def generate_launch_description():
    empty_map = PathJoinSubstitution([FindPackageShare('aav_navigation'), 'maps', 'empty.yaml'])
    return LaunchDescription([
        DeclareLaunchArgument('map', default_value=empty_map,
                              description='Map YAML (see maps/README.md)'),
        DeclareLaunchArgument('radar', default_value='false',
                              description='true where a radar publishes '
                                          '/sensors/radar/points: the '
                                          "local costmap's obstacle layer reads it"),
        DeclareLaunchArgument('lidar', default_value='false',
                              description='true where a lidar publishes '
                                          '/sensors/lidar/points: lidar_scan, the '
                                          "local costmap's lidar_layer and collision_monitor "
                                          'read it'),
        # Empty: radar, lidar or ghost. collision_monitor needs one of them, and stops Nav2
        # when one goes silent.
        DeclareLaunchArgument('collision_monitor', default_value='',
                              description='Insert collision_monitor (needs the radar, '
                                          'the lidar or the ghost); empty: wherever one runs'),
        DeclareLaunchArgument('camera_obstacles', default_value='false',
                              description="true: the local costmap's camera layer reads "
                                          '/perception/camera_obstacles'),
        DeclareLaunchArgument('ghost', default_value='false',
                              description='true: a pretend person (aav_ghost), its own '
                                          'costmap layer and collision_monitor source; '
                                          'placed with pixi run ghost'),
        DeclareLaunchArgument('max_speed', default_value='',
                              description="m/s: Nav2's top speed, if not nav2.yaml's 1.0 "
                                          '(sim.launch.py sim_speed:=)'),
        DeclareLaunchArgument('reversing', default_value='false',
                              description='true: Nav2 may drive backwards (blind: nothing '
                                          'senses behind the car). docs/learn-nav2.md'),
        DeclareLaunchArgument('controller', default_value='rpp',
                              description='rpp (Regulated Pure Pursuit) or mppi: what '
                                          'follows the path. docs/controllers.md'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('autostart', default_value='true'),
        OpaqueFunction(function=nodes),
    ])
