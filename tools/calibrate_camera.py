"""
calibrate_camera: calibrate a streamed camera with ROS's camera_calibration, and file it.

  pixi run calibrate-camera board [--square 0.025] [--paper a4|a3] [--out FILE.svg]
  pixi run calibrate-camera front_left [--host 192.168.1.108] [--port 8554] [--square 0.025]
  pixi run calibrate-camera install front_left [/tmp/calibrationdata.tar.gz or ost.yaml]

board: write the checkerboard to print (9x6 inner corners, 25 mm squares, A4; SVG, print
at 100%, then measure a square and pass that with --square).

<camera>: pulls rtsp://<host>:8554/<camera> (the camera Pi's MediaMTX) through
camera_stream (no detector, no undistortion, every picture as image_raw), and opens
camera_calibration's window on it (the calib environment: pixi install --locked -e calib,
done here once). Move the board until X, Y, Size and Skew are green, press CALIBRATE, then
SAVE, then close the window. The result (/tmp/calibrationdata.tar.gz) is filed as
src/sensors/aav_camera_stream/config/calibrations/<camera>.yaml, and config/cameras.yaml
points to it: commit both. Everything stays on this computer's own ROS domain (LOCALHOST):
only the RTSP stream comes over the network.

install: file a result saved before (the same checks: a camera_info YAML that fits the
1280x720 stream).

docs/camera-calibration.md has the whole procedure, for the car.
"""

import os
import random
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIBRATOR = os.path.join(ROOT, '.pixi', 'envs', 'calib', 'lib', 'camera_calibration',
                          'cameracalibrator')
# camera_calibration with OpenCV 5's checkerboard corners put back in OpenCV 4's shape.
SHIM = os.path.join(ROOT, 'tools', 'camera_calibration_cv5.py')
# What the calibrator keeps of this environment: who, where, and the screen.
KEEP = ('HOME', 'USER', 'LOGNAME', 'SHELL', 'TERM', 'LANG', 'LC_ALL', 'TMPDIR', 'DISPLAY',
        'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'QT_QPA_PLATFORM',
        'PYTHONUNBUFFERED')
PAPER = {'a4': (297.0, 210.0), 'letter': (279.4, 215.9), 'a3': (420.0, 297.0)}


def option(args, name, default):
    return args[args.index(name) + 1] if name in args else default


def board(args):
    from aav_camera_stream import calibration
    square = float(option(args, '--square', '0.025'))
    paper = option(args, '--paper', 'a4').lower()
    out = option(args, '--out', f'checkerboard-9x6-{1000 * square:g}mm.svg')
    if paper not in PAPER:
        raise SystemExit(f'--paper {paper}: use one of {", ".join(PAPER)}')
    svg = calibration.board_svg(calibration.Board(square_m=square), PAPER[paper])
    with open(out, 'w') as f:
        f.write(svg)
    print(f'{out}: 9x6 inner corners, {1000 * square:g} mm squares, {paper.upper()} '
          'landscape. Print it at 100% ("actual size"), glue it on something flat, and '
          'measure a square: give that to --square (in m)')
    return 0


def install(camera, path, note=''):
    from aav_camera_stream import calibration
    try:
        relative = calibration.install(calibration.read_result(path), camera, ROOT,
                                       note=note)
    except (OSError, ValueError) as e:
        raise SystemExit(f'{path}: not filed: {e}')
    print(f'Filed: {relative}\n'
          f'config/cameras.yaml: {camera} calibration: {relative}\n'
          f'Commit both (git add {relative} {calibration.CAMERAS}); camera_stream_{camera} '
          'undistorts with it and publishes its CameraInfo from its next start')
    return 0


def known_cameras():
    import yaml
    from aav_camera_stream import calibration
    with open(os.path.join(ROOT, calibration.CAMERAS)) as f:
        return yaml.safe_load(f)['cameras']


def stop(proc):
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(5)
        except (ProcessLookupError, PermissionError):
            pass
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def wait_for_publisher(topic, seconds=30.0):
    """
    Wait until the topic has a publisher (camera_stream's), on this process's ROS domain.

    camera_calibration takes the QoS of the publisher it finds; with none yet it takes
    best effort, and over Cyclone DDS a 2.7 MB best-effort picture is lost whenever one
    of its pieces is (24 Oct: not one of 50 s of pictures arrived). So it starts after.
    """
    import rclpy
    rclpy.init()
    node = rclpy.create_node('calibrate_camera_wait')
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if node.count_publishers(topic):
                return True
            rclpy.spin_once(node, timeout_sec=0.2)
        return False
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


