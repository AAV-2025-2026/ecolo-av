"""drive_metrics: the numbers controller_compare.py reports, on made-up drives."""

import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive_metrics as m  # noqa: E402
import pytest  # noqa: E402

BODY = (2.0, 1.0, 0.2)      # length, width, rear overhang: vehicle.yaml's body


def straight(speed=1.0, seconds=10.0, rate=10.0, y=0.0, yaw=0.0):
    """Truth samples of a car driving along y at `speed`, heading `yaw` (0: east)."""
    n = int(seconds * rate)
    return [(i / rate, math.cos(yaw) * speed * i / rate, y + math.sin(yaw) * speed * i / rate,
             yaw) for i in range(n + 1)]


def test_distance_to_a_path_and_its_ends():
    path = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert m.path_distance((5.0, 2.0), path) == pytest.approx(2.0)
    assert m.path_distance((12.0, 5.0), path) == pytest.approx(2.0)   # beside the second leg
    assert m.path_distance((-3.0, 4.0), path) == pytest.approx(5.0)   # past the start
    assert m.path_distance((1.0, 1.0), [(1.0, 4.0)]) == pytest.approx(3.0)
    assert math.isnan(m.path_distance((0.0, 0.0), []))


def test_off_path_uses_the_newest_plan_at_each_moment():
    truth = straight(seconds=4.0, rate=1.0, y=1.0)          # t = 0..4, 1 m left of y = 0
    plans = [(0.5, [(0.0, 0.0), (10.0, 0.0)]),               # the first plan: y = 0
             (2.5, [(0.0, 1.0), (10.0, 1.0)])]               # a new one, through the car
    # t = 0: no plan yet; t = 1, 2: 1 m off; t = 3, 4: on it.
    assert m.off_path(truth, plans) == pytest.approx([1.0, 1.0, 0.0, 0.0])


def test_signed_speed_distance_stops_and_reversals():
    forward = straight(speed=1.0, seconds=5.0)
    assert m.travelled(forward) == pytest.approx(5.0)
    assert all(v == pytest.approx(1.0) for _, v in m.speeds(forward))
    # Forward 5 s, stand 2 s, back 3 s at 0.5 m/s: one stop, one reversal.
    t_end = forward[-1][0]
    still = [(t_end + i / 10.0, 5.0, 0.0, 0.0) for i in range(1, 21)]
    back = [(t_end + 2.0 + i / 10.0, 5.0 - 0.05 * i, 0.0, 0.0) for i in range(1, 31)]
    drive = forward + still + back
    assert any(v < 0 for _, v in m.speeds(drive))            # reverse: negative, heading east
    assert m.stops(drive) == 1
    assert m.reversals(drive) == 1
    # Standing still at the start or the end isn't a stop.
    waiting = [(i / 10.0, 0.0, 0.0, 0.0) for i in range(20)]
    assert m.stops(waiting + [(t + 2.0, x, y, yaw) for t, x, y, yaw in forward]) == 0
    assert m.stops(forward + still) == 0
    # Shorter than STOP_TIME: not a stop either.
    brief = forward + still[:5] + [(t + 0.5 - 2.0, x, y, yaw) for t, x, y, yaw in back]
    assert m.stops(brief) == 0


def test_the_cars_outline_and_its_gap_to_a_box():
    car = m.footprint(0.0, 0.0, 0.0, BODY)
    assert sorted(car) == sorted([(1.8, 0.5), (1.8, -0.5), (-0.2, -0.5), (-0.2, 0.5)])
    turned = m.footprint(0.0, 0.0, math.pi / 2, BODY)      # facing north: the nose at y 1.8
    assert max(p[1] for p in turned) == pytest.approx(1.8)
    box = m.square(5.0, 0.0, 1.0)                            # x 4.5..5.5
    assert m.polygon_distance(car, box) == pytest.approx(2.7)   # nose at 1.8
    assert m.polygon_distance(m.footprint(3.0, 0.0, 0.0, BODY), box) == 0.0   # overlaps
    beside = m.footprint(4.0, 2.0, 0.0, BODY)                # 1 m left of the box's side
    assert m.polygon_distance(beside, box) == pytest.approx(1.0)
    assert m.clearance(straight(seconds=2.0), (5.0, 0.0, 1.0), BODY) == pytest.approx(0.7)
    assert m.clearance(straight(), None, BODY) is None


