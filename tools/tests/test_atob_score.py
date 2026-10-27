"""atob_score: the A-to-B scorer, on made-up runs (CSV); a bag too, where ROS is."""

import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atob_score as ab  # noqa: E402
import pytest  # noqa: E402

try:
    from geometry_msgs.msg import TwistStamped
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    import rosbag2_py
    HAVE_ROS = True
except ImportError:
    HAVE_ROS = False
try:
    from aav_interfaces.action import DriveToPoint     # our messages: through tools/ros.sh
    HAVE_OURS = HAVE_ROS
except ImportError:
    HAVE_OURS = False

# Not importorskip, and not at module level: the CSV tests run everywhere.
needs_ros = pytest.mark.skipif(not HAVE_ROS, reason='needs rosbag2_py (ROS 2)')
needs_ours = pytest.mark.skipif(not HAVE_OURS,
                                reason='needs aav_interfaces: tools/ros.sh python3 -m pytest')

RATE = 100.0


def speed(t):
    """Up at 0.5 m/s^2 from t = 1 to 2 m/s (t = 5), hold to 15, down at 1 m/s^2 to 17."""
    if t < 1.0:
        return 0.0
    if t < 5.0:
        return 0.5 * (t - 1.0)
    if t < 15.0:
        return 2.0
    return max(0.0, 2.0 - (t - 15.0))


def where(t):
    """Distance (m) driven by t: 4 m speeding up, 20 m holding, 2 m stopping: 26 m."""
    if t < 1.0:
        return 0.0
    if t < 5.0:
        return 0.25 * (t - 1.0) ** 2
    if t < 15.0:
        return 4.0 + 2.0 * (t - 5.0)
    s = min(t, 17.0) - 15.0
    return 24.0 + 2.0 * s - 0.5 * s * s


def made_up_run(ekf_off=(0.3, 0.2)):
    """
    Return a run east along y = 0, stopping at x = 26: the truth, the EKF `ekf_off` m off.

    Asked 2 m/s from t = 1, 1 m/s from 15, 0 from 16.
    """
    run = ab.empty_run()
    for i in range(int(19 * RATE) + 1):
        t = i / RATE
        x, v = where(t), speed(t)
        run['truth'].append((t, x, 0.0, v))
        run['ekf'].append((t, x + ekf_off[0], ekf_off[1], v))
        run['cmd'].append((t, 0.0 if t < 1.0 else 2.0 if t < 15.0 else
                           1.0 if t < 16.0 else 0.0))
    return run


def test_utm_and_the_map_frame_match_geographiclib():
    # aav_hud map-core earth.rs's reference numbers (GeographicLib's GeoConvert).
    e, n, gamma = ab.utm(45.3860, -75.6960, 18)
    assert e == pytest.approx(445514.1385, abs=1e-3)
    assert n == pytest.approx(5026067.1450, abs=1e-3)
    assert math.degrees(gamma) == pytest.approx(-0.49546284270, abs=1e-8)
    e, n, _ = ab.utm(-33.9, 151.2, 56)
    assert e == pytest.approx(333568.9410, abs=1e-3)
    assert n == pytest.approx(6247473.3368, abs=1e-3)
    assert ab.utm_zone(-75.696) == 18 and ab.utm_zone(151.2) == 56
    datum = (45.3860, -75.6960)
    assert ab.to_map(*datum, datum) == pytest.approx((0.0, 0.0), abs=1e-9)
    for lat, lon, x, y in [(45.3835, -75.6974, -109.6068, -277.7464),
                           (45.4215, -75.6972, -93.8754, 3944.0251)]:
        assert ab.to_map(lat, lon, datum) == (pytest.approx(x, abs=0.01),
                                              pytest.approx(y, abs=0.01))


def test_the_datum_comes_from_navsat_yaml():
    assert ab.load_datum() == pytest.approx((45.3860, -75.6960))


