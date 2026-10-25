"""vehicle_model: the tables print, and Gazebo's steering gain is read from the xacro."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import vehicle_model as tool  # noqa: E402
    HAVE_SCIPY = True
except ImportError:          # no numpy or scipy here: pixi run test has them
    HAVE_SCIPY = False

pytestmark = pytest.mark.skipif(not HAVE_SCIPY, reason='needs numpy and scipy')


def test_the_tables_print(capsys):
    assert tool.main(['--no-figures', '--set', 'throttle_lag=0.25']) == 0
    out = capsys.readouterr().out
    assert 'with throttle_lag=0.25' in out
    for title in ('Speed loop margins', 'Steering: second order', 'Lateral margins',
                  'Discrete time', "Gazebo's car"):
        assert title in out


def test_gazebo_s_steering_gain():
    # The xacro's steer_p_gain: Gazebo turns each steering joint at gain x error (1/s).
    assert tool.gazebo_steer_gain() == 10.0
    gain, rows = tool.gazebo_rows(tool.vm.VehicleModel())
    assert len(rows) == 1 + len(tool.vm.lateral_speeds())


def test_a_wrong_key_is_refused():
    with pytest.raises(KeyError):
        tool.main(['--no-figures', '--set', 'throtle_lag=0.2'])