def test_a_leg_summary():
    truth = straight(speed=1.0, seconds=10.0)
    leg = {'truth': truth, 'plans': [(0.0, [(0.0, 0.0), (20.0, 0.0)])],
           'steering': [(0.0, 0.0), (1.0, 0.1), (2.0, 0.1)], 'start': 0.0, 'end': 12.0,
           'asked': [(0.02, 0.0), (0.04, 0.3)],
           'goal': (10.0, 0.5, math.radians(10)), 'reached': True, 'cpu': 7.5,
           'obstacle': None, 'body': BODY}
    row = m.summary(leg)
    assert row['reached'] is True
    assert row['time_s'] == pytest.approx(12.0)
    assert row['driven_m'] == pytest.approx(10.0)
    assert row['off_path_mean_m'] == pytest.approx(0.0, abs=1e-9)
    assert row['off_path_max_m'] == pytest.approx(0.0, abs=1e-9)
    assert row['end_error_m'] == pytest.approx(0.5)
    assert row['end_heading_deg'] == pytest.approx(10.0)
    assert row['steering_rms'] == pytest.approx(math.sqrt(0.01 / 2))
    assert (row['stops'], row['reversals'], row['clearance_m']) == (0, 0, None)
    assert row['cpu_percent'] == 7.5
    assert row['moving_after_s'] == pytest.approx(0.1)      # 0.1 m at 1 m/s
    assert row['asked_after_s'] == pytest.approx(0.04)
    assert row['off_route_max_m'] == pytest.approx(0.0, abs=1e-9)
    assert row['route_m'] == pytest.approx(20.0)
    assert row['detour'] == pytest.approx(0.5)
    assert math.isnan(row['lingered_s'])         # no EKF recorded


def test_a_car_that_circles_a_goal_it_reached():
    # TODO 17: the EKF has the car at the goal at t = 9 s, but Nav2 answers at 30 s.
    belief = [(t, t, 0.0, 0.0) for t in range(12)]
    assert m.lingered(belief, (10.0, 0.0, 0.0), end=30.0) == pytest.approx(21.0)
    assert m.lingered(belief, (10.0, 0.0, 0.0), end=9.5) == pytest.approx(0.5)
    assert m.lingered(belief, (50.0, 0.0, 0.0), end=30.0) is None
    assert m.path_length([(0.0, 0.0), (3.0, 4.0), (3.0, 5.0)]) == pytest.approx(6.0)


def test_how_long_the_car_took_to_start():
    waiting = [(i / 10.0, 0.0, 0.0, 0.0) for i in range(30)]          # 3 s still
    drive = waiting + [(t + 3.0, x, y, yaw) for t, x, y, yaw in straight(seconds=2.0)]
    assert m.moving_after(drive, start=-1.0) == pytest.approx(4.1)   # sent 1 s before
    assert m.moving_after(waiting, start=0.0) is None
    assert m.moving_after([], start=0.0) is None


def test_off_the_route_sees_what_replanning_hides():
    # The car wanders 3 m left; each new plan starts where it is, so the newest plan
    # stays close, but the first route (y = 0) doesn't.
    truth = [(float(t), float(t), min(t, 3.0), 0.0) for t in range(6)]
    plans = [(t - 0.5, [(t, min(t, 3.0)), (30.0, 0.0)]) for t in range(6)]
    row = m.summary({'truth': truth, 'plans': plans, 'steering': [], 'start': 0.0,
                     'end': 5.0, 'goal': (30.0, 0.0, 0.0), 'reached': False, 'cpu': None,
                     'obstacle': None, 'body': BODY})
    assert row['off_route_max_m'] == pytest.approx(3.0, abs=0.01)
    assert row['off_path_max_m'] < 0.1


def test_thinning_keeps_the_first_and_the_last():
    samples = [(i / 10.0, i) for i in range(26)]                   # 0 .. 2.5 s
    assert [s[0] for s in m.thin(samples, 1.0)] == [0.0, 1.0, 2.0, 2.5]
    assert m.thin([], 1.0) == []