def test_b_from_the_point_drivers_feedback():
    b, heading = (20.0, 5.0), math.radians(30.0)
    ux, uy = math.cos(heading), math.sin(heading)
    ekf, feedback = [], []
    # Turning first (ignored: no line yet), then 15 m along the line, wavering +-0.2 m.
    feedback.append((0.0, ab.TURN, 18.0, 0.0, 'g'))
    ekf.append((0.0, 0.0, 0.0, 0.0))
    for i in range(16):
        t, d, c = 1.0 + i, 15.0 - i, 0.2 * math.sin(i)
        ekf.append((t, b[0] - d * ux - c * uy, b[1] - d * uy + c * ux, 1.0))
        feedback.append((t, 2, d, c, 'g'))
    a, found = ab.goal_from_feedback(ekf, feedback)
    assert found == (pytest.approx(20.0), pytest.approx(5.0))
    assert a == (pytest.approx(20.0 - 15.0 * ux), pytest.approx(5.0 - 15.0 * uy))
    assert ab.goal_from_feedback(ekf, feedback[:2]) is None        # one sample on the line
    assert ab.goal_from_feedback([], feedback) is None


def test_a_sim_run_scored_against_the_truth(tmp_path):
    run = made_up_run()
    path = tmp_path / 'run.csv'
    ab.write_csv(run, path)
    row = ab.score(ab.read_csv(path), a=(0.0, 0.0), b=(26.1, 0.0))
    assert (row['b_from'], row['speed_from']) == ('given', 'truth')
    assert row['set_speed'] == 2.0 and row['top_speed'] == pytest.approx(2.0)
    assert row['line_m'] == pytest.approx(26.1)
    assert ab.score(run, b=(26.1, 0.0))['a'] == (0.3, 0.2)   # no A: the EKF's first pose
    assert row['reach_s'] == pytest.approx(3.6, abs=0.011)   # asked at 1 s, 1.8 m/s at 4.6
    assert row['overshoot_pct'] == 0.0
    assert -0.01 < row['hold_error'] < 0.0                   # 1.8 -> 2 m/s at its start
    assert row['decel_peak'] == pytest.approx(1.0)
    assert row['coast_m'] == pytest.approx(0.5)              # from 1 m/s at 1 m/s^2
    # The truth stops 0.1 m short of B; the EKF thinks 0.2 m past and 0.2 m left.
    assert row['truth_along'] == pytest.approx(-0.1) and row['truth_past'] == 0.0
    assert row['truth_across'] == pytest.approx(0.0, abs=1e-9)
    assert row['ekf_along'] == pytest.approx(0.2) and row['ekf_past'] == pytest.approx(0.2)
    assert row['ekf_across'] == pytest.approx(0.2)
    # The GPS part: real (the truth) - the EKF.
    assert (row['gps_along'], row['gps_across']) == (pytest.approx(-0.3), pytest.approx(-0.2))


def test_a_car_run_with_the_taped_stop():
    run = made_up_run()
    run['truth'], run['wheel'] = [], [(t, v) for t, _, _, v in run['truth']]
    row = ab.score(run, a=(0.0, 0.0), b=(26.1, 0.0), taped=(-0.15, 0.05))
    assert row['speed_from'] == 'wheels'
    assert 'truth_along' not in row
    assert (row['taped_along'], row['taped_across']) == (-0.15, 0.05)
    assert (row['gps_along'], row['gps_across']) == (pytest.approx(-0.35),
                                                     pytest.approx(-0.15))


def test_no_b_is_an_error_and_b_can_come_from_the_csv(tmp_path):
    run = made_up_run()
    with pytest.raises(ValueError, match='no B'):
        ab.score(run)
    run['b'] = (26.1, 0.0)
    path = tmp_path / 'run.csv'
    ab.write_csv(run, path)
    assert ab.score(ab.read_csv(path))['b_from'] == 'the CSV'
    assert ab.score(run, set_speed=2.5)['reach_s'] is None       # never 2.25 m/s


