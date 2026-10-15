#!/usr/bin/env python3
"""
Regenerate the UART link's test vectors, from the ROS side's own code.

The bytes come from src/backends/aav_legacy/aav_legacy/legacy_protocol.py (pack_frame,
to_legacy, stop_command): what the Motor-Pi sends today. The expected Jrk and DAC targets
come from a line-by-line model of the 2025-26 C++ (ros2_handler.cpp, jrk_g2.cpp), in
single-precision floats as the ESP32 computes them.

Writes:
  firmware/spine/crates/legacy-link/vectors.json     (read by aav_legacy's tests)
  firmware/spine/crates/legacy-link/tests/vectors.rs (read by `cargo test`)

Run it after any change to legacy_protocol.py or the legacy-link crate:
  python3 firmware/spine/crates/legacy-link/gen_vectors.py
"""

import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOCOL = ROOT / 'src/backends/aav_legacy/aav_legacy/legacy_protocol.py'
JSON_OUT = HERE / 'vectors.json'
RUST_OUT = HERE / 'tests/vectors.rs'

spec = importlib.util.spec_from_file_location('legacy_protocol', PROTOCOL)
lp = importlib.util.module_from_spec(spec)
sys.modules['legacy_protocol'] = lp  # dataclasses look the module up while loading
spec.loader.exec_module(lp)


def f32(x):
    """Round to the nearest single-precision float, as the ESP32's float maths does."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def u16(x):
    """C's (uint16_t) cast of a non-negative float: drop the fraction."""
    return int(x)


def constrain(x, lo, hi):
    return max(lo, min(hi, x))


# hardware_configs.h
JRK_MIN, JRK_CENTER, JRK_MAX, DAC_MAX_CAP = 400, 1950, 3500, 700


def cpp_targets(steering, speed, accel):
    """Return what handleROS2Messages() sent to the devices, or None if it refused."""
    if not (abs(steering) <= 1.0 and abs(speed) <= 1.0 and abs(accel) <= 1.0):
        return None  # "packet rejected - out of range": writeDACRamped(0) only
    if steering <= 0.0:
        steer = u16(f32(JRK_CENTER + f32(steering * JRK_CENTER)))
    else:
        steer = u16(f32(JRK_CENTER + f32(steering * (JRK_MAX - JRK_CENTER))))
    steer = constrain(steer, JRK_MIN, JRK_MAX)  # setSteer()
    if accel < f32(-0.05):  # -0.05f: a float literal
        brake = constrain(u16(f32(abs(accel) * JRK_MAX)), JRK_MIN, JRK_MAX)
        return {'steering': steer, 'brake': brake, 'throttle': 'cut'}
    if abs(speed) < f32(0.03):  # 0.03f
        return {'steering': steer, 'brake': JRK_MIN, 'throttle': 'idle'}
    code = constrain(u16(f32(abs(speed) * DAC_MAX_CAP)), 0, DAC_MAX_CAP)
    return {'steering': steer, 'brake': JRK_MIN,
            'throttle': {'code': code, 'reverse': speed < 0}}


def raw_frame(steering, speed, accel):
    """Pack a frame without pack_frame's clamp: for values the C++ must turn down."""
    body = struct.pack('<fff', steering, speed, accel)
    return body + bytes([sum(body) & 0xFF])


M = lp.LegacyMapping()   # the defaults: 0.5 rad full lock, 3.0 m/s full throttle
M_CAR = lp.LegacyMapping(steering_sign=-1.0)  # legacy.yaml's sign
NAN = float('nan')

# (name, how the frame was made, the frame's bytes)
CASES = [
    ('stand_still', 'to_legacy(0.0, 0.0)', lp.pack_frame(*lp.to_legacy(0.0, 0.0, M))),
    ('stale_stop', 'stop_command()', lp.pack_frame(*lp.stop_command(M))),
    ('stale_stop_holding_steer', 'stop_command(steering_hold=0.4)',
     lp.pack_frame(*lp.stop_command(M, 0.4))),
    ('creep', 'to_legacy(0.06, 0.0)', lp.pack_frame(*lp.to_legacy(0.06, 0.0, M))),
    ('cruise_left', 'to_legacy(1.5, 0.25)', lp.pack_frame(*lp.to_legacy(1.5, 0.25, M))),
    ('cruise_right', 'to_legacy(1.5, -0.25)', lp.pack_frame(*lp.to_legacy(1.5, -0.25, M))),
    ('car_sign_left', 'to_legacy(2.0, 0.3), steering_sign=-1',
     lp.pack_frame(*lp.to_legacy(2.0, 0.3, M_CAR))),
    ('full_forward', 'to_legacy(5.0, 1.0)', lp.pack_frame(*lp.to_legacy(5.0, 1.0, M))),
    ('reverse', 'to_legacy(-0.9, -0.1)', lp.pack_frame(*lp.to_legacy(-0.9, -0.1, M))),
    ('full_reverse', 'to_legacy(-9.0, 0.0)', lp.pack_frame(*lp.to_legacy(-9.0, 0.0, M))),
    ('full_left_raw', 'pack_frame(1, 0.5, 0)', lp.pack_frame(1.0, 0.5, 0.0)),
    ('full_right_raw', 'pack_frame(-1, 0.5, 0)', lp.pack_frame(-1.0, 0.5, 0.0)),
    ('odd_steer_raw', 'pack_frame(0.123, -0.456, 0.0)', lp.pack_frame(0.123, -0.456, 0.0)),
    ('deadband_edge', 'pack_frame(0, 0.0299, 0)', lp.pack_frame(0.0, 0.0299, 0.0)),
    ('just_past_deadband', 'pack_frame(0, -0.0301, 0)', lp.pack_frame(0.0, -0.0301, 0.0)),
    ('brake_threshold', 'pack_frame(0, 0.5, -0.05)', lp.pack_frame(0.0, 0.5, -0.05)),
    ('light_brake', 'pack_frame(0, 0.5, -0.06)', lp.pack_frame(0.0, 0.5, -0.06)),
    ('brake_and_throttle', 'pack_frame(-0.3, 0.8, -0.7)', lp.pack_frame(-0.3, 0.8, -0.7)),
    ('clamped_by_pack', 'pack_frame(2, -3, 9)', lp.pack_frame(2.0, -3.0, 9.0)),
    ('out_of_range', 'raw (1.5, 0, 0)', raw_frame(1.5, 0.0, 0.0)),
    ('not_a_number', 'raw (0, NaN, 0)', raw_frame(0.0, NAN, 0.0)),
]


