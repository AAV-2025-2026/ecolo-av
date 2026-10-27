"""VEDirect: blocks, checksums, and which block arrived last."""

from aav_battery_victron.VEDirect import VEDirect


def frame(fields):
    """VE.Direct text for one block, with a checksum that makes it sum to 0."""
    body = ''.join(f'\r\n{key}\t{value}' for key, value in fields)
    total = sum(map(ord, body + '\r\nChecksum\t')) % 256
    return (body + '\r\nChecksum\t' + chr((256 - total) % 256) + '\r').encode('latin-1')


def feed(vd, data):
    blocks = []
    for byte in data:
        vd.process_byte(byte, lambda: blocks.append(dict(vd.last_block)))
    return blocks


def test_a_good_block_is_kept_and_a_bad_one_is_not():
    vd = VEDirect()
    assert feed(vd, frame([('V', '51200'), ('I', '-1500'), ('SOC', '987'), ('VS', '12100')]))
    assert vd.data['V'] == '51200' and vd.data['SOC'] == '987'
    bad = bytearray(frame([('V', '1')]))
    bad[3] ^= 1                              # one byte changed: the checksum fails
    assert feed(vd, bytes(bad)) == []
    assert vd.data['V'] == '51200'


def test_last_block_is_only_the_newest_block():
    # The history block keeps the readings in data (merged), but last_block shows it
    # brought none: battery_monitor then publishes nothing for it.
    vd = VEDirect()
    feed(vd, frame([('V', '51200'), ('I', '-1500'), ('SOC', '987'), ('VS', '12100')]))
    blocks = feed(vd, frame([('H1', '-1000'), ('H2', '-500')]))
    assert blocks == [{'H1': '-1000', 'H2': '-500'}]
    assert 'V' in vd.data and 'V' not in vd.last_block
