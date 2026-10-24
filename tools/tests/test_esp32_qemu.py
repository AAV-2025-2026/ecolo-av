"""esp32_qemu: reading the firmware's log, and judging a heartbeat cycle from it."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import esp32_qemu as q  # noqa: E402
from aav_legacy.legacy_protocol import unpack_frame_v2  # noqa: E402,I100
import pytest  # noqa: E402

# Lines as the firmware prints them on UART0, colour codes and all.
EVENT = ('\x1b[32mINFO - EVENT t=1415 mode=Manual armed=false estop=true throttle=0.00 '
         'brake=1.00 reverse=false steer=0.000 faults=0x0001\x1b[0m')
DEVICES = '\x1b[32mINFO - DEVICES t=1415 steering=1950 brake=3500 dac=0 expander=0xffff\x1b[0m'


def status(t, *, armed, throttle, brake, faults=0, kind='STATUS', mode=None):
    """Return a STATUS or EVENT line, as the firmware writes it."""
    mode = mode or ('Computer' if armed else 'Manual')
    return (f'INFO - {kind} t={t} mode={mode} armed={str(armed).lower()} estop=false '
            f'throttle={throttle:.2f} brake={brake:.2f} reverse=false steer=0.000 '
            f'faults={faults:#06x}')


def devices(t, brake, dac):
    return f'INFO - DEVICES t={t} steering=1950 brake={brake} dac={dac} expander=0xffff'


def firmware(timeout_after=110, latched=True, brake_on_timeout=True):
    """
    Return the lines of one cycle, with the host seeing each 1 ms after it was printed.

    The firmware's clock is the host's minus 100 s. Drive from 1.0 s to 2.0 s (the last
    frame), silence, frames again from 2.6 s to 3.2 s.
    """
    texts = []
    for t in range(1000, 2001, 200):
        texts.append((t, status(t, armed=True, throttle=0.2, brake=0.0)))
        texts.append((t, devices(t, 400, min(140, (t - 1000) // 2 + 6))))
    trip = 2000 + timeout_after
    brake = 1.0 if brake_on_timeout else 0.0
    texts.append((trip, status(trip, armed=False, throttle=0.0, brake=brake,
                               faults=q.CMD_TIMEOUT, kind='EVENT')))
    texts.append((trip, devices(trip, q.BRAKE_FULL if brake_on_timeout else 400, 0)))
    for t in range(2600, 3201, 200):
        if latched:
            texts.append((t, status(t, armed=False, throttle=0.0, brake=1.0,
                                    faults=q.CMD_TIMEOUT)))
        else:
            texts.append((t, status(t, armed=True, throttle=0.2, brake=0.0)))
    return [q.parse_line(text, 100 + t / 1000 + 0.001) for t, text in texts]


CYCLE = q.Cycle(stop_from=100.7, drive_from=101.0, last_frame=102.0, resume_from=102.6,
                end=103.2)


def judged(**kwargs):
    lines = firmware(**kwargs)
    return q.judge(CYCLE, lines, q.ClockMap.fit(lines))


def test_lines_are_read_with_their_numbers():
    e = q.parse_line(EVENT, 5.0)
    assert (e.kind, e.t, e.host) == ('EVENT', 1415, 5.0)
    assert e.get('faults') == q.CMD_TIMEOUT
    assert e.get('brake') == 1.0 and e.get('throttle') == 0.0
    assert e.get('armed') is False and e.get('mode') == 'Manual'
    d = q.parse_line(DEVICES, 5.0)
    assert (d.get('brake'), d.get('dac'), d.get('expander')) == (3500, 0, 0xFFFF)
    assert q.parse_line('I (833) boot: Loaded app', 5.0).kind == 'TEXT'


def test_the_clocks_map_through_the_fastest_line():
    lines = [q.parse_line(status(t, armed=False, throttle=0, brake=1), 100 + t / 1000 + lag)
             for t, lag in [(0, 0.004), (200, 0.001), (400, 0.003)]]
    clock = q.ClockMap.fit(lines)
    assert clock.offset == pytest.approx(100.001)
    assert clock.to_firmware_ms(100.5) == pytest.approx(499)
    assert clock.rate == pytest.approx(0.4 / 0.399)


def test_a_good_cycle_passes():
    r = judged()
    assert r.ok, r.problems
    assert r.drove and r.dac_rose == 140
    assert r.timeout_fw_ms == pytest.approx(111)    # 110 ms, and the 1 ms lag
    assert r.timeout_host_ms == pytest.approx(111)
    assert r.brake_full_fw_ms == pytest.approx(111)
    assert r.fault_bit and r.stopped and r.latched


def test_a_late_timeout_fails():
    r = judged(timeout_after=250)
    assert not r.ok
    assert any('not 100-200' in p for p in r.problems)


def test_a_timeout_that_does_not_brake_fails():
    r = judged(brake_on_timeout=False)
    assert not r.stopped
    assert any('did not stop the car' in p for p in r.problems)
    assert any('never got 3500' in p for p in r.problems)


def test_driving_again_without_a_stop_fails():
    r = judged(latched=False)
    assert r.latched is False
    assert any('without a stop drove again' in p for p in r.problems)


def test_no_timeout_at_all_fails():
    lines = [ln for ln in firmware() if not (ln.kind == 'EVENT')]
    r = q.judge(CYCLE, lines, q.ClockMap.fit(lines))
    assert any('no timeout event' in p for p in r.problems)


def test_the_frames_are_the_bridges():
    # What legacy_uart_bridge sends: 0.6 m/s straight, and its stale stop.
    m = q.LegacyMapping()
    assert q.to_legacy(*q.DRIVE, m) == pytest.approx((0.0, 0.2, 0.0))
    assert q.stop_command(m) == (0.0, 0.0, -1.0)
    assert len(q.pack_frame(*q.stop_command(m))) == 13


def test_the_table_has_a_row_per_cycle():
    lines = firmware()
    text = q.table([judged(), judged(latched=False)], q.ClockMap.fit(lines))
    rows = [r for r in text.splitlines() if r.startswith('| ') and r[2].isdigit()]
    assert len(rows) == 2
    assert rows[0].endswith('| pass |') and rows[1].endswith('| FAIL |')


# --- Version 2: the Orin's counter (TODO 50) ---

def link(t, *, bad=0, repeats=0):
    return (f'INFO - LINK t={t} frames=100 bad={bad} skipped=0 repeats={repeats} '
            f'counter=7')


def with_links(lines, before, after):
    """Add a LINK line before the gap (at 1.8 s) and one after it (at 2.8 s)."""
    extra = [q.parse_line(link(1800, **before), 101.8 + 0.001),
             q.parse_line(link(2800, **after), 102.8 + 0.001)]
    return sorted(lines + extra, key=lambda ln: ln.host)


def test_link_lines_are_read():
    ln = q.parse_line(link(5, bad=3), 1.0)
    assert (ln.kind, ln.get('bad'), ln.get('counter')) == ('LINK', 3, 7)


@pytest.mark.parametrize('kind,field', [('frozen', 'repeats'), ('bad_crc', 'bad')])
def test_a_gap_of_frames_must_be_counted(kind, field):
    cycle = q.Cycle(100.7, 101.0, 102.0, 102.6, 103.2, kind=kind, gap_frames=30)
    lines = with_links(firmware(), {field: 1}, {field: 31})
    r = q.judge(cycle, lines, q.ClockMap.fit(lines))
    assert r.ok, r.problems
    assert r.counted == 30
    lines = with_links(firmware(), {field: 1}, {field: 11})
    r = q.judge(cycle, lines, q.ClockMap.fit(lines))
    assert any(f'only 10 counted as {field}' in p for p in r.problems)


def test_the_orins_frames_move_freeze_or_break():
    orin = q.Orin()
    values = q.to_legacy(*q.DRIVE, q.LegacyMapping())
    moving, frozen = orin.frames(values), orin.frames(values, move=False)
    counters = [unpack_frame_v2(f()).counter for f in (moving, moving, frozen, frozen)]
    assert counters == [1, 2, 2, 2]
    with pytest.raises(ValueError):
        unpack_frame_v2(orin.frames(values, bad_crc=True)())