def test_the_table_has_a_column_each_and_leaves_out_numbers_nobody_has():
    row = m.summary({'truth': straight(), 'plans': [], 'steering': [], 'start': 0.0,
                     'end': 10.0, 'goal': (10.0, 0.0, 0.0), 'reached': False, 'cpu': None,
                     'obstacle': None, 'body': BODY})
    other = dict(row, reached=True, cpu_percent=12.0)
    text = m.table([('rpp', row), ('mppi', other)])
    lines = text.splitlines()
    assert lines[:4] == ['|  | rpp | mppi |', '|---|---:|---:|',
                         '| Reached the goal | **no** | yes |', '| Time (s) | 10 | 10 |']
    assert 'Closest to the box' not in text and 'Off the path' not in text
    assert '| follower CPU (%): controller_server, or aav_track | - | 12 |' in lines


def test_the_picture_puts_north_up():
    # Two plans, two lines: one leg's end isn't joined to the next one's start.
    tracks = [('rpp', 'blue', [[(0.0, 0.0), (10.0, 5.0)]], False),
              ('plan', 'grey', [[(0.0, 0.0), (10.0, 0.0)], [(20.0, 0.0), (30.0, 0.0)]], True)]
    blocks = [(20.0, 20.0, 40.0, 35.0, 'grey')]
    text = m.svg((-10.0, -10.0, 70.0, 50.0), tracks, blocks, [(10.0, 5.0, 'goal <1>')])
    root = ET.fromstring(text)                                  # well-formed, names escaped
    ns = '{http://www.w3.org/2000/svg}'
    assert float(root.get('width')) == 640.0                    # 80 m at 8 px/m
    lines = root.findall(ns + 'polyline')
    assert len(lines) == 3
    # Map (0, 0) is 10 m right of the left edge and 50 m below the top: y points up.
    assert lines[0].get('points').split()[:2] == ['80.0,400.0', '160.0,360.0']
    assert lines[1].get('stroke-dasharray') and not lines[0].get('stroke-dasharray')
    building = root.findall(ns + 'rect')[1]                     # after the white page
    assert (building.get('x'), building.get('y')) == ('240.0', '120.0')   # its north-west
    assert [t.text for t in root.findall(ns + 'text')] == ['goal <1>', 'rpp', 'plan', '10 m']


def test_where_the_ekf_put_the_car_against_the_truth():
    truth = [(t * 0.1, t * 0.1, 0.0, 0.0) for t in range(20)]       # east at 1 m/s
    # The EKF: 0.3 m to the side, then 20 degrees off, matched by the nearest time.
    belief = [(0.52, 0.5, 0.3, 0.0), (1.49, 1.5, 0.0, math.radians(20))]
    gaps, turns = m.belief_errors(truth, belief)
    assert gaps == [pytest.approx(0.3), pytest.approx(0.0, abs=1e-9)]
    assert turns == [pytest.approx(0.0), pytest.approx(math.radians(20))]
    assert m.belief_errors([], belief) == ([], [])


def test_a_plan_that_takes_another_route_counts():
    east = [(float(x), 0.0) for x in range(11)]
    shorter = [(float(x), 0.0) for x in range(2, 11)]                # the car moved on
    north = [(2.0, 0.0)] + [(2.0 + x, 4.0) for x in range(9)]        # round the other side
    plans = [(0.0, east), (1.0, shorter), (2.0, north), (3.0, north), (4.0, [])]
    assert m.route_switches(plans) == 1
    assert m.route_switches([]) == 0


# --- A to B ---

def a_to_b_profile(rate=100.0):
    """
    Speeds and commands of a known A-to-B drive, at `rate` Hz.

    Still 1 s; up at 0.5 m/s^2 to 2 m/s (t = 1..5); hold 2 m/s (5..15); down at 1 m/s^2
    (15..17); still 2 s. Asked: 2 m/s from t = 1, 1 m/s from 15, 0 from 16.
    """
    def v(t):
        if t < 1.0:
            return 0.0
        if t < 5.0:
            return 0.5 * (t - 1.0)
        if t < 15.0:
            return 2.0
        return max(0.0, 2.0 - (t - 15.0))

    def asked(t):
        return 0.0 if t < 1.0 else 2.0 if t < 15.0 else 1.0 if t < 16.0 else 0.0
    times = [i / rate for i in range(int(19 * rate) + 1)]
    return [(t, v(t)) for t in times], [(t, asked(t)) for t in times]


def test_the_stop_error_along_and_across_the_line():
    assert m.stop_error((0.0, 0.0), (10.0, 0.0), (10.3, -0.2)) == pytest.approx((0.3, -0.2))
    # A line going north: left of it is west.
    assert m.stop_error((0.0, 0.0), (0.0, 10.0), (-0.5, 9.0)) == pytest.approx((-1.0, 0.5))
    with pytest.raises(ValueError):
        m.stop_error((1.0, 1.0), (1.0, 1.0), (0.0, 0.0))