def test_the_run_is_the_last_goal_or_the_cut():
    run = ab.empty_run()
    run['cmd'] = [(float(t), 1.0) for t in range(100)]
    run['feedback'] = [(10.0, 2, 5.0, 0.0, 'one'), (20.0, 2, 1.0, 0.0, 'one'),
                       (50.0, 2, 5.0, 0.0, 'two'), (60.0, 4, 0.0, 0.0, 'two')]
    last = ab.last_goal(run)
    assert [s[4] for s in last['feedback']] == ['two', 'two']
    assert (last['cmd'][0][0], last['cmd'][-1][0]) == (49.0, 62.0)   # 1 s before, 2 s after
    cut = ab.cut(run, 5.0, 7.0)
    assert [s[0] for s in cut['cmd']] == [5.0, 6.0, 7.0] and cut['feedback'] == []
    assert ab.last_goal(ab.empty_run()) == ab.empty_run()


def test_the_command_line_table_and_json(tmp_path, capsys):
    path = tmp_path / 'sim.csv'
    ab.write_csv(made_up_run(), path)
    assert ab.main([str(path), '--b-xy', '26.1', '0']) == 0
    text = capsys.readouterr().out
    assert text.splitlines()[0] == '|  | sim.csv |'
    assert '| Stop by the truth: past B (m) | -0.10 |' in text
    assert 'tape' not in text                                     # nobody taped it
    assert ab.main([str(path), '--b-xy', '26.1', '0', '--json', '--taped', '-0.15', '0.05']) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]['run'] == 'sim.csv' and rows[0]['taped_along'] == -0.15
    assert rows[0]['b'] == [26.1, 0.0]
    assert ab.main([str(path)]) == 2                              # no B
    with pytest.raises(SystemExit):
        ab.main([str(path), str(path), '--b-xy', '1', '0', '--taped', '0', '0'])


def test_b_as_a_gps_point(tmp_path, capsys):
    run = made_up_run()
    datum = (45.3860, -75.6960)
    path = tmp_path / 'run.csv'
    ab.write_csv(run, path)
    # The GPS point that navsat_transform puts at map (26.1, 0), found by a search.
    lat, lon = datum
    for _ in range(5):
        x, y = ab.to_map(lat, lon, datum)
        lat += (0.0 - y) / 111_000.0
        lon += (26.1 - x) / (111_000.0 * math.cos(math.radians(lat)))
    assert ab.main([str(path), '--b-latlon', str(lat), str(lon), '--json']) == 0
    row = json.loads(capsys.readouterr().out)[0]
    assert row['truth_along'] == pytest.approx(-0.1, abs=1e-3)


@needs_ros
def test_a_bag_reads_as_the_csv_does(tmp_path):
    run = made_up_run()
    uri = str(tmp_path / 'bag')
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=uri, storage_id='mcap'),
                rosbag2_py.ConverterOptions('cdr', 'cdr'))
    topics = [(ab.EKF, 'nav_msgs/msg/Odometry'), (ab.TRUTH, 'nav_msgs/msg/Odometry'),
              ('/control/cmd_vel', 'geometry_msgs/msg/TwistStamped')]
    for i, (name, kind) in enumerate(topics):
        writer.create_topic(rosbag2_py.TopicMetadata(id=i, name=name, type=kind,
                                                     serialization_format='cdr'))
    t0 = 1_700_000_000 * 10 ** 9           # a wall-clock time, as a recording has
    for (t, x, y, v), (_, tx, ty, tv), (_, c) in zip(run['ekf'], run['truth'], run['cmd']):
        stamp = t0 + round(t * 1e9)
        for name, (px, py, pv) in ((ab.EKF, (x, y, v)), (ab.TRUTH, (tx, ty, tv))):
            msg = Odometry()
            msg.pose.pose.position.x, msg.pose.pose.position.y = px, py
            msg.twist.twist.linear.x = pv
            writer.write(name, serialize_message(msg), stamp)
        cmd = TwistStamped()
        cmd.twist.linear.x = c
        writer.write('/control/cmd_vel', serialize_message(cmd), stamp)
    del writer                             # closes the bag
    got = ab.read_run(uri)
    assert len(got['ekf']) == len(run['ekf']) and len(got['cmd']) == len(run['cmd'])
    row = ab.score(got, a=(0.0, 0.0), b=(26.1, 0.0))
    assert row['truth_along'] == pytest.approx(-0.1)
    assert row['reach_s'] == pytest.approx(3.6, abs=0.011)
    assert row['coast_m'] == pytest.approx(0.5, abs=1e-6)
    # --start/--end count from the bag's first message.
    assert ab.cut(got, 0.0, 2.0)['ekf'][-1][0] - got['ekf'][0][0] == pytest.approx(2.0)


