"""vehicle_model: the tables print, and Gazebo's steering gain is read from the xacro."""

from pathlib import Path
import re
import sys

import pytest
import yaml

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
    assert tool.gazebo_steer_gain() == 100.0
    gain, rows = tool.gazebo_rows(tool.vm.VehicleModel())
    assert len(rows) == 1 + len(tool.vm.lateral_speeds())


def test_gazebo_steers_as_vehicle_yaml_says():
    # TODO 52c: Gazebo's own steering lag (1/steer_p_gain, and the adapter's 50 Hz hold)
    # comes after the actuator model's steer_lag. It was 0.11 s (gain 10), more than
    # steer_lag itself. Keep it a small part of steer_lag, so Gazebo's car is the model's.
    actuators = yaml.safe_load(tool.VEHICLE_YAML.read_text())['actuators']
    assert tool.gazebo_extra_lag() <= 0.25 * actuators['steer_lag']


def test_gazebo_s_joints_can_turn_as_fast_as_the_model():
    # Gazebo holds each steering joint to the URDF's velocity limit: at 1.0 rad/s its wheels
    # turned only 0.63, slower than the model's steer_rate (TODO 52c). The inner wheel turns
    # faster than the centre one, and the gain's catch-up on each 20 ms hold faster still.
    urdf = (tool.ROOT / 'src/aav_description/urdf/aav.urdf.xacro').read_text()
    limit = re.search(r'<limit [^>]*upper="\$\{1.3 \* max_steer\}"[^>]*velocity="([\d.]+)"',
                      urdf)
    actuators = yaml.safe_load(tool.VEHICLE_YAML.read_text())['actuators']
    assert limit and float(limit.group(1)) >= 4.0 * actuators['steer_rate']


def test_a_wrong_key_is_refused():
    with pytest.raises(KeyError):
        tool.main(['--no-figures', '--set', 'throtle_lag=0.2'])


def test_the_speed_loop_study_prints(capsys):
    assert tool.main(['--speed-loop', '--no-figures']) == 0
    out = capsys.readouterr().out
    assert 'The speed loop against the uncertainty' in out
    rows = [line for line in out.splitlines() if 'K (vehicle.yaml)' in line]
    today = next(r for r in rows if r.startswith('today (kp 0.3'))
    smooth = next(r for r in rows if r.startswith("'smooth'"))
    assert ' 17 % ' in today and ' 0 % ' in smooth


def test_the_speed_loop_study_follows_the_measured_numbers():
    model = tool.vm.VehicleModel().with_measured({'drag': 0.5})
    assert tool.plant_numbers(model, 0.2, 1.0) == {'max_accel': 1.5 * 0.2, 'drag': 0.5}
