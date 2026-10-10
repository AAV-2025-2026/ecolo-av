from aav_legacy.legacy_protocol import (
    encoder_counts, LegacyMapping, metres_per_count, pack_frame, stop_command, to_legacy,
    unpack_frame)
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
