"""
The real car. One launch file for every machine; a machine file picks the parts.

  ros2 launch aav_bringup car.launch.py machine:=orin
      [gps:=true] [gps_driver:=ublox] [map:=<map yaml>] [start_x:=0] [start_y:=0]
      [start_yaw:=0] [max_speed:=0.3]
      [reversing:=true]   (Nav2 may back up, at 0.5 m/s at most, where the machine runs
                           something that sees behind: the lidar.
                           Without, it stays forward only and says why. false: never)
      [lidar:=true]       (false: no lidar anywhere, whatever the machine file says)
      [ghost:=false]      (true: a pretend person in Nav2's view, where Nav2 runs, for
                           stopping tests with nothing real to hit: pixi run ghost ahead 10)

machine: config/machines/<machine>.yaml lists which parts run on that computer
(orin, motor_pi, laptop, all), and the detector's settings there. Every machine uses the
same ROS_DOMAIN_ID, so the parts find each other over the network; see docs/platforms.md.
The arguments win over the machine file: gps:=false starts no GPS driver anywhere, and
lidar:=false no lidar. A part
that can't run here (no PyTorch, no model file, no usb_cam) is skipped with a warning.

Parts and what they start:
  description     robot_state_publisher (+ joint_state_publisher): the car's frames
  mux, ego        twist_mux -> /control/cmd_vel -> ego -> /ego/actuator_cmd; with the
                  mux, the sensor watchdog (aav_safety): it stops Nav2 and the AI slot when
                  a sensor they need fails, and they stop too if it goes quiet
  teleop          joystick -> /drivers/joy/cmd_vel, e-stop button -> /safety/estop
  scripted        /scripted_drive action -> /drivers/scripted/cmd_vel
  goto            /goto action (drive to a GPS point, stop there) -> /drivers/goto/cmd_vel
  imu, gps,       sensor drivers (on the machine the device is plugged into);
  radar, battery  gps_driver picks the GPS's: ublox (the default), nmea or ublox_dgnss
  lidar           the roof Velodyne VLP-16, through the stock velodyne driver ->
                  /sensors/lidar/points. On the machine its packets go to: the Jetson
  camera          usb_cam -> /sensors/camera/front_left/image_raw (Linux only)
  detector        YOLO on /sensors/camera/front_left/image_raw -> /perception/detections, as
                  yolo_detector_<machine>, with the machine file's model
  stop_signs      stop_sign_watcher -> /perception/stop_sign, twist_mux's stop-sign lock (the
                  lock is in aav_mux's config). One per car, next to the mux
  radar_clusters  DBSCAN (aav_radar_clusters, Rust) on /sensors/radar/points ->
                  /perception/radar/clusters, /perception/radar/cluster_boxes
  camera_obstacles
                  the detectors' boxes as points on the road -> /perception/camera_obstacles,
                  for Nav2's costmap. Off until the cameras are calibrated (Q22)
  lane            lane keeping: lane_finder on /sensors/camera/front_left/image_raw ->
                  /perception/lane/geometry, and
                  control_interface -> /drivers/ai/cmd_vel (twist_mux's AI slot). Off on every
                  machine: it drives whenever it sees a lane, unless a driver above it does
  localization    ekf_local, ekf_global, navsat_transform
  navigation      Nav2 -> /drivers/nav/cmd_vel. Nav2's local costmap reads the sensors
                  this machine runs: with radar, /sensors/radar/points, and
                  collision_monitor stops Nav2 for radar points just ahead; with
                  camera_obstacles, the camera's points; with lidar, /sensors/lidar/points
                  (and collision_monitor stops Nav2 for lidar points, or a silent lidar)
  spine           backend: CAN spine (ros2_socketcan + spine_bridge)
  legacy_uart     backend: today's ESP32 over UART (the Pi wired to it)
  legacy_encoder  today's wheel encoder over UDP
  foxglove        foxglove_bridge on port 8765, for Foxglove Studio on a laptop

The detector runs as `python3 -m aav_yolo.detector`, the python3 of the environment that
starts this file: on a laptop, the ml environment's PyTorch (pixi run -e ml car laptop);
on the Orin, JetPack's (docs/perception.md).
"""

import os
import re
import shutil
import subprocess

