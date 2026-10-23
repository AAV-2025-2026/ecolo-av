"""tools/ci_annotate.py: failed tests become GitHub annotations."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ci_annotate  # noqa: E402

JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite name="pytest">
  <testcase classname="test_car_launch" name="test_ok"/>
  <testcase classname="test_car_launch" name="test_bad">
    <failure message="assert 1 == 2">Traceback\nline: a, b\nAssertionError</failure>
  </testcase>
  <testcase classname="test_x" name="test_broken"><error message="ImportError"/></testcase>
</testsuite></testsuites>
"""


def write_junit(build, text=JUNIT):
    folder = build / 'aav_bringup' / 'test_results' / 'aav_bringup'
    folder.mkdir(parents=True)
    (folder / 'test_car_launch.xunit.xml').write_text(text)


def test_one_annotation_per_failing_case(tmp_path):
    write_junit(tmp_path / 'build')
    out = ci_annotate.annotations(str(tmp_path / 'none.log'), str(tmp_path / 'build'))
    assert out == [
        '::error title=aav_bringup%3A test_car_launch test_bad::'
        'assert 1 == 2%0ATraceback%0Aline: a, b%0AAssertionError',
        '::error title=aav_bringup%3A test_x test_broken::ImportError',
    ]


def test_the_logs_end_when_no_case_failed(tmp_path):
    log = tmp_path / 'test.log'
    log.write_text('\n'.join(f'line {n}' for n in range(100)) + '\n100% done\n')
    out = ci_annotate.annotations(str(log), str(tmp_path / 'build'))
    assert len(out) == 1
    assert out[0].startswith('::error title=the end of the test step::line 61%0A')
    assert out[0].endswith('100%25 done%0A')


def test_at_most_ten(tmp_path):
    cases = ''.join(f'<testcase name="t{n}"><failure message="no"/></testcase>'
                    for n in range(15))
    write_junit(tmp_path / 'build', f'<testsuite>{cases}</testsuite>')
    out = ci_annotate.annotations(str(tmp_path / 'none.log'), str(tmp_path / 'build'))
    assert len(out) == 10
    assert out[-1].startswith('::error title=6 more failing tests::')


# The nightly sim job's first failure (23 Oct), as oirp-spss showed it: Gazebo crashed.
LAUNCH_LOG = """[INFO] [launch]: All log files can be found below /tmp/x
[gazebo-1] \x1b[1;31m[Err] [Ogre2RenderEngine.cc:752] \x1b[0mUnable to load Ogre Plugin
[gazebo-1] Segmentation fault (Address not mapped to object [(nil)])
[INFO] [ekf_global-15]: process started
[ERROR] [gazebo-1]: process has died [pid 1, exit code -11]
"""


def test_sim_fail_lines_and_launch_errors(tmp_path):
    step = tmp_path / 'sim.log'
    step.write_text('Starting...\nPASS  graph vs contract: 0 failures\n'
                    'FAIL  start-up: nothing from: truth, in 120 s\n| table |\n')
    launch = tmp_path / 'aav-sim-check.log'
    launch.write_text(LAUNCH_LOG)
    out = ci_annotate.sim_annotations(str(step), [str(launch)])
    assert out == [
        '::error title=sim-check::FAIL  start-up: nothing from: truth, in 120 s',
        '::error title=aav-sim-check.log%2C its last errors::'
        '[gazebo-1] [Err] [Ogre2RenderEngine.cc:752] Unable to load Ogre Plugin%0A'
        '[gazebo-1] Segmentation fault (Address not mapped to object [(nil)])%0A'
        '[ERROR] [gazebo-1]: process has died [pid 1, exit code -11]',
    ]


def test_sim_without_fail_lines_or_logs(tmp_path):
    step = tmp_path / 'sim.log'
    step.write_text('Traceback (most recent call last):\nKeyError: x\n')
    out = ci_annotate.sim_annotations(str(step), [str(tmp_path / 'gone.log')])
    assert out[0] == ('::error title=the end of sim-check::'
                      'Traceback (most recent call last):%0AKeyError: x%0A')
    assert out[1].endswith(f'::no {tmp_path}/gone.log')
    assert len(ci_annotate.sim_annotations(str(tmp_path / 'none.log'), [])) == 1


def test_sim_at_most_ten(tmp_path):
    step = tmp_path / 'sim.log'
    step.write_text(''.join(f'FAIL  check {n}\n' for n in range(12)))
    out = ci_annotate.sim_annotations(str(step), ['a.log', 'b.log'])
    assert len(out) == 10
    assert out[-2].startswith('::error title=a.log')
