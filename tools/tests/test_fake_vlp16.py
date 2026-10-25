"""Tests for tools/fake_vlp16.py: its made-up scene (aav_bench tests the packets)."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fake_vlp16 as v  # noqa: E402, I100


def test_the_scene_has_a_post_ahead_and_a_ring():
    assert v.scene_distance(0.0, 6.0, 1.0, 15.0) == 6.0
    assert v.scene_distance(4.0, 6.0, 1.0, 15.0) == 6.0         # atan(0.5 / 6) = 4.76 deg
    assert v.scene_distance(5.0, 6.0, 1.0, 15.0) == 15.0
    assert v.scene_distance(356.0, 6.0, 1.0, 15.0) == 6.0       # just left of ahead
    assert v.scene_distance(180.0, 6.0, 1.0, 15.0) == 15.0
