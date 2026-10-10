"""Check the codec against the CRC standard, the DBC file and the shared test vectors."""

import json
from pathlib import Path
import re

from aav_spine import can_codec as cc
import pytest

ROOT = Path(__file__).resolve().parents[4]
DBC = ROOT / 'firmware/can/aav.dbc'
VECTORS = ROOT / 'firmware/can/test_vectors.json'


def test_crc_check_value():
    assert cc.crc8_sae_j1850(b'123456789') == 0x4B


@pytest.mark.parametrize('can_id', sorted(cc.FRAMES))
def test_round_trip(can_id):
    layout = cc.FRAMES[can_id]
    values = {n: (1 if s.length == 1 else 3 * s.scale) for n, s in layout.signals.items()
              if n != 'checksum'}
    back = cc.unpack(can_id, cc.pack(can_id, values))
    for name, value in values.items():
        assert back[name] == pytest.approx(value)


def test_saturates_instead_of_wrapping():
    data = cc.pack(cc.DRIVE_CMD_ID, {'target_speed': 100.0, 'steering_angle': -100.0})
    back = cc.unpack(cc.DRIVE_CMD_ID, data)
    assert back['target_speed'] == pytest.approx(32.767)
    assert back['steering_angle'] == pytest.approx(-3.2768)


def test_rejects_bad_frames():
    good = cc.pack(cc.VEHICLE_STATUS_ID, {'mode': 2})
    with pytest.raises(cc.FrameError):
        cc.unpack(cc.VEHICLE_STATUS_ID, good[:-1])
    with pytest.raises(cc.FrameError):
        cc.unpack(cc.VEHICLE_STATUS_ID, bytes([good[0] ^ 1]) + good[1:])
    with pytest.raises(cc.FrameError):
        cc.unpack(cc.VEHICLE_FEEDBACK_ID, good)   # right length, wrong ID
    with pytest.raises(KeyError):
        cc.pack(cc.DRIVE_CMD_ID, {'no_such_signal': 1})


def test_counter_step():
    assert cc.counter_step(15, 0) == 1
    assert cc.counter_step(4, 4) == 0
    assert cc.counter_step(None, 7) == 1


@pytest.mark.skipif(not DBC.exists(), reason='run from the monorepo')
def test_codec_matches_dbc():
    text = DBC.read_text()
    frames = {}
    current = None
    for line in text.splitlines():
        m = re.match(r'BO_ (\d+) (\w+): (\d+) \w+', line)
        if m:
            current = int(m.group(1))
            frames[current] = {'name': m.group(2), 'dlc': int(m.group(3)), 'signals': {}}
            continue
        m = re.match(r'\s+SG_ (\w+) : (\d+)\|(\d+)@1([+-]) \(([^,]+),([^)]+)\)', line)
        if m and current is not None:
            frames[current]['signals'][m.group(1)] = (
                int(m.group(2)), int(m.group(3)), m.group(4) == '-', float(m.group(5)),
                float(m.group(6)))
    assert set(frames) == set(cc.FRAMES)
    for can_id, layout in cc.FRAMES.items():
        dbc = frames[can_id]
        assert dbc['name'] == layout.name
        assert dbc['dlc'] == layout.dlc
        assert set(dbc['signals']) == set(layout.signals)
        for name, sig in layout.signals.items():
            start, length, signed, factor, offset = dbc['signals'][name]
            assert (start, length, signed) == (sig.start, sig.length, sig.signed), name
            assert factor == pytest.approx(sig.scale), name
            assert offset == 0.0


@pytest.mark.skipif(not VECTORS.exists(), reason='run from the monorepo')
def test_vectors_match_codec():
    for v in json.loads(VECTORS.read_text())['vectors']:
        assert cc.pack(v['id'], v['values']).hex() == v['data_hex'], v['name']
        back = cc.unpack(v['id'], bytes.fromhex(v['data_hex']))
        for name, value in v['decoded'].items():
            assert back[name] == pytest.approx(value), (v['name'], name)