def cpp_parse(stream):
    """Split a stream as the C++'s byte loop did: 13 bytes, then the sum; a mismatch drops one."""
    buf, out = [], []
    for b in stream:
        buf.append(b)
        if len(buf) == 13:
            if sum(buf[:12]) & 0xFF == buf[12]:
                out.append(bytes(buf))
                buf = []
            else:
                buf = buf[1:]
    return out


# Noise, a frame, a frame's tail, two frames back to back: what a Pi rebooting mid-frame,
# or a loose wire, gives.
STREAM = (bytes([0x00, 0xFF, 0x13]) + lp.pack_frame(0.1, 0.2, 0.0)
          + lp.pack_frame(-0.5, 0.0, -1.0)[5:]
          + lp.pack_frame(0.0, 0.4, 0.0) + lp.pack_frame(0.2, -0.3, 0.0))
STREAM_FRAMES = cpp_parse(STREAM)


def rust_throttle(t):
    if t == 'cut':
        return 'Throttle::Cut'
    if t == 'idle':
        return 'Throttle::Idle'
    rev = 'true' if t['reverse'] else 'false'
    return f"Throttle::Drive {{ code: {t['code']}, reverse: {rev} }}"


def hexes(bs):
    return ', '.join(f'0x{b:02x}' for b in bs)


def rust_tests(cases):
    out = ['// Generated by gen_vectors.py from legacy_protocol.py and a model of the',
           "// 2025-26 C++. Do not edit. Checks that this crate reads the Motor-Pi's",
           '// bytes, and sends the devices the targets, as the C++ did.',
           '',
           'use legacy_link::{Frame, FrameError, Parser, Targets, Throttle};',
           '']
    for c in cases:
        out += ['#[test]', f"fn {c['name']}() {{",
                f"    // {c['made_by']}",
                f"    let bytes = [{hexes(c['bytes'])}];",
                '    let frame = Frame::decode(&bytes).expect("checksum");']
        t = c['cpp']
        if t is None:
            out.append('    assert_eq!(frame.check(), Err(FrameError::OutOfRange));')
        else:
            out += ['    let frame = frame.check().expect("in range");',
                    '    assert_eq!(',
                    '        frame.targets(),',
                    f"        Targets {{ steering: {t['steering']}, brake: {t['brake']}, "
                    f"throttle: {rust_throttle(t['throttle'])} }}",
                    '    );',
                    '    assert_eq!(frame.encode(), bytes);']
        out += ['}', '']
    out += ['#[test]', 'fn a_stream_with_noise() {',
            f'    let stream = [{hexes(STREAM)}];',
            '    let mut parser = Parser::new();',
            '    let found: Vec<[u8; 13]> = stream',
            '        .iter()',
            '        .filter_map(|&b| parser.push(b))',
            '        .filter_map(Result::ok)',
            '        .map(|f| f.encode())',
            '        .collect();',
            '    let expected: Vec<[u8; 13]> = vec![']
    out += [f'        [{hexes(f)}],' for f in STREAM_FRAMES]
    out += ['    ];', '    assert_eq!(found, expected);', '}', '']
    return '\n'.join(out)


def main():
    cases = []
    for name, made_by, frame in CASES:
        steering, speed, accel = struct.unpack('<fff', frame[:12])
        cases.append({'name': name, 'made_by': made_by, 'bytes': list(frame),
                      'values': [steering, speed, accel],
                      'cpp': cpp_targets(steering, speed, accel)})
    doc = {'note': 'Generated by gen_vectors.py. bytes: what the Motor-Pi sends; '
                   'cpp: the Jrk and DAC targets the 2025-26 ESP32 firmware set for them '
                   '(null: it turned the frame down).',
           'cases': [{k: v for k, v in c.items() if k != 'values'} for c in cases],
           'stream': list(STREAM),
           'stream_frames': [list(f) for f in STREAM_FRAMES]}
    JSON_OUT.write_text(json.dumps(doc, indent=1) + '\n')
    RUST_OUT.parent.mkdir(exist_ok=True)
    RUST_OUT.write_text(rust_tests(cases))
    if shutil.which('rustfmt'):
        subprocess.run(['rustfmt', '--edition', '2021', str(RUST_OUT)], check=True)
    print(f'wrote {len(cases)} cases and a stream of {len(STREAM)} bytes '
          f'to {JSON_OUT.relative_to(ROOT)} and {RUST_OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
