#!/usr/bin/env python3
"""
Link check: did the Motor Pi's frames reach the ESP32? PASS, FAIL or NOT TESTED.

The joystick path's last hop (docs/hardware-debug.md, layer 2). It sets what the Pi says it
wrote against what the ESP32 says it received, over the same stretch of frames:

    pixi run link-check bags/2026-11-08_joy --esp32 esp32.jsonl
    pixi run link-check --live 30 --esp32 esp32.jsonl     30 s of the live topics, then the file
    pixi run link-check bags/... --json

  the Pi      /control/car/link_frame (legacy_uart_bridge, aav_interfaces/LinkFrame): a
              sample of the frames written, each with `written`, the count of every frame
  the ESP32   its status lines (firmware/status/README.md, `"t":"status"`): `rx` (the last
              good frame: counter, check, values) and `link` (frames, bad, skipped).
              Today's Rust writes only text (`LINK t=... frames=... bad=...`): read too,
              but with no frame to match, the ESP32 hop stays NOT TESTED
  the uplink  /vehicle/esp32/uplink_health, if recorded: reported, but not in the verdict

How a frame is known: by its counter AND its check byte, never by the counter alone. Stop
frames repeat a counter with other values (review 2, M1). A key seen in two separate
stretches (the counter wraps every 256 commands) is ambiguous, and isn't used.

How the counts are compared: each frame both sides saw is an anchor. On the Pi it lies
between the samples either side of it (a range of `written`); on the ESP32 it is the last
frame before `frames`. With no frame lost, `frames - written` is the same at every anchor.
So the check passes only if one offset fits every anchor, and `bad` and `skipped` stay flat
between the first and last anchor.

  FAIL        a write failed; frames lost for certain; the ESP32 counted frames the Pi
              never wrote (a second writer?); `bad` or `skipped` rose; a frame's values
              differ; the ESP32 restarted
  NOT TESTED  no data on a side; the commands never changed (a parked car); under two
              frames seen by both, or none with different values
  PASS        none of those, over at least two anchors with different values. It says
              how long a run of lost frames could still hide in the samples' gaps

It says "sampled N frames": the Pi's samples are a tenth or so of the frames, so the proof is
the counts, not the samples. Reading a bag or the live topics needs ROS (tools/ros.sh, our
messages built); the check itself doesn't.

Exit status: 0 PASS, 1 FAIL, 3 NOT TESTED, 2 a usage error.
"""

import argparse
import json
import os
import re
import sys

PASS, FAIL, NOT_TESTED = 'PASS', 'FAIL', 'NOT TESTED'
EXIT = {PASS: 0, FAIL: 1, NOT_TESTED: 3}
LINK_FRAME = '/control/car/link_frame'
HEALTH = '/vehicle/esp32/uplink_health'
SCHEMA = 1              # firmware/status/README.md
VALUE_TOL = 0.01        # the ESP32's JSON may round its values (-1..1) to two places
VALUES = ('steering', 'speed', 'accel')


# --- What each side says ---

def pi_sample(version, counter, check, steering, speed, accel, written, write_errors, t=0.0):
    """Return one /control/car/link_frame sample as the check reads it."""
    return {'t': t, 'version': int(version), 'counter': int(counter), 'check': int(check),
            'steering': float(steering), 'speed': float(speed), 'accel': float(accel),
            'written': int(written), 'write_errors': int(write_errors)}


LINK_TEXT = re.compile(r'LINK t=(\d+) frames=(\d+) bad=(\d+) skipped=(\d+)')


def esp32_lines(text):
    """
    Return (status lines, notes) from the ESP32's log: its JSON lines, or else its text.

    JSON status lines (firmware/status/README.md) carry the last frame, so frames can be
    matched. Other JSON (`hb`, `event`) is passed over; a status line of another schema
    can't be read, and is counted in the notes. With no JSON status line at all, today's
    text lines (`LINK t=... frames=... bad=... skipped=...`) give the counts alone, with
    no frame to match: the counts can't then be set against the Pi's.
    """
    out, text_lines, other_schema, not_json = [], [], 0, 0
    for raw in text.splitlines():
        raw = raw.strip()
        match = LINK_TEXT.search(raw)
        if match:
            t, frames, bad, skipped = (int(g) for g in match.groups())
            text_lines.append({'seq': None, 'up_ms': t, 'frames': frames, 'bad': bad,
                               'skipped': skipped, 'rx': None})
            continue
        if not raw.startswith('{'):
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError:
            not_json += 1
            continue
        if not isinstance(line, dict) or line.get('t') != 'status':
            continue
        if line.get('schema') != SCHEMA:
            other_schema += 1
            continue
        link, rx = line.get('link') or {}, line.get('rx')
        status = {'seq': line.get('seq'), 'up_ms': line.get('up_ms'),
                  'frames': link.get('frames'), 'bad': link.get('bad'),
                  'skipped': link.get('skipped'), 'rx': None}
        if None in (status['frames'], status['bad'], status['skipped']):
            continue
        if rx:
            status['rx'] = {'version': rx.get('v'), 'counter': rx.get('counter'),
                            'check': rx.get('check'), 'steering': rx.get('steer'),
                            'speed': rx.get('speed'), 'accel': rx.get('accel')}
        out.append(status)
    notes = []
    if not out and text_lines:
        out = text_lines
        notes.append(f'{len(text_lines)} text LINK lines only: counts, but no frame to match')
    if other_schema:
        notes.append(f'{other_schema} status lines of a schema other than {SCHEMA}: not read')
    if not_json:
        notes.append(f'{not_json} lines looked like JSON but were not')
    return out, notes


