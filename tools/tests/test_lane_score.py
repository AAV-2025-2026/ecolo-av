"""lane_score: the car's offset from its lane's centre, and a drive's numbers."""

import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lane_score as s  # noqa: E402, I100

TWO_WAY = s.Road('two way', ((0.0, 0.0), (100.0, 0.0)), 8.0)
ONE_WAY = s.Road('one way', ((0.0, 50.0), (100.0, 50.0)), 8.0, oneway=True)
LANE = (4.0 - s.EDGE_INSET) / 2.0     # m: a lane centre from the centre line, 8 m roads


def test_the_road_worlds_lane_is_its_middle():
    road = s.road_world()
    assert s.lane_error(road, 10.0, 0.3, 0.0)[0] == pytest.approx(0.3)
    # Facing west, left is south.
    assert s.lane_error(road, 10.0, 0.3, math.pi)[0] == pytest.approx(-0.3)
    assert s.lane_error(road, 10.0, 3.0, 0.0) == (None, None)


def test_a_two_way_road_keeps_right_whichever_way_the_car_goes():
    east, road = s.lane_error([TWO_WAY], 50.0, -LANE, 0.0)
    assert road is TWO_WAY and east == pytest.approx(0.0)
    west, _ = s.lane_error([TWO_WAY], 50.0, LANE, math.pi)
    assert west == pytest.approx(0.0)
    # Eastbound in the westbound lane: one lane left of where it should be.
    assert s.lane_error([TWO_WAY], 50.0, LANE, 0.0)[0] == pytest.approx(2 * LANE)


def test_a_one_way_road_has_two_lanes_to_choose_from():
    assert s.lane_error([ONE_WAY], 50.0, 50.0 + LANE + 0.5, 0.0)[0] == pytest.approx(0.5)
    assert s.lane_error([ONE_WAY], 50.0, 50.0 - LANE - 0.5, 0.0)[0] == pytest.approx(-0.5)


def test_the_nearest_road_counts():
    assert s.lane_error([TWO_WAY, ONE_WAY], 50.0, 49.0, 0.0)[1] is ONE_WAY


def test_a_drive_down_the_road_scores_its_error_time_and_lost_pictures():
    track = [(0.1 * k, 0.1 * k, 0.2 if k < 50 else -0.1, 0.0) for k in range(101)]
    lanes = [(0.0, True, True), (1.0, True, False), (2.0, False, False), (3.0, True, True)]
    got = s.score(s.road_world(), track, lanes)
    assert got.seconds == pytest.approx(10.0)
    assert got.mean_speed == pytest.approx(1.0, abs=0.04)    # the one sideways step adds
    assert got.max_error == pytest.approx(0.2)
    assert got.mean_error == pytest.approx((49 * 0.2 + 51 * 0.1) / 100)
    assert got.lost == pytest.approx(0.25) and got.both == pytest.approx(0.5)
    assert got.off_road == 0.0
    assert 'lateral error mean' in got.line()


def test_lanes_yaml_reads(tmp_path):
    path = tmp_path / 'lanes.yaml'
    path.write_text('roads:\n- {name: Library Road, kind: tertiary, width: 7.0, oneway: false,'
                    ' points: [[0, 0], [10, 0]]}\n- {name: x, kind: tertiary, width: 7,'
                    ' points: [[0, 0]]}\n')
    roads = s.load_roads(str(path))
    assert len(roads) == 1 and roads[0].name == 'Library Road' and roads[0].lanes == 2