def calibrate(camera, args):
    from aav_camera_stream import calibration
    cameras = known_cameras()
    if camera not in cameras:
        raise SystemExit(f'{camera}: not in config/cameras.yaml ({", ".join(cameras)})')
    host = option(args, '--host', '192.168.1.108')    # CAM1-PI (orin.yaml)
    port = option(args, '--port', '8554')
    square = float(option(args, '--square', '0.025'))
    board_ = calibration.Board(square_m=square)
    if not os.path.exists(CALIBRATOR):
        print('camera_calibration, once: pixi install --locked -e calib', flush=True)
        subprocess.run(['pixi', 'install', '--locked', '-e', 'calib'], cwd=ROOT, check=False)
        if not os.path.exists(CALIBRATOR):
            raise SystemExit('No camera_calibration: pixi install --locked -e calib failed')
    domain = os.environ.get('AAV_CALIBRATE_DOMAIN', str(random.randint(150, 230)))
    os.environ.update(ROS_DOMAIN_ID=domain, ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    url = f'rtsp://{host}:{port}/{camera}'
    topic = f'/sensors/camera/{camera}/image_raw'
    started = time.time()
    print(f'{camera}: {url} -> camera_stream -> {topic} -> camera_calibration '
          f'(--size {board_.size} --square {square:g}); ROS domain {domain}, this computer '
          'only.\nMove the board: left, right, up, down, near, far and tilted, until X, Y, '
          'Size and Skew are green. Then CALIBRATE (wait), SAVE, and close the window.',
          flush=True)
    stream = calibrator = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt
    # Each child has its own process group, stopped below: Ctrl-C, a closed terminal or a
    # kill all come here first.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        # The raw picture: no calibration (even one there is), no detector, every picture.
        stream = subprocess.Popen(
            [sys.executable, '-m', 'aav_camera_stream.camera_stream', '--ros-args',
             '-r', f'__node:=calibrate_{camera}', '-p', f'camera:={camera}',
             '-p', f'url:={url}', '-p', f'frame_id:={cameras[camera]["frame_id"]}',
             '-p', 'detector:=none', '-p', 'publish_image:=true',
             '-p', 'preview_period:=0.0', '-p', 'publish_camera_info:=false'],
            process_group=0)
        if not wait_for_publisher(topic):
            raise SystemExit(f'camera_stream never published {topic}')
        # The calib environment's own ROS (Jazzy), activated from nothing: started from
        # inside this one, its activation keeps this one's as a backup and leaves out
        # RMW_IMPLEMENTATION and ROS_DISTRO (24 Oct: the calibrator then never met the
        # stream). The range after activation, which sets SUBNET.
        clean = {k: os.environ[k] for k in KEEP if k in os.environ}
        clean['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
        calibrator = subprocess.Popen(
            [os.environ.get('PIXI_EXE') or shutil.which('pixi') or 'pixi', 'run', '--frozen',
             '-e', 'calib', '/usr/bin/env', f'ROS_DOMAIN_ID={domain}',
             'ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST', 'python', SHIM,
             *calibration.calibrator_command('cameracalibrator', board_, topic)],
            cwd=ROOT, env=clean, process_group=0)
        calibrator.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop(calibrator)
        stop(stream)
    if not os.path.exists(calibration.RESULT) or os.path.getmtime(calibration.RESULT) < started:
        print(f'No new {calibration.RESULT}: nothing filed (SAVE, after CALIBRATE, writes it)')
        return 1
    return install(camera, calibration.RESULT,
                   note=f'{time.strftime("%Y-%m-%d")}, board {board_.size} corners, '
                        f'{1000 * square:g} mm squares, from {url}')


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if args else 2
    if args[0] == 'board':
        return board(args[1:])
    if args[0] == 'install':
        if len(args) < 2:
            raise SystemExit('install <camera> [file]: which camera?')
        from aav_camera_stream import calibration
        return install(args[1], args[2] if len(args) > 2 else calibration.RESULT)
    return calibrate(args[0], args[1:])


if __name__ == '__main__':
    sys.exit(main())
