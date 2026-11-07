"""What the bridge reports it wrote (/control/car/link_frame): the bookkeeping. No ROS."""

from aav_legacy.legacy_protocol import (CAL_MODE_JOG, crc8, pack_frame, pack_frame_v2,
                                        pack_frame_v3)
from aav_legacy.link_report import frame_fields, LinkReport
import pytest


def test_every_version_decodes_from_its_own_bytes():
    v1 = frame_fields(pack_frame(0.25, 0.5, -0.5))
    assert (v1['version'], v1['counter'], v1['armed'], v1['estop']) == (1, 0, False, False)
    assert (v1['steering'], v1['speed'], v1['accel']) == (0.25, 0.5, -0.5)

    frame = pack_frame_v2(-0.25, 0.0, -1.0, 41, True, False)
    v2 = frame_fields(frame)
    assert (v2['version'], v2['counter'], v2['armed'], v2['estop']) == (2, 41, True, False)
    assert v2['check'] == frame[-1] == crc8(frame[1:16])
    assert (v2['cal_mode'], v2['jog_target']) == (0, 0)

    v3 = frame_fields(pack_frame_v3(0.0, 0.0, -1.0, 7, False, True, CAL_MODE_JOG, 1800))
    assert (v3['version'], v3['counter'], v3['estop']) == (3, 7, True)
    assert (v3['cal_mode'], v3['jog_target']) == (CAL_MODE_JOG, 1800)


def test_a_bad_frame_is_refused_not_reported():
    frame = bytearray(pack_frame_v2(0.1, 0.2, 0.0, 1, True, False))
    frame[5] ^= 0x01
    with pytest.raises(ValueError):
        frame_fields(bytes(frame))
    with pytest.raises(ValueError):
        frame_fields(b'\xa5\x02\x00')


def test_same_counter_different_values_have_different_checks():
    # Stop frames repeat the counter with new values: only counter + check tell them apart.
    go = frame_fields(pack_frame_v2(0.0, 0.3, 0.0, 9, True, False))
    stop = frame_fields(pack_frame_v2(0.0, 0.0, -1.0, 9, True, False))
    assert go['counter'] == stop['counter'] and go['check'] != stop['check']


def test_only_whole_writes_count():
    r = LinkReport()
    frame = pack_frame_v2(0.0, 0.0, 0.0, 1, True, False)
    assert r.wrote(frame, len(frame)) and r.wrote(frame, None)
    assert not r.wrote(frame, 5)
    r.failed()
    assert (r.written, r.write_errors) == (2, 2)
    f = r.fields(frame)
    assert (f['written'], f['write_errors']) == (2, 2)


def test_counts_wrap_like_a_uint32():
    r = LinkReport()
    r.written = 2 ** 32 + 3
    assert r.fields(pack_frame(0.0, 0.0, 0.0))['written'] == 3


def test_samples_keep_their_rate_through_jitter():
    r = LinkReport(rate_hz=10.0)
    ticks = [i * 0.02 + (0.004 if i % 3 else 0.0) for i in range(500)]   # 50 Hz, 10 s
    samples = [t for t in ticks if r.due(t)]
    assert 98 <= len(samples) <= 101


def test_a_gap_starts_the_samples_again():
    r = LinkReport(rate_hz=10.0)
    assert r.due(0.0) and not r.due(0.05) and r.due(0.1)
    assert r.due(5.0)                   # the port was closed for 5 s: one sample, not 49
    assert not r.due(5.02)


def test_rate_zero_samples_nothing_but_still_counts():
    r = LinkReport(rate_hz=0.0)
    assert not any(r.due(t / 50) for t in range(100))
    frame = pack_frame(0.0, 0.0, 0.0)
    r.wrote(frame, len(frame))
    assert r.written == 1
    with pytest.raises(ValueError):
        LinkReport(rate_hz=-1.0)
