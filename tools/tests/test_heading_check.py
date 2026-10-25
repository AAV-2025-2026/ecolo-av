"""heading_check: its sums, without Gazebo."""

import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import heading_check as hc  # noqa: E402
import pytest  # noqa: E402


def test_errors_are_split_into_forward_and_reversing_and_standing_still_is_left_out():
    d = math.radians
    samples = [(0.5, d(2.0), 0.0), (0.5, d(-4.0), 0.0), (0.5, d(10.0), 0.0),
               (-0.5, d(181.0), d(180.0)), (0.0, d(90.0), 0.0)]
    out = hc.summarise(samples)
    assert out['forward']['n'] == 3
    assert out['forward']['median'] == pytest.approx(4.0)
    assert out['forward']['worst'] == pytest.approx(10.0)
    # Across the +-180 degree seam: 1 degree, not 359.
    assert out['reversing']['worst'] == pytest.approx(1.0)


def test_no_samples_either_way():
    assert hc.summarise([]) == {'forward': {'n': 0}, 'reversing': {'n': 0}}


def test_the_profile_drives_forward_and_back_and_ends():
    assert hc.command_at(0.0) == (0.0, 0.0)
    assert hc.command_at(4.0) == (0.5, 0.0)
    assert any(speed < 0 for _, speed, _ in hc.PROFILE)
    assert hc.command_at(sum(seconds for seconds, *_ in hc.PROFILE)) is None


def test_percentile_is_nearest_rank():
    assert hc.percentile(list(range(1, 101)), 0.95) == 95


def test_recovered_after_is_the_first_time_under_5_degrees():
    assert hc.recovered_after([(10.0, 30.0), (12.0, 9.0), (13.5, 4.0), (14.0, 6.0)]) == 3.5
    assert hc.recovered_after([(0.0, 30.0)]) == math.inf