def test_overshoot_past_b_counts_the_worst_moment():
    a, b = (0.0, 0.0), (10.0, 0.0)
    rolled_back = [(0.0, 0.0, 0.0), (1.0, 10.4, 0.1), (2.0, 10.1, 0.1)]
    assert m.overshoot_past(a, b, rolled_back) == pytest.approx(0.4)
    assert m.overshoot_past(a, b, [(0.0, 0.0, 0.0), (1.0, 9.8, 0.0)]) == 0.0


def test_speeding_up_and_holding():
    speeds, commands = a_to_b_profile()
    # 90 % of 2 m/s is 1.8 m/s, at t = 4.6: 3.6 s after the first command (t = 1).
    assert m.reach_time(speeds, 2.0, start=1.0) == pytest.approx(3.6, abs=0.011)
    assert m.reach_time(speeds, 3.0) is None
    t0, t1 = m.hold_window(speeds, 2.0, commands)
    assert (t0, t1) == (pytest.approx(4.6, abs=0.011), pytest.approx(15.0))
    # Without commands: until the last moment at 1.8 m/s (t = 15.2).
    assert m.hold_window(speeds, 2.0)[1] == pytest.approx(15.2, abs=0.011)
    assert m.overshoot_percent(speeds, 2.0) == 0.0
    assert m.hold_window(speeds, 5.0) is None
    assert math.isnan(m.hold_error(speeds, 5.0, None))


def test_hold_error_and_overshoot_on_a_made_up_hold():
    # 2.1 m/s for 2 s, with one peak of 2.2 m/s: 0.1 m/s fast, 10 % over.
    held = [(i / 10.0, 2.1) for i in range(21)]
    assert m.hold_error(held, 2.0, (0.0, 2.0)) == pytest.approx(0.1)
    assert m.hold_error(held, 2.0, (0.5, 0.5)) == pytest.approx(0.1)    # one sample
    held[10] = (1.0, 2.2)
    assert m.overshoot_percent(held, 2.0) == pytest.approx(10.0)


def test_smoothing_keeps_a_straight_line_and_drops_the_half_windows():
    line = [(i / 100.0, 3.0 * i / 100.0) for i in range(101)]        # 1 s
    out = m.smooth(line, 0.5)
    assert out[0][0] == pytest.approx(0.25) and out[-1][0] == pytest.approx(0.75)
    assert all(v == pytest.approx(3.0 * t) for t, v in out)
    assert m.smooth([], 0.5) == []


def test_peak_deceleration_and_jerk():
    speeds, _ = a_to_b_profile()
    assert m.peak_deceleration(speeds) == pytest.approx(1.0)
    # The steps in acceleration (the biggest: 1 m/s^2 at t = 15 and 17) read as about
    # da / width: 1 / 0.5 s (51 samples of 0.01 s: 1 / 0.51).
    assert m.peak_jerk(speeds) == pytest.approx(1.0 / 0.51, rel=0.02)
    # A constant jerk reads exactly: v = 2 - 0.25 t^2, a = -0.5 t, jerk -0.5 m/s^3.
    curve = [(i / 100.0, 2.0 - 0.25 * (i / 100.0) ** 2) for i in range(201)]
    assert m.peak_jerk(curve) == pytest.approx(0.5)
    assert math.isnan(m.peak_deceleration(speeds[:5]))
    assert math.isnan(m.peak_jerk(speeds[:5]))


