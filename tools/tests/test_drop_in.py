"""Everything is a drop-in (Ben, 5 Nov): the rules, and that the contract keeps to them."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import drop_in  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / 'docs' / 'interfaces.yaml').read_text())


def test_a_good_stream_passes():
    assert drop_in.judge('/a', {'min_hz': 9, 'frame': 'f'}, 100, 10.0, {'f'}) == []


def test_silence_fails():
    assert drop_in.judge('/a', {'min_hz': 9}, 0, 10.0, set()) == ['/a: nothing heard in 10 s']


def test_too_slow_fails():
    problems = drop_in.judge('/a', {'min_hz': 9}, 50, 10.0, set())
    assert problems == ['/a: 5.0 Hz, the contract needs at least 9']


def test_the_wrong_frame_fails():
    problems = drop_in.judge('/a', {'frame': 'f'}, 100, 10.0, {'g'})
    assert problems == ["/a: frame ['g'], the contract says f"]


def test_mixed_frames_fail():
    assert drop_in.judge('/a', {'frame': 'f'}, 100, 10.0, {'f', 'g'})


def test_the_sensors_have_rules():
    rules = drop_in.rules(SPEC)
    for topic in ('/sensors/lidar/points', '/sensors/imu/data', '/sensors/gps/fix',
                  '/vehicle/odom', '/perception/voxels/cubes'):
        assert 'min_hz' in rules[topic], topic


def test_too_fast_fails():
    problems = drop_in.judge('/a', {'max_hz': 12}, 9860, 10.0, set())
    assert problems == ['/a: 986.0 Hz, the contract allows at most 12']


def test_a_best_effort_publisher_fails_a_reliable_rule():
    assert drop_in.judge('/a', {'reliable': True}, 100, 10.0, set(), False)
    assert drop_in.judge('/a', {'reliable': True}, 100, 10.0, set(), True) == []
    assert drop_in.judge('/a', {'reliable': True}, 100, 10.0, set(), None) == []


def test_every_rule_is_on_a_topic_that_publishes_something():
    for name in drop_in.rules(SPEC):
        assert SPEC['topics'][name].get('pub'), name


def test_no_topic_is_named_after_one_simulator():
    assert drop_in.named_after_a_simulator(SPEC) == []


def test_nothing_that_drives_reads_a_simulators_own_topics():
    assert drop_in.sim_leaks(SPEC) == []


def test_a_new_reader_would_be_caught():
    spec = {'topics': {'/vehicle/sim/truth': {'sub': ['ego']}}}
    assert drop_in.sim_leaks(spec) == ['ego reads /vehicle/sim/truth']
