import importlib.util
import json
from pathlib import Path

from aav_legacy.legacy_protocol import (
    crc8, encoder_counts, EncoderSpeed, FRAME_V2_LEN, FrameV2, LegacyMapping, metres_per_count,
    pack_frame, pack_frame_v2, stop_command, to_legacy, unpack_frame, unpack_frame_v2)
import pytest

ROOT = Path(__file__).resolve().parents[4]
# The wheel encoder's packet, as the Pico 2's Rust (crate wheel-encoder) checks it too.
ENCODER_VECTORS = ROOT / 'firmware/udp/wheel_encoder_vectors.txt'

M = LegacyMapping(max_steering_angle=0.5, full_throttle_speed=3.0)


def test_frame_layout_and_checksum():
    frame = pack_frame(0.5, -0.25, 0.0)
    assert len(frame) == 13
    assert frame[12] == sum(frame[:12]) & 0xFF
    assert unpack_frame(frame) == pytest.approx((0.5, -0.25, 0.0))


def test_values_are_clamped():
    assert unpack_frame(pack_frame(2.0, -3.0, 9.0)) == pytest.approx((1.0, -1.0, 1.0))


def test_bad_checksum_is_rejected():
    frame = bytearray(pack_frame(0.1, 0.2, 0.0))
    frame[0] ^= 1
    with pytest.raises(ValueError):
        unpack_frame(bytes(frame))


def test_driving_maps_to_open_loop_throttle():
    s, v, a = to_legacy(1.5, 0.25, M)
    assert (s, v, a) == pytest.approx((0.5, 0.5, 0.0))


def test_standing_still_holds_the_brake():
    s, v, a = to_legacy(0.0, 0.0, M)
    assert v == 0.0 and a < -0.05


def test_creep_is_not_lost_in_the_firmware_deadband():
    _, v, _ = to_legacy(0.06, 0.0, M)
    assert v >= 0.03


def test_stale_stop_brakes_fully():
    _, v, a = stop_command(M)
    assert v == 0.0 and a == -1.0


def test_encoder_packet():
    assert encoder_counts((-3).to_bytes(4, 'big', signed=True)) == -3
    with pytest.raises(ValueError):
        encoder_counts(b'\x00\x01')


