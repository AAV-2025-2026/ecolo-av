#!/usr/bin/env python3
"""
Save the front camera's pictures of Gazebo's stop sign, from several distances.

    pixi run python3 tools/sim_frames.py --out ~/aav-models/frames   (about 1 minute)

For tools/compare_detectors.py: every detector gets the same pictures. Starts the road
world headless (no Nav2, lidar, radar or watchdog), on its own ROS domain and Gazebo
partition, on this computer only; puts the car on the lane's centre line so that the front
left camera is each DISTANCES metres from the sign (Gazebo's set_pose service); and saves
/sensors/camera/front_left/image_raw as road_sign_<m>m.png. Stops the launch by its
process group.
"""

import argparse
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

SIGN_X = 25.0       # m east: the road world's stop sign (bench.yaml stop_signs)
CAMERA_X = 1.75     # m: the front cameras ahead of base_link (vehicle.yaml camera_left_link)
DISTANCES = (40.0, 30.0, 20.0, 15.0, 10.0, 7.0, 5.0)


def car_x(distance: float) -> float:
    """Where base_link goes for the camera to be this far from the sign."""
    return SIGN_X - CAMERA_X - distance


def set_pose_request(x: float, y: float = 0.0, z: float = 0.05) -> str:
    """gz.msgs.Pose text for the car, called aav (gazebo.launch.py), facing east."""
    return (f'name: "aav", position: {{x: {x:.3f}, y: {y:.3f}, z: {z:.3f}}}, '
            'orientation: {w: 1.0}')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    p.add_argument('--out', type=Path, default=Path.home() / 'aav-models' / 'frames')
    p.add_argument('--log', default='/tmp/aav-sim-frames.log')
    args = p.parse_args(argv)
    out = args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)
    # A private ROS domain and Gazebo partition, on this computer only, before rclpy starts.
    os.environ.setdefault('ROS_DOMAIN_ID', str(random.randint(150, 230)))
    os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    os.environ.setdefault('GZ_IP', '127.0.0.1')
    os.environ.setdefault('GZ_PARTITION', f'sim_frames_{os.environ["ROS_DOMAIN_ID"]}')
    os.environ.pop('ROS_STATIC_PEERS', None)

    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
    import cv2
    from cv_bridge import CvBridge

    print(f"Starting Gazebo's road world on ROS domain {os.environ['ROS_DOMAIN_ID']}, "
          f"partition {os.environ['GZ_PARTITION']} (log {args.log})", flush=True)
    log = open(args.log, 'w')
    launch = subprocess.Popen(
        ['ros2', 'launch', 'aav_bringup', 'sim.launch.py', 'world:=road', 'gui:=false',
         'rviz:=false', 'nav:=false', 'lidar:=false', 'radar:=false', 'watchdog:=false'],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('sim_frames')
    latest = {}
    node.create_subscription(Image, '/sensors/camera/front_left/image_raw',
                             lambda m: latest.update(msg=m, at=time.monotonic()),
                             qos_profile_sensor_data)
    saved = 0
    try:
        deadline = time.monotonic() + 180.0
        while 'msg' not in latest and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.5)
        if 'msg' not in latest:
            print('No picture from the camera in 180 s', file=sys.stderr)
            return 1
        bridge = CvBridge()
        for distance in DISTANCES:
            x = car_x(distance)
            ok = False
            for _ in range(3):      # a busy computer may drop the first call
                r = subprocess.run(
                    ['gz', 'service', '-s', '/world/aav/set_pose', '--reqtype', 'gz.msgs.Pose',
                     '--reptype', 'gz.msgs.Boolean', '--timeout', '3000',
                     '--req', set_pose_request(x)], capture_output=True, text=True)
                if 'data: true' in r.stdout:
                    ok = True
                    break
            if not ok:
                print(f'  {distance:g} m: set_pose failed ({r.stdout.strip()} '
                      f'{r.stderr.strip()[:200]})', flush=True)
                continue
            moved = time.monotonic()
            while time.monotonic() < moved + 2.0 or latest['at'] < moved + 1.5:
                rclpy.spin_once(node, timeout_sec=0.2)
            frame = bridge.imgmsg_to_cv2(latest['msg'], 'bgr8')
            path = out / f'road_sign_{distance:04.1f}m.png'
            cv2.imwrite(str(path), frame)
            saved += 1
            print(f'  {path.name}: the car at x = {x:.2f} m', flush=True)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
        os.killpg(launch.pid, signal.SIGINT)
        try:
            launch.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
        log.close()
    return 0 if saved == len(DISTANCES) else 1


if __name__ == '__main__':
    sys.exit(main())