NEW = {'cmd': '/drivers/point/cmd_vel', 'feedback': '/drive_to_point/_action/feedback',
       'type': 'aav_interfaces/action/DriveToPoint_FeedbackMessage'}
# aav_goto's names, before 26 Oct: bags recorded then must still score.
OLD = {'cmd': '/drivers/goto/cmd_vel', 'feedback': '/goto/_action/feedback',
       'type': 'aav_interfaces/action/GoTo_FeedbackMessage'}


@pytest.mark.parametrize('names', [NEW, OLD], ids=['new', 'before-26-oct'])
def test_the_point_drivers_topics_new_names_and_old(names):
    types = {ab.EKF: 'nav_msgs/msg/Odometry',
             '/control/cmd_vel': 'geometry_msgs/msg/TwistStamped',
             names['cmd']: 'geometry_msgs/msg/TwistStamped',
             names['feedback']: names['type']}
    command, feedback, wanted = ab.bag_topics(types)
    assert (command, feedback) == (names['cmd'], names['feedback'])
    # The old action type reads as the new one: the same fields.
    assert wanted[feedback] == NEW['type']
    assert set(wanted) == {ab.EKF, names['cmd'], names['feedback']}
    # Neither recorded: /control/cmd_vel, and no feedback.
    command, feedback, _ = ab.bag_topics({ab.EKF: 'nav_msgs/msg/Odometry',
                                          '/control/cmd_vel': 'geometry_msgs/msg/TwistStamped'})
    assert (command, feedback) == ('/control/cmd_vel', None)


@needs_ours
@pytest.mark.parametrize('names', [NEW, OLD], ids=['new', 'before-26-oct'])
def test_a_bag_with_the_point_drivers_feedback_finds_b(tmp_path, names):
    """A recorded drive to B = (20, 0): B comes from the feedback, under either name."""
    uri = str(tmp_path / 'bag')
    writer = rosbag2_py.SequentialWriter()
    writer.open(rosbag2_py.StorageOptions(uri=uri, storage_id='mcap'),
                rosbag2_py.ConverterOptions('cdr', 'cdr'))
    topics = [(ab.EKF, 'nav_msgs/msg/Odometry'),
              (names['cmd'], 'geometry_msgs/msg/TwistStamped'),
              (names['feedback'], names['type'])]
    for i, (name, kind) in enumerate(topics):
        writer.create_topic(rosbag2_py.TopicMetadata(id=i, name=name, type=kind,
                                                     serialization_format='cdr'))
    t0 = 1_700_000_000 * 10 ** 9
    for i in range(16):
        stamp = t0 + i * 10 ** 9
        odom = Odometry()
        odom.pose.pose.position.x = float(i + 4)
        odom.twist.twist.linear.x = 1.0
        writer.write(ab.EKF, serialize_message(odom), stamp)
        cmd = TwistStamped()
        cmd.twist.linear.x = 1.0
        writer.write(names['cmd'], serialize_message(cmd), stamp)
        fb = DriveToPoint.Impl.FeedbackMessage()
        fb.goal_id.uuid = [7] * 16
        fb.feedback.phase = 2
        fb.feedback.distance_left = 20.0 - (i + 4)
        writer.write(names['feedback'], serialize_message(fb), stamp)
    del writer
    run = ab.read_run(uri)
    assert len(run['cmd']) == 16 and len(run['feedback']) == 16
    _, b = ab.goal_from_feedback(run['ekf'], run['feedback'])
    assert b == (pytest.approx(20.0), pytest.approx(0.0, abs=1e-6))
