"""gz_crash: is a failed sim-check start-up Gazebo's own crash, worth one retry."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gz_crash  # noqa: E402

# From the nightly run on GitHub, 25 Oct.
NIGHTLY = """\
[gazebo-1] Segmentation fault (core dumped)
[ERROR] [gazebo-1]: process has died [pid 15290, exit code 139, cmd 'ruby gz sim -r -s'].
[ERROR] [ekf_node-19]: process has died [pid 15339, exit code -6, cmd 'ekf_node'].
"""


def test_the_nightly_segfault_is_a_crash():
    assert gazebo_crashed(NIGHTLY) == 'segmentation fault'


def test_another_nodes_abort_is_not_gazebos():
    log = "[ERROR] [ekf_node-19]: process has died [pid 15339, exit code -6, cmd 'ekf']."
    assert gazebo_crashed(log) == ''


def test_gazebo_stopped_normally_is_not_a_crash():
    log = ('[INFO] [gazebo-1]: process has finished cleanly [pid 1]\n'
           "[ERROR] [gazebo-1]: process has died [pid 2, exit code 1, cmd 'gz'].")
    assert gazebo_crashed(log) == ''


def test_an_abort_counts():
    assert gazebo_crashed('[ERROR] [gazebo-1]: process has died [pid 2, exit code -6, '
                          "cmd 'gz']") == 'abort'


gazebo_crashed = gz_crash.gazebo_crashed
