"""Tests for aav_bench's VLP-16 packets: they must be the real lidar's, byte for byte."""

import struct

from aav_bench import vlp16
import pytest


def test_the_rate_is_the_vlp16s_at_600_rpm():
    assert vlp16.BLOCK_DEG == pytest.approx(0.398, abs=0.001)
    assert vlp16.PACKETS_PER_S == pytest.approx(754, abs=1)


def test_a_packet_is_1206_bytes_ending_in_strongest_and_vlp16():
    data = vlp16.packet(0.0, lambda b: [10.0] * 16, 123456)
    assert len(data) == 1206
    timestamp, mode, product = struct.unpack_from('<IBB', data, 1200)
    assert (timestamp, mode, product) == (123456, 0x37, 0x22)


def test_each_block_is_flagged_and_turns_by_one_block():
    data = vlp16.packet(359.0, lambda b: [10.0] * 16, 0)
    azimuths = [struct.unpack_from('<H', data, 100 * i + 2)[0] for i in range(12)]
    assert all(data[100 * i:100 * i + 2] == b'\xff\xee' for i in range(12))
    assert azimuths[0] == 35900
    assert azimuths[3] == round((359.0 + 3 * vlp16.BLOCK_DEG) % 360 * 100)   # wraps past 360
    assert all(0 <= a < 36000 for a in azimuths)


def test_distances_round_trip_in_2_mm_steps():
    ranges = [6.0 + e / 1000.0 for e in vlp16.ELEVATIONS]
    points = vlp16.decode(vlp16.packet(0.0, lambda b: ranges, 0))
    assert len(points) == 12 * 32
    for azimuth, laser, metres in points:
        # Within half a 2 mm step: 5.985 m is sent as 5.984 m.
        assert abs(metres - ranges[laser]) <= vlp16.DISTANCE_UNIT / 2 + 1e-9


def test_decode_refuses_what_isnt_a_vlp16_packet():
    with pytest.raises(ValueError, match='1206 bytes'):
        vlp16.decode(b'\x00' * 100)
    with pytest.raises(ValueError, match='0xFFEE'):
        vlp16.decode(b'\x00' * 1206)


def test_a_far_return_is_held_at_the_farthest_a_packet_can_say():
    points = vlp16.decode(vlp16.packet(0.0, lambda b: [500.0] * 16, 0))
    assert {m for _, _, m in points} == {vlp16.MAX_RAW * vlp16.DISTANCE_UNIT}


def test_the_sender_keeps_to_the_real_rate_and_skips_a_stall():
    sent = []
    sender = vlp16.Sender(sent.append, start=100.0)
    assert sender.catch_up(101.0, lambda b: [0.0] * 16, 0) == int(vlp16.PACKETS_PER_S / 10)
    later = int(1.01 * vlp16.PACKETS_PER_S) - int(vlp16.PACKETS_PER_S)
    assert sender.catch_up(101.01, lambda b: [0.0] * 16, 0) == later    # 7 or 8
    assert sender.sent == int(1.01 * vlp16.PACKETS_PER_S)          # the stall's skipped too
    first = [vlp16.decode(p)[0][0] for p in sent[-2:]]
    assert (first[1] - first[0]) % 360 == pytest.approx(vlp16.PACKET_DEG, abs=0.01)
