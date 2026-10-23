"""Check the choice of spine_bridge: Rust or Python, and nothing else."""

from aav_spine import bridges
import pytest


def test_each_language_picks_its_package():
    assert bridges.package('rust') == 'aav_spine_bridge'
    assert bridges.package('python') == 'aav_spine'
    assert bridges.package(' Python ') == 'aav_spine'


def test_the_default_is_one_of_them():
    assert bridges.DEFAULT in bridges.PACKAGES


def test_anything_else_is_refused():
    with pytest.raises(ValueError, match='bridge:=cpp'):
        bridges.package('cpp')