from aav_description import vehicle
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import evaluate_condition_expression
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.logging import get_logger
from launch.substitutions import LaunchConfiguration
from launch.utilities import perform_substitutions
from launch_ros.actions import Node
import yaml

PARTS = ('description', 'mux', 'ego', 'teleop', 'scripted', 'goto', 'imu', 'gps', 'radar',
         'lidar', 'battery', 'camera', 'detector', 'stop_signs', 'radar_clusters',
         'camera_obstacles', 'lane', 'localization', 'navigation', 'spine', 'legacy_uart',
         'legacy_encoder', 'foxglove')
# What a machine file holds: the parts, and the detector's settings.
SECTIONS = ('parts', 'detector')
# Each model format: what runs it, besides PyTorch and Ultralytics, and how to make it.
FORMATS = {
    '.pth': ([], 'pixi run get-models'),
    '.pt': ([], 'pixi run get-models'),
    '.mlpackage': (['coremltools'], 'pixi run -e ml export-coreml (on a Mac)'),
    '.engine': (['tensorrt'], 'python3 tools/build_engine.py (on this computer)'),
}
# Prints the modules a python3 lacks. find_spec looks without importing: no time at all.
MISSING = ('import importlib.util as u, sys; '
           'print(" ".join(m for m in sys.argv[1:] if not u.find_spec(m)))')


def launch_file(package, name):
    return os.path.join(get_package_share_directory(package), 'launch', name)


def include(package, name, **args):
    # Pass every argument the included file needs: included files share launch
    # arguments, so one left out may arrive from another file.
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file(package, name)),
        launch_arguments={k: str(v).lower() if isinstance(v, bool) else str(v)
                          for k, v in args.items()}.items())


def installed(package):
    try:
        get_package_share_directory(package)
    except PackageNotFoundError:
        return False
    return True


def skipped(part, why):
    """Warn that a part the machine file asks for can't run here; the rest still starts."""
    get_logger('car.launch.py').warning(f'{part}: not started: {why}')
    return []


def workspace():
    """Return this repository: Pixi's project folder, or the folder holding colcon's install/."""
    if os.environ.get('PIXI_PROJECT_ROOT'):
        return os.environ['PIXI_PROJECT_ROOT']
    head, found, _ = get_package_share_directory('aav_bringup').partition(
        f'{os.sep}install{os.sep}')
    return head if found else os.getcwd()


def load_machine(machine):
    folder = os.path.join(get_package_share_directory('aav_bringup'), 'config', 'machines')
    path = os.path.join(folder, f'{machine}.yaml')
    if not os.path.isfile(path):
        known = sorted(f[:-len('.yaml')] for f in os.listdir(folder) if f.endswith('.yaml'))
        raise RuntimeError(f'machine:={machine}: no such machine file. Pick one of {known}')
    with open(path) as f:
        config = yaml.safe_load(f)
    for what, found, known in (('sections', config, SECTIONS),
                               ('parts', config['parts'], PARTS)):
        unknown = set(found) - set(known)
        if unknown:
            raise RuntimeError(f'{machine}.yaml: unknown {what} {sorted(unknown)}')
    return config


def lacks(modules):
    """Return the python3 on PATH, which the detector runs in, and the modules it lacks."""
    python = shutil.which('python3') or 'python3'
    return python, subprocess.run([python, '-c', MISSING, *modules],
                                  capture_output=True, text=True).stdout.split()


