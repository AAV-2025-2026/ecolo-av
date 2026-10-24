"""
The camera streams: one camera_stream node per camera, each pulling its RTSP stream.

  ros2 launch aav_camera_stream camera_stream.launch.py host:=<camera Pi> [decoder:=...]

What you can set:
  cameras     which, comma-separated: front_left,front_right (config/cameras.yaml)
  host        the camera Pi's address (127.0.0.1: a MediaMTX on this computer)
  port        its RTSP port, 8554
  decoder     ffmpeg (any Mac or Linux), gst-nvidia (the Orin: NVIDIA's hardware),
              gst-soft, gst-mac, opencv (aav_camera_stream decoders.py)
  pipeline    a GStreamer pipeline instead of the decoder's own ({url}, {width}...)
  program     the decoder program, if not the preset's (gst-nvidia: /usr/bin/gst-launch-1.0)
  hwaccel     ffmpeg's -hwaccel, such as videotoolbox on a Mac; empty: software
  width, height, fps  the stream's: 1280, 720, 15 (pi/mediamtx.yml)
  delay       s from the camera to here, taken off each picture's stamp (measure it:
              docs/camera-pipeline.md)
  detector    rfdetr (the default), yolo or none; model, device, confidence, labels as
              aav_detector's detector.launch.py
  preview_period  s between small JPEG previews (0: none)
  source      real (the car), or sim, bench, replay for a stand-in stream
  time_code   true: read tools/stream_check.py's time code, to measure the delay

The nodes run as `python3 -m aav_camera_stream.camera_stream`: the python3 of the
environment that started the launch, so `pixi run -e ml` gives them PyTorch, as for
aav_detector's object detector.
"""

import atexit
import os
import tempfile

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare
import yaml

ARGS = [
    ('cameras', 'front_left,front_right', 'comma-separated: config/cameras.yaml names'),
    ('host', '127.0.0.1', "the camera Pi's address"),
    ('port', '8554', 'its RTSP port'),
    ('decoder', 'ffmpeg', 'ffmpeg, gst-nvidia (the Orin), gst-soft, gst-mac or opencv'),
    ('pipeline', '', "a GStreamer pipeline instead of the decoder's own"),
    ('program', '', "the decoder program's path, if not the preset's"),
    ('hwaccel', '', "ffmpeg's -hwaccel (videotoolbox on a Mac); empty: software"),
    ('transport', 'tcp', 'RTSP over tcp or udp'),
    ('width', '1280', 'px'),
    ('height', '720', 'px'),
    ('fps', '15.0', "the stream's rate, for the report"),
    ('delay', '0.06', 's: camera to here, taken off the stamps (an estimate: measure it)'),
    ('detector', 'rfdetr', 'rfdetr, yolo or none'),
    ('model', '', "the model file; empty = the detector's own"),
    ('device', 'auto', 'auto, cuda, cuda:N, mps or cpu'),
    ('confidence', '0.5', 'the lowest score kept'),
    ('labels', '', 'labels to keep, comma-separated; empty keeps all'),
    ('preview_period', '1.0', 's between previews; 0: none'),
    ('preview_width', '320', 'px'),
    ('publish_image', 'false', 'also every undistorted picture, as image_raw'),
    ('publish_camera_info', 'true', "the undistorted picture's lens, with a calibration"),
    ('source', 'real', 'real, sim, bench or replay: for /system/source'),
    ('time_code', 'false', "read the stream check's time code"),
    ('use_sim_time', 'false', "true in a simulator: stamps on the simulator's clock"),
]
INTS = ('width', 'height', 'preview_width')
FLOATS = ('fps', 'delay', 'confidence', 'preview_period')
BOOLS = ('publish_image', 'publish_camera_info', 'time_code', 'use_sim_time')
NOT_PARAMETERS = ('cameras', 'host', 'port')


def typed(name, text):
    if name in INTS:
        return int(text)
    if name in FLOATS:
        return float(text)
    if name in BOOLS:
        return text.strip().lower() == 'true'
    return text


def node_parameters(camera, settings, values, root):
    """One node's ROS parameters, from its config/cameras.yaml entry and the arguments."""
    params = {k: typed(k, v) for k, v in values.items() if k not in NOT_PARAMETERS}
    calibration = settings.get('calibration', '')
    params.update(camera=camera, url=f'rtsp://{values["host"]}:{values["port"]}/{camera}',
                  frame_id=settings.get('frame_id', f'camera_{camera}_link'),
                  calibration=os.path.join(root, calibration) if calibration else '')
    return params


def launch_setup(context):
    values = {name: LaunchConfiguration(name).perform(context) for name, _, _ in ARGS}
    share = FindPackageShare('aav_camera_stream').perform(context)
    with open(os.path.join(share, 'config', 'cameras.yaml')) as f:
        known = yaml.safe_load(f)['cameras']
    root = os.environ.get('PIXI_PROJECT_ROOT', os.getcwd())
    actions = []
    for camera in [c.strip() for c in values['cameras'].split(',') if c.strip()]:
        if camera not in known:
            raise ValueError(f'cameras:={values["cameras"]}: {camera} is not in '
                             f'config/cameras.yaml ({", ".join(known)})')
        name = f'camera_stream_{camera}'
        params = node_parameters(camera, known[camera], values, root)
        # A parameters file keeps each value's type (a label with a space, a pipeline).
        out = tempfile.NamedTemporaryFile('w', prefix=f'{name}_', suffix='.yaml', delete=False)
        with out:
            yaml.safe_dump({name: {'ros__parameters': params}}, out)
        atexit.register(os.remove, out.name)
        actions.append(ExecuteProcess(
            name=name, output='screen', emulate_tty=True,
            cmd=['python3', '-m', 'aav_camera_stream.camera_stream', '--ros-args',
                 '-r', f'__node:={name}', '--params-file', out.name]))
    return actions


def generate_launch_description():
    return LaunchDescription(
        [DeclareLaunchArgument(name, default_value=default, description=text)
         for name, default, text in ARGS] + [OpaqueFunction(function=launch_setup)])
