"""link_check: the Pi's frames against the ESP32's counts, on made-up runs. No ROS."""

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'ros/can_bridge/aav_legacy'))
from aav_legacy.legacy_protocol import pack_frame_v2  # noqa: E402
import link_check as lc  # noqa: E402
import pytest  # noqa: E402

try:
    from aav_interfaces.msg import LinkFrame, UplinkHealth  # our messages: tools/ros.sh
    from rclpy.serialization import serialize_message
    import rosbag2_py
    HAVE_OURS = True
except ImportError:
    HAVE_OURS = False

# Not importorskip: the tests above run everywhere.
needs_ours = pytest.mark.skipif(not HAVE_OURS,
                                reason='needs rosbag2_py and aav_interfaces: tools/ros.sh')

GOLDEN = ROOT / 'firmware/status/golden.jsonl'


def drive(seconds=10.0, moving=True, lose=(), extra=0, bad_at=None, esp_rate=10.0,
          esp_start=0.0, stop_every=None):
    """
    Return (Pi samples, ESP32 lines): a joystick drive, as both sides would report it.

    The bridge writes at 50 Hz, the mux passes a command (counter + 1) at 20 Hz, the Pi
    samples one frame in five, the ESP32 reports at esp_rate. `lose`: frame numbers that
    never arrive. `extra`: frames a second writer adds, each second. `bad_at`: a time from
    which the ESP32 counts bad frames. `stop_every`: every nth command is a stop frame
    with the same counter (as the relay's stop frames).
    """
    samples, lines = [], []
    frames = bad = 0
    last = None
    seq = 0
    next_status = esp_start
    for n in range(1, int(seconds * 50) + 1):
        t = n / 50
        counter = int(t * 20) & 0xFF
        speed = 0.3 * math.sin(t) if moving else 0.0
        steering = 0.2 * math.cos(t * 0.7) if moving else 0.0
        accel = 0.0 if moving else -1.0
        if stop_every and int(t * 20) % stop_every == 0:
            speed, accel = 0.0, -1.0
        frame = pack_frame_v2(steering, speed, accel, counter, moving, False)
        if n % 5 == 0:
            samples.append(lc.pi_sample(2, counter, frame[-1], steering, speed, accel, n, 0, t))
        if n not in lose:
            frames += 1
            last = {'v': 2, 'counter': counter, 'check': frame[-1], 'steer': round(steering, 3),
                    'speed': round(speed, 3), 'accel': round(accel, 3), 'age_ms': 5}
        if extra and n % (50 // extra) == 0:
            frames += 1
        if bad_at is not None and t >= bad_at and n % 25 == 0:
            bad += 1
        if t >= next_status:
            seq += 1
            lines.append({'t': 'status', 'schema': 1, 'seq': seq, 'up_ms': int(t * 1000) + 5000,
                          'rx': last, 'link': {'frames': frames + 1000, 'bad': bad,
                                               'skipped': 3, 'repeats': 0}})
            next_status += 1.0 / esp_rate
    text = '\n'.join(json.dumps(line) for line in lines)
    return samples, lc.esp32_lines(text)[0]


def verdicts(report):
    return report['verdict'], [h['verdict'] for h in report['hops']]


def test_a_clean_drive_passes():
    samples, lines = drive()
    r = lc.check(samples, lines)
    assert verdicts(r)[0] == lc.PASS, lc.text(r)
    assert r['anchors'] >= 10
    assert 'sampled 100' in r['hops'][0]['reasons'][0]


def test_the_pass_says_how_small_a_loss_it_could_miss():
    samples, lines = drive()
    hidden = lc.hidden_loss(lc.anchors(samples, lines))
    assert 0 < hidden <= 10                            # one sample in five, 50 Hz
    assert f'up to {hidden} frames' in lc.check(samples, lines)['hops'][1]['reasons'][1]
    samples, lines = drive(lose=set(range(240, 240 + hidden + 1)))
    assert lc.check(samples, lines)['verdict'] == lc.FAIL


def test_status_lines_at_another_rate_and_phase_still_pass():
    samples, lines = drive(esp_rate=7.0, esp_start=0.013)
    assert lc.check(samples, lines)['verdict'] == lc.PASS


def test_stop_frames_that_repeat_a_counter_are_told_apart():
    samples, lines = drive(stop_every=3)
    assert lc.check(samples, lines)['verdict'] == lc.PASS


def test_a_parked_car_is_never_a_pass():
    samples, lines = drive(moving=False)
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.NOT_TESTED, lc.text(r)
    assert 'never changed' in r['hops'][0]['reasons'][0]
    assert r['hops'][1]['verdict'] != lc.PASS


def test_lost_frames_fail():
    samples, lines = drive(lose=set(range(200, 230)))
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.FAIL, lc.text(r)
    assert 'lost' in ' '.join(r['hops'][1]['reasons'])


def test_a_second_writer_fails():
    samples, lines = drive(extra=5)
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.FAIL
    assert 'second writer' in ' '.join(r['hops'][1]['reasons'])


def test_bad_frames_fail():
    samples, lines = drive(bad_at=4.0)
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.FAIL
    assert 'turned down' in ' '.join(r['hops'][1]['reasons'])


def test_a_failed_write_fails():
    samples, lines = drive()
    samples[-1]['write_errors'] = 2
    assert lc.check(samples, lines)['hops'][0]['verdict'] == lc.FAIL


def test_a_good_frame_with_other_values_is_a_reporting_bug():
    samples, lines = drive()
    found = lc.anchors(samples, lines)
    k = found[3]['key']
    for line in lines:
        if line['rx'] and lc.key(line['rx']) == k:
            line['rx']['speed'] += 0.5
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.FAIL and 'reporting bug' in r['hops'][1]['reasons'][0]


def test_the_counter_alone_never_matches():
    samples, lines = drive()
    for line in lines:                        # same counters, other check bytes
        if line['rx']:
            line['rx']['check'] ^= 0xFF
    r = lc.check(samples, lines)
    assert r['verdict'] == lc.NOT_TESTED and r['anchors'] == 0


def test_without_the_esp32_it_is_not_tested():
    samples, _ = drive()
    r = lc.check(samples, [])
    assert verdicts(r) == (lc.NOT_TESTED, [lc.PASS, lc.NOT_TESTED, lc.NOT_TESTED])


def test_without_the_pi_it_is_not_tested():
    _, lines = drive()
    assert lc.check([], lines)['verdict'] == lc.NOT_TESTED


def test_an_esp32_restart_fails_and_a_bridge_restart_is_not_tested():
    samples, lines = drive()
    lines[40]['frames'] = 3
    assert lc.check(samples, lines)['verdict'] == lc.FAIL
    samples, lines = drive()
    samples[50]['written'] = 1
    assert lc.check(samples, lines)['hops'][0]['verdict'] == lc.NOT_TESTED


def test_recordings_at_different_times_are_not_tested():
    samples, _ = drive(seconds=5.0)
    _, lines = drive(seconds=10.0)
    later = [line for line in lines if line['seq'] > 60]
    assert lc.check(samples, later)['verdict'] == lc.NOT_TESTED


def test_the_golden_lines_read():
    lines, notes = lc.esp32_lines(GOLDEN.read_text(encoding='utf-8'))
    assert len(lines) == 2 and notes == []
    assert lines[0]['rx'] == {'version': 2, 'counter': 41, 'check': 17, 'steering': -0.1,
                              'speed': 0.3, 'accel': 0.0}
    assert (lines[0]['frames'], lines[0]['bad'], lines[0]['skipped']) == (12040, 0, 0)
    assert lines[1]['rx'] is None


def test_other_schemas_and_text_log_lines_are_passed_over():
    text = ('INFO boot\n{"t":"status","schema":2,"seq":1,"link":{}}\n{not json\n'
            + GOLDEN.read_text(encoding='utf-8'))
    lines, notes = lc.esp32_lines(text)
    assert len(lines) == 2 and len(notes) == 2


def test_the_uplink_is_reported_beside_the_verdict():
    samples, lines = drive()
    good = [{'fresh': True, 'frames': 50 * i, 'lost': 0, 'bad': 0} for i in range(1, 10)]
    r = lc.check(samples, lines, good)
    assert verdicts(r) == (lc.PASS, [lc.PASS, lc.PASS, lc.PASS])
    lossy = good[:-1] + [{'fresh': False, 'frames': 460, 'lost': 4, 'bad': 1}]
    r = lc.check(samples, lines, lossy)
    assert verdicts(r) == (lc.PASS, [lc.PASS, lc.PASS, lc.FAIL])


def test_the_command_line(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        lc.main([])
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        lc.main([str(tmp_path / 'nothing')])
    assert lc.EXIT == {lc.PASS: 0, lc.FAIL: 1, lc.NOT_TESTED: 3}
    print(lc.text(lc.check(*drive())))
    assert capsys.readouterr().out.startswith('Link check: PASS')


@needs_ours
def test_a_bag_and_the_esp32_lines(tmp_path, capsys):
    samples, lines = drive()
    uri = str(tmp_path / 'bag')
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=uri, storage_id='mcap'),
                rosbag2_py.ConverterOptions('cdr', 'cdr'))
    for i, (name, kind) in enumerate(((lc.LINK_FRAME, 'aav_interfaces/msg/LinkFrame'),
                                      (lc.HEALTH, 'aav_interfaces/msg/UplinkHealth'))):
        writer.create_topic(rosbag2_py.TopicMetadata(id=i, name=name, type=kind,
                                                     serialization_format='cdr'))
    t0 = 1_700_000_000 * 10 ** 9
    for n, s in enumerate(samples):
        msg = LinkFrame(version=2, counter=s['counter'], check=s['check'],
                        steering=s['steering'], speed=s['speed'], accel=s['accel'],
                        written=s['written'], write_errors=0, armed=True)
        writer.write(lc.LINK_FRAME, serialize_message(msg), t0 + round(s['t'] * 1e9))
        if n % 10 == 0:
            health = UplinkHealth(fresh=True, frames=50 * n, lost=0, bad=0)
            writer.write(lc.HEALTH, serialize_message(health), t0 + round(s['t'] * 1e9))
    del writer                             # closes the bag
    esp = tmp_path / 'esp32.jsonl'
    esp.write_text('\n'.join(json.dumps(
        {'t': 'status', 'schema': 1, 'seq': i, 'up_ms': i,
         'rx': line['rx'] and {'v': 2, 'counter': line['rx']['counter'],
                               'check': line['rx']['check'], 'steer': line['rx']['steering'],
                               'speed': line['rx']['speed'], 'accel': line['rx']['accel']},
         'link': {'frames': line['frames'], 'bad': 0, 'skipped': 3, 'repeats': 0}})
        for i, line in enumerate(lines)), encoding='utf-8')
    assert lc.main([uri, '--esp32', str(esp)]) == 0
    out = capsys.readouterr().out
    assert out.startswith('Link check: PASS') and 'uplink frames, none lost' in out
    assert lc.main([uri]) == 3                                     # no ESP32: NOT TESTED


def test_todays_text_log_gives_counts_but_no_verdict():
    tail = ' repeats=0 counter=3 uplinks=0 uplink_errors=0\n'
    log = ('LINK t=1000 frames=10 bad=0 skipped=2' + tail + 'FSM t=1000 lifecycle=Run\n'
           'LINK t=2000 frames=60 bad=1 skipped=2' + tail)
    lines, notes = lc.esp32_lines(log)
    assert [line['frames'] for line in lines] == [10, 60] and 'text LINK' in notes[0]
    samples, _ = drive()
    hop = lc.check(samples, lines)['hops'][1]
    assert hop['verdict'] == lc.NOT_TESTED
    assert 'frames +50, bad +1' in hop['reasons'][1]


def test_json_lines_win_over_the_text_log():
    text = ('LINK t=1 frames=1 bad=0 skipped=0 repeats=0 counter=1 uplinks=0 uplink_errors=0\n'
            + GOLDEN.read_text(encoding='utf-8'))
    lines, notes = lc.esp32_lines(text)
    assert len(lines) == 2 and notes == []
