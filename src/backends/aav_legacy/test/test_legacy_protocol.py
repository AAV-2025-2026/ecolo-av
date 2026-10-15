import importlib.util
import json
from pathlib import Path

from aav_legacy.legacy_protocol import (
    encoder_counts, EncoderSpeed, LegacyMapping, metres_per_count, pack_frame, stop_command,
    to_legacy, unpack_frame)
import pytest

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
