"""
foxglove_bridge: watch the car, or a stand-in, from Foxglove or Lichtblick (docs/foxglove.md).

  ros2 launch aav_bringup foxglove.launch.py [foxglove_address:=127.0.0.1]
      [foxglove_port:=8765] [use_sim_time:=false] [foxglove_control:=true]
      [foxglove_topics:=wifi] [foxglove_preview:=]

The sim, the bench and CARLA start it with foxglove:=true; the car with its foxglove part.
A laptop connects to ws://<address>:<port> and loads a layout from tools/foxglove/.
The names start with foxglove_ because an included file's arguments reach the file that
includes it (CARLA's own launch has a port and a control). Pass every one.

  foxglove_address  127.0.0.1: this computer only, like the stand-ins (tools/ros.sh
                    --local). 0.0.0.0: every network the computer is on (the car)
  foxglove_control  true: a client may publish a goal (/goal_pose), drive
                    (/drivers/keyboard/cmd_vel), press or clear the e-stop
                    (/safety/estop), set parameters and call services. false: it only
                    watches (the car: anyone on its WiFi reaches the bridge)
  foxglove_topics   wifi: config/foxglove_bridge.yaml's list, without the raw cameras
                    and the full lidar (docs/bandwidth.md). all: every topic, for a
                    laptop on a cable
  foxglove_preview  the stand-ins' cameras to make a small preview of, comma-separated
                    (such as front_left): /perception/camera/<camera>/preview/compressed,
                    a JPEG once a second, the topic the car's camera_stream makes. Two
                    stock nodes: topic_tools throttle (image_raw, once a second, to
                    .../preview) and image_transport republish (to .../preview/compressed).
                    Empty: none (the car)
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

PORT = 8765
TOPICS = ('wifi', 'all')
CAMERAS = ('front_left', 'front_right', 'rear')
# What a client may publish to, with foxglove_control:=true: a goal, driving, the e-stop.
CLIENT_TOPICS = ['^/goal_pose$', '^/drivers/keyboard/cmd_vel$', '^/safety/estop$']
WATCH = ['connectionGraph', 'assets']           # foxglove_control:=false: nothing more
CONTROL = WATCH + ['clientPublish', 'parameters', 'parametersSubscribe', 'services']
PREVIEW_HZ = 1.0


def preview(camera, use_sim_time):
    """Return the two nodes that make one camera's preview, as camera_stream's."""
    raw = f'/sensors/camera/{camera}/image_raw'
    small = f'/perception/camera/{camera}/preview'
    clock = {'use_sim_time': use_sim_time}
    return [
        Node(package='topic_tools', executable='throttle', name=f'preview_throttle_{camera}',
             arguments=['messages', raw, str(PREVIEW_HZ), small], parameters=[clock]),
        Node(package='image_transport', executable='republish',
             name=f'preview_jpeg_{camera}',
             parameters=[clock, {'in_transport': 'raw', 'out_transport': 'compressed'}],
             # Its compressed publisher's name isn't remapped with "out" (seen 24 Oct).
             remappings=[('in', small), ('out', small),
                         ('out/compressed', f'{small}/compressed')]),
    ]


def launch_setup(context):
    def arg(name):
        return LaunchConfiguration(name).perform(context)

    control = arg('foxglove_control').lower() == 'true'
    sim_time = arg('use_sim_time').lower() == 'true'
    topics = arg('foxglove_topics').lower()
    if topics not in TOPICS:
        raise ValueError(f'foxglove_topics:={topics}: use wifi (no raw cameras or full '
                         'lidar) or all')
    cameras = [c.strip() for c in arg('foxglove_preview').split(',') if c.strip()]
    unknown = sorted(set(cameras) - set(CAMERAS))
    if unknown:
        raise ValueError(f'foxglove_preview: {unknown} is not one of {CAMERAS}')
    config = os.path.join(FindPackageShare('aav_bringup').perform(context), 'config',
                          'foxglove_bridge.yaml')
    settings = {
        'address': arg('foxglove_address'),
        'port': int(arg('foxglove_port')),
        'use_sim_time': sim_time,
        'capabilities': CONTROL if control else WATCH,
        'client_topic_whitelist': CLIENT_TOPICS if control else ['(?!)'],
    }
    if topics == 'all':
        settings['topic_whitelist'] = ['.*']
    actions = [Node(package='foxglove_bridge', executable='foxglove_bridge',
                    name='foxglove_bridge', parameters=[config, settings])]
    for camera in cameras:
        actions += preview(camera, sim_time)
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('foxglove_address', default_value='127.0.0.1',
                              description='127.0.0.1: this computer only; 0.0.0.0: every '
                                          'network it is on (the car)'),
        DeclareLaunchArgument('foxglove_port', default_value=str(PORT)),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('foxglove_control', default_value='true',
                              description='true: a client may send a goal, drive and use '
                                          'the e-stop; false: watch only (the car)'),
        DeclareLaunchArgument('foxglove_topics', default_value='wifi',
                              description='wifi: no raw cameras or full lidar '
                                          '(config/foxglove_bridge.yaml); all: every topic'),
        DeclareLaunchArgument('foxglove_preview', default_value='',
                              description='cameras to make a small JPEG of, once a second, '
                                          'as the car does: such as front_left'),
        OpaqueFunction(function=launch_setup),
    ])