def test_encoder_packet_matches_the_rust_firmware():
    lines = [line.split() for line in ENCODER_VECTORS.read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    assert len(lines) >= 10
    for spokes, packet in lines:
        assert encoder_counts(bytes.fromhex(packet)) == int(spokes)


def test_metres_per_count():
    assert metres_per_count(0.30, 8) == pytest.approx(0.1178, abs=1e-4)


def jrk_target(s):
    """Return the ESP32's steering Jrk target for a frame value (ros2_handler.cpp:35-38)."""
    return 1950 + s * 1950 if s <= 0 else 1950 + s * (3500 - 1950)


def test_steering_has_the_same_gain_both_ways():
    m = LegacyMapping(max_steering_angle=0.5, steering_sign=-1.0)
    for angle in (0.1, 0.25, 0.5):
        left = jrk_target(to_legacy(1.0, angle, m)[0])
        right = jrk_target(to_legacy(1.0, -angle, m)[0])
        assert 1950 - left == pytest.approx(right - 1950)
    assert jrk_target(to_legacy(1.0, 0.5, m)[0]) == pytest.approx(400)
    assert jrk_target(to_legacy(1.0, -0.5, m)[0]) == pytest.approx(3500)


def feed(enc, start, end, counts=1):
    """Send one packet every 0.1 s from `start` up to `end`, like the Pico."""
    t = start
    while t < end - 1e-9:
        enc.add(t, counts)
        t += 0.1


def test_encoder_speed_from_steady_packets():
    enc = EncoderSpeed(metres_per_count=0.1, window=0.5, timeout=0.3)
    feed(enc, 0.0, 2.0, counts=2)
    assert enc.speed(1.95) == pytest.approx(2.0, rel=0.25)   # 2 counts * 0.1 m / 0.1 s


def test_parked_car_reads_zero():
    enc = EncoderSpeed(metres_per_count=0.1)
    feed(enc, 0.0, 1.0, counts=0)
    assert enc.speed(0.95) == 0.0


def test_silent_encoder_reads_nothing():
    enc = EncoderSpeed(metres_per_count=0.1, window=0.5, timeout=0.3)
    assert enc.speed(0.0) is None
    feed(enc, 0.0, 1.0, counts=2)
    assert enc.speed(1.5) is None           # 0.6 s since the last packet
    feed(enc, 2.0, 2.3, counts=2)
    assert enc.speed(2.25) is None          # back, but not a full window yet
    feed(enc, 2.3, 2.6, counts=2)
    assert enc.speed(2.55) == pytest.approx(2.0, rel=0.25)


# --- The Rust board's vectors (firmware/spine/crates/legacy-link) ---

ROOT = Path(__file__).resolve().parents[4]
VECTORS = ROOT / 'firmware/spine/crates/legacy-link/vectors.json'
GENERATOR = ROOT / 'firmware/spine/crates/legacy-link/gen_vectors.py'


def load_generator():
    spec = importlib.util.spec_from_file_location('legacy_gen_vectors', GENERATOR)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


@pytest.mark.skipif(not VECTORS.exists(), reason='not in a full checkout')
def test_rust_vectors_are_what_this_module_sends():
    """vectors.json holds this module's bytes: rerun gen_vectors.py after changing it."""
    gen = load_generator()
    doc = json.loads(VECTORS.read_text())
    assert [c['bytes'] for c in doc['cases']] == [list(f) for _, _, f in gen.CASES]
    assert doc['stream'] == list(gen.STREAM)


@pytest.mark.skipif(not VECTORS.exists(), reason='not in a full checkout')
def test_rust_vectors_decode_here():
    doc = json.loads(VECTORS.read_text())
    for case in doc['cases']:
        values = unpack_frame(bytes(case['bytes']))
        in_range = all(abs(v) <= 1.0 for v in values)  # False for NaN
        assert in_range == (case['cpp'] is not None), case['name']


@pytest.mark.skipif(not VECTORS.exists(), reason='not in a full checkout')
def test_rust_v2_vectors_are_what_this_module_sends():
    gen = load_generator()
    doc = json.loads(VECTORS.read_text())
    assert [c['bytes'] for c in doc['v2_cases']] == [list(f) for _, _, f, _ in gen.V2_CASES]
    assert doc['v2_stream'] == list(gen.V2_STREAM)


@pytest.mark.skipif(not VECTORS.exists(), reason='not in a full checkout')
def test_rust_v2_vectors_decode_here_as_in_the_firmware():
    doc = json.loads(VECTORS.read_text())
    for case in doc['v2_cases']:
        frame = bytes(case['bytes'])
        if case['error']:
            with pytest.raises(ValueError):
                unpack_frame_v2(frame)
            continue
        f = unpack_frame_v2(frame)
        assert (f.counter, f.armed, f.estop) == (case['counter'], case['armed'],
                                                 case['estop']), case['name']
        in_range = all(abs(v) <= 1.0 for v in (f.steering, f.speed, f.accel))
        assert in_range == (case['cpp'] is not None), case['name']


# --- Version 2 (TODO 50) ---


def test_crc8_is_the_can_frames_crc():
    # CRC-8/SAE-J1850's published check value, as aav.dbc's frames use.
    assert crc8(b'123456789') == 0x4B


def test_v2_layout():
    frame = pack_frame_v2(0.5, -0.25, 0.0, 200, armed=True, estop=False)
    assert len(frame) == FRAME_V2_LEN == 17
    assert frame[:2] == bytes([0xA5, 2])
    assert (frame[14], frame[15]) == (200, 0x01)
    assert frame[16] == crc8(frame[1:16])
    assert unpack_frame_v2(frame) == FrameV2(0.5, -0.25, 0.0, 200, True, False)
    assert pack_frame_v2(0, 0, -1, 0, armed=False, estop=True)[15] == 0x02


def test_v2_clamps_values_and_wraps_the_counter():
    f = unpack_frame_v2(pack_frame_v2(2.0, -3.0, 9.0, 256 + 7, True, False))
    assert (f.steering, f.speed, f.accel, f.counter) == (1.0, -1.0, 1.0, 7)


def test_v2_catches_every_one_and_two_bit_error():
    """CRC-8/SAE-J1850 over these 15 bytes: checked by trying them all."""
    frame = pack_frame_v2(0.2, 0.3, -0.1, 42, True, False)
    bits = range(8, FRAME_V2_LEN * 8)   # after the sync byte
    flipped = [bytearray(frame) for _ in bits]

    def flip(b, bit):
        b[bit // 8] ^= 0x80 >> (bit % 8)

    for b, bit in zip(flipped, bits):
        flip(b, bit)
        with pytest.raises(ValueError):
            unpack_frame_v2(bytes(b))
    for i in bits:
        for j in range(i + 1, FRAME_V2_LEN * 8):
            b = bytearray(frame)
            flip(b, i)
            flip(b, j)
            with pytest.raises(ValueError):
                unpack_frame_v2(bytes(b))


def test_v2_turns_down_a_v1_frame_and_unknown_flags():
    with pytest.raises(ValueError):
        unpack_frame_v2(pack_frame(0.0, 0.5, 0.0) + bytes(4))
    bad = bytearray(pack_frame_v2(0, 0, 0, 1, True, False))
    bad[15] = 0x80
    bad[16] = crc8(bytes(bad[1:16]))
    with pytest.raises(ValueError):
        unpack_frame_v2(bytes(bad))
