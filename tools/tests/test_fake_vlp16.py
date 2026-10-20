"""Tests for tools/fake_vlp16.py: its packets must be the VLP-16's, byte for byte."""

from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fake_vlp16 as v  # noqa: E402, I100


def test_the_rate_is_the_vlp16s_at_600_rpm():
    assert v.BLOCK_DEG == pytest.approx(0.398, abs=0.001)
    assert v.PACKETS_PER_S == pytest.approx(754, abs=1)


def test_a_packet_is_1206_bytes_ending_in_strongest_and_vlp16():
    data = v.packet(0.0, lambda b, e: 10.0, 123456)
    assert len(data) == 1206
    timestamp, mode, product = struct.unpack_from('<IBB', data, 1200)
    assert (timestamp, mode, product) == (123456, 0x37, 0x22)


def test_each_block_is_flagged_and_turns_by_one_block():
    data = v.packet(359.0, lambda b, e: 10.0, 0)
    azimuths = [struct.unpack_from('<H', data, 100 * i + 2)[0] for i in range(12)]
    assert all(data[100 * i:100 * i + 2] == b'\xff\xee' for i in range(12))
    assert azimuths[0] == 35900
    assert azimuths[3] == round((359.0 + 3 * v.BLOCK_DEG) % 360 * 100)   # wraps past 360
    assert all(0 <= a < 36000 for a in azimuths)


def test_distances_round_trip_in_2_mm_steps():
    points = v.decode(v.packet(0.0, lambda b, e: 6.0 + e / 1000.0, 0))
    assert len(points) == 12 * 32
    for azimuth, laser, metres in points:
        # Within half a 2 mm step: 5.985 m is sent as 5.984 m.
        assert abs(metres - (6.0 + v.ELEVATIONS[laser] / 1000.0)) <= v.DISTANCE_UNIT / 2 + 1e-9


def test_the_scene_has_a_post_ahead_and_a_ring():
    assert v.scene_distance(0.0, 6.0, 1.0, 15.0) == 6.0
    assert v.scene_distance(4.0, 6.0, 1.0, 15.0) == 6.0         # atan(0.5 / 6) = 4.76 deg
    assert v.scene_distance(5.0, 6.0, 1.0, 15.0) == 15.0
    assert v.scene_distance(356.0, 6.0, 1.0, 15.0) == 6.0       # just left of ahead
    assert v.scene_distance(180.0, 6.0, 1.0, 15.0) == 15.0


def test_decode_refuses_what_isnt_a_vlp16_packet():
    with pytest.raises(ValueError, match='1206 bytes'):
        v.decode(b'\x00' * 100)
    with pytest.raises(ValueError, match='0xFFEE'):
        v.decode(b'\x00' * 1206)
