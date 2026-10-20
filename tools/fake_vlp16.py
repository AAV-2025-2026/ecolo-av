#!/usr/bin/env python3
"""
Pretend to be the roof's Velodyne VLP-16: send its UDP packets, of a made-up scene.

The stock velodyne driver (aav_sensors sensors.launch.py lidar:=true) can't tell these from
the real lidar, so the whole chain - driver, point cloud, lidar_scan, Nav2's costmap - can
be tried on a laptop, with distances we know:

    python3 tools/fake_vlp16.py                      # a post 6 m ahead, a ring at 15 m
    python3 tools/fake_vlp16.py --ahead 4 --width 2 --seconds 30

then, on the same computer:
    ros2 launch aav_sensors sensors.launch.py imu:=false gps:=false lidar:=true \
        lidar_ip:=127.0.0.1 lidar_port:=2369

The scene: a post `width` m wide, `ahead` m in front of the lidar (straight ahead, so it
fills the bearings within atan(width / 2 / ahead)), and everything else `ring` m away.
Every laser sees the same distance at a bearing, as if the post and the ring were tall.

The packet itself is aav_bench's (src/bench/aav_bench/aav_bench/vlp16.py), which bench
mode's mock_lidar sends too.

No ROS: it only sends UDP. Standard library only, and aav_bench's vlp16 module.
"""

import argparse
import math
from pathlib import Path
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/bench/aav_bench'))
from aav_bench.vlp16 import ELEVATIONS, PACKETS_PER_S, RPM, Sender  # noqa: E402, I100


def scene_distance(bearing_deg, ahead, width, ring):
    """Return the scene's distance (m) at a bearing (degrees, clockwise from ahead)."""
    bearing = (bearing_deg + 180.0) % 360.0 - 180.0
    half = math.degrees(math.atan2(width / 2.0, ahead))
    return ahead if abs(bearing) <= half else ring


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--host', default='127.0.0.1', help='where to send (this computer)')
    ap.add_argument('--port', type=int, default=2369,
                    help="UDP port: not the real lidar's 2368, so the two never mix")
    ap.add_argument('--ahead', type=float, default=6.0, help='m to the post ahead')
    ap.add_argument('--width', type=float, default=1.0, help="the post's width, m")
    ap.add_argument('--ring', type=float, default=15.0, help='m to everything else')
    ap.add_argument('--seconds', type=float, default=0.0, help='stop after; 0 = Ctrl-C')
    args = ap.parse_args()

    def ranges(bearing):
        return [scene_distance(bearing, args.ahead, args.width, args.ring)] * len(ELEVATIONS)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f'a VLP-16 at {RPM:.0f} rpm -> {args.host}:{args.port}: a post {args.width} m wide '
          f'{args.ahead} m ahead, the rest {args.ring} m away. Ctrl-C stops it.')
    start = time.monotonic()
    sender = Sender(lambda data: sock.sendto(data, (args.host, args.port)), start)
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            sender.catch_up(time.monotonic(), ranges, int(time.time() * 1e6))
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    sent = sender.sent
    print(f'sent {sent} packets ({sent / PACKETS_PER_S * RPM / 60.0:.0f} turns)')


if __name__ == '__main__':
    main()