# --- The check ---

def key(frame):
    """Return the frame's identity: its counter and its check byte."""
    return frame['counter'], frame['check']


def runs(items, key_of):
    """Return [(key, first index, last index)]: the stretches of one key in a row."""
    out = []
    for i, item in enumerate(items):
        k = key_of(item)
        if out and out[-1][0] == k:
            out[-1] = (k, out[-1][1], i)
        else:
            out.append((k, i, i))
    return out


def unique_runs(stretches):
    """Return {key: (first, last)} for the keys seen in one stretch only."""
    seen = {}
    for k, first, last in stretches:
        seen.setdefault(k, []).append((first, last))
    return {k: v[0] for k, v in seen.items() if len(v) == 1 and k is not None}


def pi_ranges(samples):
    """
    Return {key: (lo, hi, sample)}: the `written` numbers a key's frames can have.

    A key's frames lie after the sample before it with another key and before the one after:
    lo and hi are those, one frame in. Keys at either end have no bound there: left out.
    """
    stretches = runs(samples, key)
    once = unique_runs(stretches)
    out = {}
    for n, (k, first, last) in enumerate(stretches):
        if k not in once or n == 0 or n == len(stretches) - 1:
            continue
        lo = samples[stretches[n - 1][2]]['written'] + 1
        hi = samples[stretches[n + 1][1]]['written'] - 1
        out[k] = (lo, hi, samples[first])
    return out


def anchors(samples, lines):
    """
    Return the frames both sides saw, in the ESP32's order.

    Each: {'key', 'lo', 'hi' (the Pi's written range), 'frames', 'bad', 'skipped' (the
    ESP32's counts at its first line with this frame), 'pi', 'esp32' (each side's values)}.
    """
    pi = pi_ranges(samples)
    esp = unique_runs(runs(lines, lambda s: key(s['rx']) if s['rx'] else None))
    out = []
    for k, (first, _) in sorted(esp.items(), key=lambda kv: kv[1][0]):
        if k in pi:
            lo, hi, sample = pi[k]
            line = lines[first]
            out.append({'key': k, 'lo': lo, 'hi': hi, 'frames': line['frames'],
                        'bad': line['bad'], 'skipped': line['skipped'], 'pi': sample,
                        'esp32': line['rx']})
    return out


def values(frame):
    """Return the frame's version and values, for telling frames apart."""
    return (frame['version'],) + tuple(round(frame[v], 2) for v in VALUES)


def check_pi(samples):
    """Return (verdict, reasons) for the Pi's own side: its writes, and changing commands."""
    if not samples:
        return NOT_TESTED, [f'no {LINK_FRAME}: was legacy_uart_bridge running and recorded?']
    for a, b in zip(samples, samples[1:]):
        if b['written'] < a['written']:
            return NOT_TESTED, ['the bridge restarted during the recording '
                                '(written went down): record again, one run of the bridge']
    errors = samples[-1]['write_errors'] - samples[0]['write_errors']
    if errors > 0:
        return FAIL, [f'{errors} writes to the serial port failed or were short']
    if len({values(s) for s in samples}) < 2:
        return NOT_TESTED, ['the commands never changed (a parked car?): '
                            'move the stick, so a changing value is compared']
    versions = {s['version'] for s in samples}
    if versions != {1} and len({s['counter'] for s in samples}) < 2:
        return NOT_TESTED, ['the counter never moved: no fresh command passed the output mux']
    return PASS, [f"wrote {samples[-1]['written'] - samples[0]['written']} frames, "
                  f'sampled {len(samples)}; no write failed']


