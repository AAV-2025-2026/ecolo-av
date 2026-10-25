"""can_load: the CAN bus's load, from the DBC's frames and rates."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import can_load as c  # noqa: E402
import pytest  # noqa: E402


def test_frame_lengths_on_the_wire():
    assert c.frame_bits(8, stuffing=False) == 111
    assert c.frame_bits(8) == 135              # the textbook worst case for 8 bytes
    assert c.frame_bits(2) == 75
    assert c.frame_bits(0, stuffing=False) == 47
    with pytest.raises(ValueError):
        c.frame_bits(9)


def test_the_contract_parses():
    frames, bitrate = c.parse_dbc(c.DBC.read_text())
    assert bitrate == 500_000
    by_id = {f.can_id: f for f in frames}
    assert by_id[0x100].name == 'DRIVE_CMD' and by_id[0x100].hz == 50
    assert by_id[0x010].size == 2 and by_id[0x010].hz == 10
    assert by_id[0x200].sender == 'WHEEL_L' and by_id[0x200].hz == 100
    assert by_id[0x201].hz == 100
    assert all(f.hz > 0 for f in frames), 'every frame says its rate ("at N Hz")'


def test_the_contract_leaves_room_on_the_bus():
    frames, bitrate = c.parse_dbc(c.DBC.read_text())
    _, share = c.load(frames, bitrate)
    # 0x010 2 B at 10 Hz; 0x100, 0x180 at 50; 0x181 at 10; the wheels 0x200, 0x201 at 100
    assert share == pytest.approx((10 * 75 + 310 * 135) / 500_000)    # 8.5%
    assert share < 0.3


def test_a_made_up_bus():
    text = """VERSION ""
CM_ "Classic CAN at 250 kbit/s.";
BO_ 1 A: 8 X
BO_ 2 B: 4 Y
CM_ BO_ 1 "Sent at 1000 Hz.";
CM_ BO_ 2 "No rate here.";
"""
    frames, bitrate = c.parse_dbc(text)
    assert bitrate == 250_000
    assert [(f.name, f.hz) for f in frames] == [('A', 1000.0), ('B', 0.0)]
    rows, share = c.load(frames, bitrate)
    assert share == pytest.approx(135_000 / 250_000)
    assert 'busy' in c.verdict(share)


def test_the_verdicts():
    assert 'plenty' in c.verdict(0.085)
    assert 'watch' in c.verdict(0.4)
    assert 'too busy' in c.verdict(0.8)


def test_the_report_has_every_frame_and_the_total():
    frames, bitrate = c.parse_dbc(c.DBC.read_text())
    text = c.report(frames, bitrate)
    for name in ('ESTOP_CMD', 'DRIVE_CMD', 'VEHICLE_FEEDBACK', 'WHEEL_SPEED_L', 'TOTAL'):
        assert name in text
    assert '8.5% busy' in text
    md = c.report(frames, bitrate, markdown=True)
    assert md.splitlines()[0].startswith('| ID | frame |')
    assert '| 0x200 | WHEEL_SPEED_L | WHEEL_L | 8 | 100 | 135 | 13.5 | 2.7 |' in md