def detector(context, machine, settings):
    """Return the detector part, as yolo_detector_<machine>, or why it can't start."""
    if not isinstance(settings, dict):
        raise RuntimeError(f'{machine}.yaml: give the detector settings, such as '
                           f'"detector: {{detector: rfdetr}}"')
    path = launch_file('aav_yolo', 'detector.launch.py')
    declared = (PythonLaunchDescriptionSource(path).get_launch_description(context)
                .get_launch_arguments())
    unknown = set(settings) - ({a.name for a in declared} - {'node_name', 'picture'})
    if unknown:
        raise RuntimeError(f'{machine}.yaml: the detector takes no {sorted(unknown)}')
    # Every argument, its own defaults included, so none can leak in from another file.
    defaults = {a.name: perform_substitutions(context, a.default_value) for a in declared
                if a.default_value is not None}
    args = {**defaults, 'labels': 'stop sign', **settings}
    from aav_yolo.boxes import check_detector   # here: only machines with a detector need it
    try:
        model = check_detector(str(args['detector']), str(args['model']))
    except ValueError as e:
        raise RuntimeError(f'{machine}.yaml: {e}')
    model = os.path.join(workspace(), os.path.expanduser(model))
    runtime, make = FORMATS.get(os.path.splitext(model)[1], ([], 'docs/perception.md'))
    library = 'rfdetr' if str(args['detector']).strip().lower() == 'rfdetr' else 'ultralytics'
    python, missing = lacks(['torch', library, *runtime])
    if missing:
        return skipped('detector', f'{python} has no {", ".join(missing)}. On a laptop: '
                                   f'pixi run -e ml car {machine}. On the Orin: '
                                   "JetPack's PyTorch and TensorRT (docs/perception.md)")
    if not os.path.exists(model):
        return skipped('detector', f'{model} is missing. Make it with {make}')
    args.update(model=model, picture='',
                node_name='yolo_detector_' + re.sub(r'\W', '_', machine))
    return [include('aav_yolo', 'detector.launch.py', **args)]