def check_esp32(samples, lines):
    """Return (verdict, reasons, anchors) for Pi -> ESP32: the counts, frame by frame."""
    if not lines:
        return NOT_TESTED, ['no ESP32 status lines (--esp32): its counts are the proof'], []
    for a, b in zip(lines, lines[1:]):
        if b['frames'] < a['frames'] or (a['up_ms'] is not None and b['up_ms'] is not None
                                         and b['up_ms'] < a['up_ms']):
            return FAIL, [f"the ESP32 restarted (status line {b['seq']}): "
                          'its counts started again'], []
    found = anchors(samples, lines)
    for a in found:
        p, e = a['pi'], a['esp32']
        if e['version'] != p['version'] or any(
                e[v] is None or abs(e[v] - p[v]) > VALUE_TOL for v in VALUES):
            return FAIL, [f"frame counter {a['key'][0]} check {a['key'][1]}: the Pi wrote "
                          f'{values(p)}, the ESP32 read {values(e)}. A good frame that '
                          'differs: a pairing or reporting bug, not the wire'], found
    if len(found) < 2:
        why = [f'{len(found)} frames seen by both sides (counter + check): '
               + ('the ESP32 log has no frames (text LINK lines, or no rx)'
                  if not any(line['rx'] for line in lines)
                  else 'were the two recordings at the same time?')]
        bad = lines[-1]['bad'] - lines[0]['bad']
        skipped = lines[-1]['skipped'] - lines[0]['skipped']
        why.append(f"over the whole ESP32 log: frames +{lines[-1]['frames'] - lines[0]['frames']}"
                   f', bad +{bad}, skipped +{skipped} (a start-up may skip a few bytes)')
        return NOT_TESTED, why, found
    if len({values(a['pi']) for a in found}) < 2:
        return NOT_TESTED, ['every frame both sides saw had the same values: '
                            'nothing changing was compared'], found
    first, last = found[0], found[-1]
    reasons = []
    bad, skipped = last['bad'] - first['bad'], last['skipped'] - first['skipped']
    if bad or skipped:
        reasons.append(f'the ESP32 turned down {bad} frames and skipped {skipped} bytes '
                       'between the first and last frame both saw: noise, the wire, or '
                       'a wrong frame_version')
    # One offset (frames - written) must fit every anchor.
    low = max(a['frames'] - a['hi'] for a in found)
    high = min(a['frames'] - a['lo'] for a in found)
    received = last['frames'] - first['frames']
    wrote_min, wrote_max = last['lo'] - first['hi'], last['hi'] - first['lo']
    if received < wrote_min:
        reasons.append(f'the Pi wrote at least {wrote_min} frames between them, the ESP32 '
                       f'received {received}: at least {wrote_min - received} lost')
    elif received > wrote_max:
        reasons.append(f'the ESP32 received {received} frames, the Pi wrote at most '
                       f'{wrote_max}: a second writer on the UART (the old service?)')
    elif low > high:
        reasons.append('the counts jumped between frames: frames lost and found again')
    if reasons:
        return FAIL, reasons, found
    return PASS, [f'{len(found)} frames seen by both; the ESP32 received {received}, '
                  f'the Pi wrote {wrote_min}..{wrote_max} between the first and last; '
                  'bad and skipped flat',
                  f'a loss of up to {hidden_loss(found)} frames in a row would not show '
                  '(more samples, link_frame_rate_hz up to 50, make it smaller)'], found


def hidden_loss(found):
    """
    Return the most frames in a row that could be lost without the counts showing it.

    Each anchor allows an offset range [frames - hi, frames - lo]. A loss of k frames after
    anchor i shifts every later range down by k: it shows only once the earlier ranges'
    lowest common offset is above the later ranges' highest.
    """
    ranges = [(a['frames'] - a['hi'], a['frames'] - a['lo']) for a in found]
    suffix_high = [0] * len(ranges)
    lowest = None
    for i in range(len(ranges) - 1, -1, -1):
        lowest = ranges[i][1] if lowest is None else min(lowest, ranges[i][1])
        suffix_high[i] = lowest
    worst, prefix_low = 0, None
    for i in range(len(ranges) - 1):
        prefix_low = ranges[i][0] if prefix_low is None else max(prefix_low, ranges[i][0])
        worst = max(worst, suffix_high[i + 1] - prefix_low)
    return worst


def check_uplink(health):
    """Return (verdict, reasons) for ESP32 -> Pi: the uplink's health, if recorded."""
    if not health:
        return NOT_TESTED, [f'no {HEALTH} (uplink off?)']
    first, last = health[0], health[-1]
    lost, bad = last['lost'] - first['lost'], last['bad'] - first['bad']
    stale = sum(1 for h in health if not h['fresh'])
    reasons = []
    if last['frames'] < first['frames']:
        return NOT_TESTED, ['the bridge restarted during the recording']
    if lost or bad:
        reasons.append(f'{lost} uplink frames lost, {bad} bad')
    if stale:
        reasons.append(f'stale in {stale} of {len(health)} reports')
    if last['frames'] == first['frames']:
        reasons.append('no uplink frame arrived')
    if reasons:
        return FAIL, reasons
    return PASS, [f"{last['frames'] - first['frames']} uplink frames, none lost or bad"]


