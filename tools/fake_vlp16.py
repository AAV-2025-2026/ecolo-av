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

The packet, from Velodyne's VLP-16 manual (single return, "strongest"), 1206 bytes:
  12 blocks of 100 bytes: flag 0xFFEE, azimuth (uint16, 0.01 degree), then 32 channels of
      3 bytes: distance (uint16, 2 mm) and reflectivity (uint8). Channels 0-15 are the 16
      lasers' first firing, 16-31 their second, half a block's turn later
  timestamp (uint32, microseconds past the hour), return mode 0x37, product 0x22 (VLP-16)
All little-endian. At 600 rpm a block turns 0.398 degrees, and 754 packets make a second.
Azimuth 0 is straight ahead; it grows clockwise (to the right), as the driver reads it.

No ROS: it only sends UDP. Standard library only.
"""

import argparse
import math
import socket
import struct
import time

# The VLP-16's lasers, in firing order: their angle above the horizon, degrees.
ELEVATIONS = (-15, 1, -13, 3, -11, 5, -9, 7, -7, 9, -5, 11, -3, 13, -1, 15)
BLOCKS = 12
FIRING_US = 55.296                  # one firing of all 16 lasers
RPM = 600.0
DEG_PER_US = RPM * 360.0 / 60.0 / 1e6
BLOCK_DEG = 2 * FIRING_US * DEG_PER_US          # 0.398 degrees: two firings a block
PACKET_DEG = BLOCKS * BLOCK_DEG                 # 4.78 degrees a packet
PACKETS_PER_S = RPM / 60.0 * 360.0 / PACKET_DEG     # 754
RETURN_STRONGEST, PRODUCT_VLP16 = 0x37, 0x22
DISTANCE_UNIT = 0.002               # m


def scene_distance(bearing_deg, ahead, width, ring):
    """Return the scene's distance (m) at a bearing (degrees, clockwise from ahead)."""
    bearing = (bearing_deg + 180.0) % 360.0 - 180.0
    half = math.degrees(math.atan2(width / 2.0, ahead))
    return ahead if abs(bearing) <= half else ring


def packet(azimuth_deg, distance, timestamp_us, reflectivity=100):
    """
    Return one VLP-16 data packet, 1206 bytes, whose first block is at azimuth_deg.

    distance(bearing_deg, elevation_deg) gives each laser's range in metres; 0 means no
    return (the driver leaves the point out).
    """
    out = bytearray()
    for block in range(BLOCKS):
        azimuth = (azimuth_deg + block * BLOCK_DEG) % 360.0
        out += b'\xff\xee' + struct.pack('<H', int(round(azimuth * 100)) % 36000)
        for firing in range(2):
            bearing = azimuth + firing * BLOCK_DEG / 2.0
            for elevation in ELEVATIONS:
                metres = distance(bearing, elevation)
                out += struct.pack('<HB', int(round(metres / DISTANCE_UNIT)), reflectivity)
    out += struct.pack('<IBB', timestamp_us % 3_600_000_000, RETURN_STRONGEST, PRODUCT_VLP16)
    return bytes(out)


def decode(data):
    """Return (azimuth_deg, laser index, distance_m) for each return in a packet: for tests."""
    if len(data) != 1206:
        raise ValueError(f'a VLP-16 packet is 1206 bytes, not {len(data)}')
    points = []
    for block in range(BLOCKS):
        base = block * 100
        if data[base:base + 2] != b'\xff\xee':
            raise ValueError(f'block {block} has no 0xFFEE flag')
        (azimuth,) = struct.unpack_from('<H', data, base + 2)
        for channel in range(32):
            raw, _ = struct.unpack_from('<HB', data, base + 4 + 3 * channel)
            points.append((azimuth / 100.0, channel % 16, raw * DISTANCE_UNIT))
    return points


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

    def distance(bearing, _elevation):
        return scene_distance(bearing, args.ahead, args.width, args.ring)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f'a VLP-16 at {RPM:.0f} rpm -> {args.host}:{args.port}: a post {args.width} m wide '
          f'{args.ahead} m ahead, the rest {args.ring} m away. Ctrl-C stops it.')
    start, sent, azimuth = time.monotonic(), 0, 0.0
    try:
        while not args.seconds or time.monotonic() - start < args.seconds:
            # Keep to the real rate: as many packets as the time so far allows.
            due = int((time.monotonic() - start) * PACKETS_PER_S)
            while sent < due:
                sock.sendto(packet(azimuth, distance, int(time.time() * 1e6)),
                            (args.host, args.port))
                azimuth = (azimuth + PACKET_DEG) % 360.0
                sent += 1
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    print(f'sent {sent} packets ({sent / PACKETS_PER_S * RPM / 60.0:.0f} turns)')


if __name__ == '__main__':
    main()