def launch_setup(context):
    def arg(name):
        return LaunchConfiguration(name).perform(context)

    def flag(name):
        # As IfCondition reads it: true or 1, false or 0; anything else is an error.
        return evaluate_condition_expression(context, [LaunchConfiguration(name)])

    machine = arg('machine')
    config = load_machine(machine)
    parts = config['parts']

    def on(name):
        # A launch argument can switch a part off, wherever the machine file has it.
        return (bool(parts.get(name, False)) and (name != 'gps' or flag('gps'))
                and (name != 'lidar' or flag('lidar')))

    actions = []
    if on('description'):
        actions.append(include('aav_description', 'description.launch.py'))
    if on('mux'):
        actions.append(include('aav_mux', 'mux.launch.py'))
        # The sensor watchdog, next to the mux: twist_mux's sensors lock stops Nav2 and the
        # AI slot when the wheels, the IMU, the GPS or an EKF fail (aav_safety), and when
        # the watchdog itself goes quiet (the lock's 1 s timeout). Nav2 and the sensors may
        # run on other machines: it watches their topics over the network.
        actions.append(include('aav_safety', 'watchdog.launch.py',
                               inputs='odom,imu,local,global' + (',gps' if flag('gps') else '')))
    if on('ego'):
        actions.append(include('aav_ego', 'ego.launch.py'))
    if on('teleop'):
        actions.append(include('aav_teleop', 'teleop.launch.py'))
    if on('scripted'):
        actions.append(include('aav_scripted', 'scripted.launch.py'))
    if on('goto'):
        actions.append(include('aav_goto', 'goto.launch.py'))
    if any(on(s) for s in ('imu', 'gps', 'radar', 'lidar', 'battery')):
        actions.append(include('aav_sensors', 'sensors.launch.py',
                               imu=on('imu'), gps=on('gps'), radar=on('radar'), lidar=on('lidar'),
                               battery=on('battery'), gps_driver=arg('gps_driver')))
    if on('camera'):
        if installed('usb_cam'):
            actions.append(include('aav_sensors', 'cameras.launch.py',
                                   left='/dev/aav/camera_left', right=''))
        else:
            actions += skipped('camera', 'usb_cam is not installed here (it is Linux only)')
    if on('detector'):
        actions += detector(context, machine, config.get('detector') or {})
    if on('stop_signs'):
        actions.append(Node(package='aav_yolo', executable='stop_sign_watcher',
                            name='stop_sign_watcher'))
    if on('radar_clusters'):
        actions.append(include('aav_radar_clusters', 'radar_clusters.launch.py',
                               mock=False, eps=0.8, minimum_points=15, radar_rviz=False))
    if on('camera_obstacles'):
        actions.append(Node(package='aav_yolo', executable='camera_obstacles',
                            name='camera_obstacles',
                            parameters=[os.path.join(get_package_share_directory('aav_yolo'),
                                                     'config', 'camera_obstacles.yaml')]))
    if on('lane'):
        actions += [include('aav_lane_finder', 'lane_finder.launch.py', debug_image=False),
                    include('aav_lane_geometry', 'lane_follower.launch.py', fake=False)]
    if on('localization'):
        actions.append(include('aav_localization', 'localization.launch.py',
                               gps=flag('gps'), start_x=arg('start_x'),
                               start_y=arg('start_y'), start_yaw=arg('start_yaw')))
    if on('navigation'):
        # Always pass a map: an empty `map` here would override Nav2's own default,
        # because included launch files share launch arguments.
        empty_map = os.path.join(get_package_share_directory('aav_navigation'), 'maps',
                                 'empty.yaml')
        # Nav2 backs up only if something here sees behind the car (Ben, 22 Oct: "Yes the
        # car can reverse"); collision_monitor then watches a box behind the rear bumper.
        reversing = flag('reversing')
        blind = vehicle.blind_behind(reversing, radar=on('radar'), lidar=on('lidar'))
        if blind:
            get_logger('car.launch.py').warning(f'reversing: {blind}')
            reversing = False
        # The local costmap reads the sensors this machine runs. Each is passed, on or
        # off, so none can leak in from another file.
        actions.append(include('aav_navigation', 'navigation.launch.py',
                               map=arg('map') or empty_map, radar=on('radar'),
                               lidar=on('lidar'), ghost=flag('ghost'),
                               collision_monitor=on('radar') or on('lidar') or flag('ghost'),
                               camera_obstacles=on('camera_obstacles'),
                               reversing=reversing))
    if on('spine'):
        actions.append(include('aav_spine', 'spine.launch.py'))
    if on('legacy_uart') or on('legacy_encoder'):
        actions.append(include('aav_legacy', 'legacy.launch.py',
                               uart=on('legacy_uart'), encoder=on('legacy_encoder')))
    if on('foxglove'):
        actions.append(Node(package='foxglove_bridge', executable='foxglove_bridge',
                            name='foxglove_bridge', parameters=[{'port': 8765}]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('machine', default_value='all',
                              description='config/machines/<machine>.yaml'),
        DeclareLaunchArgument('max_speed', default_value='',
                              description='m/s: cap ego below config/ego.yaml (a first drive on '
                                          'stands: max_speed:=0.3); empty keeps ego.yaml'),
        DeclareLaunchArgument('gps', default_value='true',
                              description='false: no GPS anywhere (odometry only), whatever '
                                          'the machine file says'),
        DeclareLaunchArgument('gps_driver', default_value='ublox',
                              description='ublox (u-blox, Pixi too), nmea (any NMEA receiver) '
                                          'or ublox_dgnss (u-blox F9P, apt only). Tentative '
                                          'until the receiver is known: Q18'),
        DeclareLaunchArgument('map', default_value='',
                              description='Map YAML for Nav2 (default: the empty map)'),
        # The roof's Velodyne VLP-16 (the 16 Oct audit), where the machine file has the
        # lidar part: its driver, and Nav2 reading it. false switches it off everywhere.
        DeclareLaunchArgument('lidar', default_value='true',
                              description='false: no lidar driver, and Nav2 without the '
                                          'lidar, whatever the machine file says'),
        # Off unless asked for: a pretend person, for stopping tests on the real car with
        # nothing real to hit (aav_ghost, docs/ghost-obstacles.md). Where Nav2 runs.
        DeclareLaunchArgument('ghost', default_value='false',
                              description="true: a pretend person in Nav2's view, placed "
                                          'with pixi run ghost ahead 10 (it only adds)'),
        DeclareLaunchArgument('start_x', default_value='0.0'),
        DeclareLaunchArgument('start_y', default_value='0.0'),
        DeclareLaunchArgument('start_yaw', default_value='0.0',
                              description='Heading at start, rad counter-clockwise from east'),
        # On since 22 Oct (Ben: "Yes the car can reverse"), where something sees behind
        # (vehicle.blind_behind). People can always reverse (joystick, keyboard, RC); this
        # is Nav2 only.
        DeclareLaunchArgument('reversing', default_value='true',
                              description='true: Nav2 may back up, with the lidar '
                                          'watching behind '
                                          '(docs/learn-nav2.md); false: forward only'),
        OpaqueFunction(function=launch_setup),
    ])