def check(samples, lines, health=()):
    """
    Return the report: {'verdict', 'hops': [{'hop', 'verdict', 'reasons'}], 'anchors'}.

    The verdict is the joystick path's, the Pi and Pi -> ESP32: FAIL if either fails, else
    NOT TESTED if either is, else PASS. The uplink is reported beside it.
    """
    pi, pi_why = check_pi(samples)
    esp, esp_why, found = check_esp32(samples, lines)
    up, up_why = check_uplink(list(health))
    hops = [{'hop': 'the Pi writes', 'verdict': pi, 'reasons': pi_why},
            {'hop': 'Pi > ESP32', 'verdict': esp, 'reasons': esp_why},
            {'hop': 'ESP32 > Pi (uplink, not in the verdict)', 'verdict': up,
             'reasons': up_why}]
    verdicts = (pi, esp)
    verdict = FAIL if FAIL in verdicts else NOT_TESTED if NOT_TESTED in verdicts else PASS
    return {'verdict': verdict, 'hops': hops, 'anchors': len(found)}


def text(report):
    """Return the report as a few lines for a person."""
    out = [f"Link check: {report['verdict']}"]
    for h in report['hops']:
        out.append(f"  {h['hop']:<42} {h['verdict']}")
        out += [f'      {r}' for r in h['reasons']]
    return '\n'.join(out)


# --- Reading ROS (needs tools/ros.sh) ---

def from_link_frame(msg, t):
    """Return a sample from an aav_interfaces/LinkFrame."""
    return pi_sample(msg.version, msg.counter, msg.check, msg.steering, msg.speed,
                     msg.accel, msg.written, msg.write_errors, t)


def from_health(msg):
    """Return the check's view of an aav_interfaces/UplinkHealth."""
    return {'fresh': bool(msg.fresh), 'frames': int(msg.frames), 'lost': int(msg.lost),
            'bad': int(msg.bad)}


def read_bag(path):
    """Return (samples, health) from a bag folder (rosbag2_py, our messages)."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(path), storage_id=''),
                rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    wanted = [t for t in (LINK_FRAME, HEALTH) if t in types]
    if not wanted:
        return [], []
    reader.set_filter(rosbag2_py.StorageFilter(topics=wanted))
    classes = {t: get_message(types[t]) for t in wanted}
    samples, health = [], []
    while reader.has_next():
        topic, data, stamp = reader.read_next()
        msg = deserialize_message(data, classes[topic])
        if topic == LINK_FRAME:
            samples.append(from_link_frame(msg, stamp * 1e-9))
        else:
            health.append(from_health(msg))
    return samples, health


def read_live(seconds):
    """Return (samples, health) heard on the live topics for this long."""
    import time

    from aav_interfaces.msg import LinkFrame, UplinkHealth
    import rclpy

    rclpy.init()
    node = rclpy.create_node('link_check')
    samples, health = [], []
    node.create_subscription(LinkFrame, LINK_FRAME,
                             lambda m: samples.append(from_link_frame(m, time.time())), 100)
    node.create_subscription(UplinkHealth, HEALTH, lambda m: health.append(from_health(m)), 10)
    end = time.monotonic() + seconds
    try:
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return samples, health


# --- The command line ---

def parse(argv):
    p = argparse.ArgumentParser(description="Did the Motor Pi's frames reach the ESP32? "
                                'PASS, FAIL or NOT TESTED (docs/hardware-debug.md).')
    p.add_argument('bag', nargs='?', help='a bag folder from tools/record.sh')
    p.add_argument('--live', type=float, metavar='SECONDS',
                   help='listen to the live topics for this long instead of a bag')
    p.add_argument('--esp32', metavar='FILE',
                   help="the ESP32's JSON lines over the same time (its USB log or "
                   '/status.json, saved); without it the ESP32 hop is NOT TESTED')
    p.add_argument('--json', action='store_true', help='the report as JSON')
    args = p.parse_args(argv)
    if (args.bag is None) == (args.live is None):
        p.error('give a bag folder or --live SECONDS, not both')
    if args.bag is not None and not os.path.isdir(args.bag):
        p.error(f'{args.bag}: not a bag folder')
    return args


def main(argv=None):
    args = parse(argv)
    samples, health = read_live(args.live) if args.live is not None else read_bag(args.bag)
    lines, notes = [], []
    if args.esp32:
        with open(args.esp32, encoding='utf-8', errors='replace') as f:
            lines, notes = esp32_lines(f.read())
    report = check(samples, lines, health)
    report['notes'] = notes
    print(json.dumps(report, indent=2) if args.json else text(report))
    for n in notes if not args.json else ():
        print(f'  note: {n}')
    return EXIT[report['verdict']]


if __name__ == '__main__':
    sys.exit(main())
