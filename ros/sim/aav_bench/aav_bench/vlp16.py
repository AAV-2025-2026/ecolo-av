"""
The Velodyne VLP-16's UDP data packet, byte for byte: for the pretend lidars.

mock_lidar (bench mode) and tools/fake_vlp16.py send these, so the stock velodyne driver
(aav_sensors sensors.launch.py lidar:=true) can't tell them from the roof's real lidar.

The packet, from Velodyne's VLP-16 manual (single return, "strongest"), 1206 bytes:
  12 blocks of 100 bytes: flag 0xFFEE, azimuth (uint16, 0.01 degree), then 32 channels of
      3 bytes: distance (uint16, 2 mm) and reflectivity (uint8). Channels 0-15 are the 16
      lasers' first firing, 16-31 their second, half a block's turn later
  timestamp (uint32, microseconds past the hour), return mode 0x37, product 0x22 (VLP-16)
All little-endian. At 600 rpm a block turns 0.398 degrees, and 754 packets make a second.
Azimuth 0 is straight ahead; it grows clockwise (to the right), as the driver reads it.
The distance is along the laser's beam, not along the ground.

No ROS imports, so the tests run anywhere.
"""

import struct

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
MAX_RAW = 0xffff                    # the farthest a uint16 holds: 131 m
FIRING = struct.Struct('<' + 'HB' * len(ELEVATIONS))


def packet(azimuth_deg, ranges, timestamp_us, reflectivity=100):
    """
    Return one VLP-16 data packet, 1206 bytes, whose first block is at azimuth_deg.

    ranges(bearing_deg) gives the 16 lasers' distances in metres at a bearing (degrees,
    clockwise from ahead), in ELEVATIONS' order; 0 means no return (the driver leaves the
    point out).
    """
    out = bytearray()
    for block in range(BLOCKS):
        azimuth = (azimuth_deg + block * BLOCK_DEG) % 360.0
        out += b'\xff\xee' + struct.pack('<H', int(round(azimuth * 100)) % 36000)
        for firing in range(2):
            values = []
            for metres in ranges(azimuth + firing * BLOCK_DEG / 2.0):
                values += (min(int(round(metres / DISTANCE_UNIT)), MAX_RAW), reflectivity)
            out += FIRING.pack(*values)
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


class Sender:
    """Keep to the real rate: send as many packets as the time since `start` allows."""

    def __init__(self, send, start):
        self.send, self.start = send, start
        self.sent, self.azimuth = 0, 0.0

    def catch_up(self, now, ranges, timestamp_us):
        """Send the packets due by `now` (seconds, the same clock as start); return how many."""
        due = int((now - self.start) * PACKETS_PER_S)
        # After a stall (a busy computer), skip ahead rather than flood: at most 0.1 s.
        if due - self.sent > PACKETS_PER_S / 10:
            skipped = due - self.sent - int(PACKETS_PER_S / 10)
            self.sent += skipped
            self.azimuth = (self.azimuth + skipped * PACKET_DEG) % 360.0
        count = 0
        while self.sent < due:
            self.send(packet(self.azimuth, ranges, timestamp_us))
            self.azimuth = (self.azimuth + PACKET_DEG) % 360.0
            self.sent += 1
            count += 1
        return count
