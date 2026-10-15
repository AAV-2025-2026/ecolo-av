"""
The Rust board's UART link against the 2025-26 C++ itself.

Compiles the C++'s own ros2_handler.cpp and jrk_g2.cpp (firmware/legacy/aav_umod_esp32)
on this computer, with stand-in Arduino headers (firmware/spine/crates/legacy-link/
cpp_check), feeds it every frame in legacy-link's vectors.json, and checks it sets the
same Jrk and DAC targets as the vectors say. `cargo test -p legacy-link` checks the Rust
crate against the same file, and aav_legacy's tests check the bytes are what
legacy_protocol.py sends. So all three agree.

Twice: with the multiply-adds kept apart, and fused into one rounding, as the ESP32's
compiler may do (its FPU has madd.s).

Skipped where there is no C++ compiler.
"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / 'firmware/spine/crates/legacy-link/cpp_check'
MODULES = ROOT / 'firmware/legacy/aav_umod_esp32/src/modules'
VECTORS = json.loads((ROOT / 'firmware/spine/crates/legacy-link/vectors.json').read_text())

CXX = shutil.which('c++') or shutil.which('g++') or shutil.which('clang++')
pytestmark = pytest.mark.skipif(CXX is None, reason='no C++ compiler here')


def expected(cpp):
    """Return the harness's line for a case's `cpp` entry in vectors.json."""
    if cpp is None:
        return 'rejected'
    t = cpp['throttle']
    if isinstance(t, str):
        return f"{cpp['steering']} {cpp['brake']} {t}"
    return f"{cpp['steering']} {cpp['brake']} drive {t['code']} {'rev' if t['reverse'] else 'fwd'}"


@pytest.fixture(scope='module', params=['off', 'fast'])
def harness(request, tmp_path_factory):
    exe = tmp_path_factory.mktemp('cpp') / f'harness-{request.param}'
    subprocess.run(
        [CXX, '-std=c++17', '-O1', f'-ffp-contract={request.param}',
         '-I', str(CHECK / 'stubs'), '-I', str(MODULES), '-o', str(exe),
         str(CHECK / 'harness.cpp'), str(MODULES / 'ros2_handler/ros2_handler.cpp'),
         str(MODULES / 'jrk_g2/jrk_g2.cpp')],
        check=True, capture_output=True, text=True)
    return exe


def run(exe, frames):
    stdin = ''.join(' '.join(f'{b:02x}' for b in f) + '\n' for f in frames)
    out = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def test_the_cpp_sets_the_targets_in_the_vectors(harness):
    cases = VECTORS['cases']
    got = run(harness, [c['bytes'] for c in cases])
    for case, line in zip(cases, got, strict=True):
        assert line == expected(case['cpp']), case['name']


def test_the_cpp_finds_the_same_frames_in_a_noisy_stream(harness):
    # The whole stream in one go: the C++ keeps its buffer between bytes, as it did between
    # loop() calls. Only the last frame's targets show; check it, and that it found one.
    got = run(harness, [VECTORS['stream']])
    last = VECTORS['stream_frames'][-1]
    assert got == run(harness, [last])
    assert got != ['rejected']