def test_the_stop_coasting_and_creeping():
    speeds, commands = a_to_b_profile()
    # Under 0.05 m/s from t = 16.95 on: stopped then.
    assert m.stopped_at(speeds) == pytest.approx(16.96, abs=0.011)
    assert m.stopped_at(speeds[:1000]) is None                       # still driving
    assert m.stopped_at([(0.0, 0.0), (1.0, 0.0)]) is None             # never moved
    # Slowing from the last moment at 1.8 m/s (t = 15.2).
    assert m.slowing_time(speeds, 2.0) == pytest.approx(1.76, abs=0.02)
    assert m.slowing_time(speeds) == pytest.approx(1.76, abs=0.02)   # the top speed: 2
    # The command went to 0 at t = 16: from 1 m/s at 1 m/s^2, 0.5 m.
    assert m.coast_distance(speeds, commands) == pytest.approx(0.5)
    assert math.isnan(m.coast_distance(speeds, []))
    assert math.isnan(m.coast_distance(speeds, commands[:1000]))      # still asking
    # The last metre, from sqrt(2) m/s at 1 m/s^2: sqrt(2) s; under 0.15 m/s for
    # 0.15^2 / 2 m. A stop counted at exactly 0 m/s, so the numbers come out clean.
    seconds, crept = m.final_metre(speeds, still=1e-6)
    assert seconds == pytest.approx(math.sqrt(2.0), abs=0.01)
    assert crept == pytest.approx(0.15 ** 2 / 2.0, abs=1e-3)
    assert all(math.isnan(x) for x in m.final_metre(speeds[:1000]))
    short = [(0.0, 0.0), (1.0, 0.5), (2.0, 0.0)]                      # 0.5 m in all
    assert all(math.isnan(x) for x in m.final_metre(short))


def test_distance_from_speeds_clips_to_the_times():
    speeds = [(0.0, 1.0), (2.0, 1.0), (4.0, -1.0)]
    assert m.distance(speeds) == pytest.approx(3.0)       # 2 m; then 1 to -1: 0.5 m each way
    assert m.distance(speeds, 1.0, 2.0) == pytest.approx(1.0)


def test_the_table_takes_other_columns():
    cols = [('a', 'A (m)', '{:.1f}'), ('b', 'B', '{:d}')]
    text = m.table([('run', {'a': 1.25})], columns=cols)
    assert text.splitlines() == ['|  | run |', '|---|---:|', '| A (m) | 1.2 |']


def test_amcl_and_the_trackers_tick_are_scored_when_recorded():
    truth = [(float(t), float(t), 0.0, 0.0) for t in range(11)]
    leg = {'truth': truth, 'plans': [(0.0, [(0.0, 0.0), (10.0, 0.0)])], 'steering': [],
           'asked': [], 'start': 0.0, 'end': 10.0, 'goal': (10.0, 0.0, 0.0),
           'reached': True, 'body': (2.0, 1.0, 0.2),
           'belief': [(float(t), t + 0.2, 0.0, 0.0) for t in range(11)],
           'amcl': [(2.0, 2.0, 0.5, 0.0), (6.0, 6.0, 0.1, math.radians(10))],
           'loops': [(1.0, 0.5, 0.5, 0), (2.0, 1.5, 2.0, 1), (3.0, 1.0, 2.0, 3)]}
    row = m.summary(leg)
    assert row['amcl_samples'] == 2
    assert row['amcl_mean_m'] == pytest.approx(0.3)
    assert row['amcl_max_m'] == pytest.approx(0.5)
    assert row['amcl_heading_max_deg'] == pytest.approx(10.0)
    assert row['belief_mean_m'] == pytest.approx(0.2)
    assert row['loop_ms_mean'] == pytest.approx(1.0)
    assert row['loop_ms_max'] == pytest.approx(2.0)
    assert row['missed_ticks'] == 3
    # Without them, no such numbers: today's table is unchanged.
    plain = m.summary({k: v for k, v in leg.items() if k not in ('amcl', 'loops')})
    assert 'amcl_mean_m' not in plain and 'loop_ms_mean' not in plain


def test_runs_combine_into_a_mean_and_a_spread():
    rows = [{'reached': True, 'time_s': 30.0, 'stops': 1, 'off_path_mean_m': 0.1,
             'end_error_m': 0.5, 'clearance_m': math.nan, 'cpu_percent': None},
            {'reached': False, 'time_s': 40.0, 'stops': 2, 'off_path_mean_m': 0.3,
             'end_error_m': 0.7, 'clearance_m': math.nan, 'cpu_percent': None}]
    out = m.combine(rows + [None])
    assert out['reached'] is False and out['runs_reached'] == '1/2'
    assert out['time_s'] == pytest.approx(35.0)
    assert out['time_s_sd'] == pytest.approx(math.sqrt(50.0))
    assert out['off_path_mean_m_sd'] == pytest.approx(math.sqrt(0.02))
    assert isinstance(out['stops'], int)
    assert math.isnan(out['clearance_m']) and out['cpu_percent'] is None
    one = m.combine(rows[:1])
    assert one['runs_reached'] == '1/1' and 'time_s_sd' not in one
    assert m.combine([]) == {}
    assert 'Runs that reached the goal' in m.table([('rpp', out)])
