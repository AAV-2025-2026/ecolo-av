import math

from aav_lidar.ground import (ground_hit, max_safe_roll, VLP16_ELEVATIONS,
                              worst_ground_height)
import pytest

ROOF = (0.9, 0.0, 1.8)          # vehicle.yaml's lidar_link
RIGHT = -math.pi / 2            # azimuth: straight out to the right


def test_level_the_road_is_at_base_links_height_where_the_beam_lands():
    rng, z = ground_hit(0.0, (0.0, 0.0, 1.8), math.radians(-9.0), 0.0)
    assert z == pytest.approx(0.0, abs=1e-12)
    assert rng == pytest.approx(1.8 / math.tan(math.radians(9.0)))   # 11.4 m


def test_a_beam_at_or_above_level_never_lands():
    assert ground_hit(0.0, ROOF, math.radians(1.0), 0.0) is None
    assert ground_hit(0.0, ROOF, 0.0, RIGHT) is None


def test_rolled_right_the_road_on_the_right_rises_by_distance_times_tan_roll():
    roll = math.radians(2.0)
    rng, z = ground_hit(roll, (0.0, 0.0, 1.8), math.radians(-7.0), RIGHT)
    assert z == pytest.approx(rng * math.tan(roll), rel=1e-9)
    # ... and on the left it falls away.
    _, z_left = ground_hit(roll, (0.0, 0.0, 1.8), math.radians(-7.0), -RIGHT)
    assert z_left < 0


def test_a_beam_just_above_level_lands_when_rolled_past_it():
    # The +1 degree beam, the body rolled 2 degrees: it comes down on the low side, far out.
    rng, _ = ground_hit(math.radians(2.0), ROOF, math.radians(1.0), RIGHT)
    assert rng == pytest.approx(1.8 / math.tan(math.radians(1.0)), rel=0.05)


def test_the_todo_s_numbers_two_degrees_lifts_the_road_about_0_7_m_by_20_m():
    z, rng, *_ = worst_ground_height(math.radians(1.95), ROOF, 30.0)
    assert z == pytest.approx(0.7, abs=0.05)
    assert 18.0 < rng < 24.0


def test_level_nothing_on_the_road_counts():
    z, *_ = worst_ground_height(0.0, ROOF, 30.0)
    assert z == pytest.approx(0.0, abs=1e-9)


def test_rolling_either_way_is_the_same():
    a = worst_ground_height(math.radians(1.5), ROOF, 12.0)[0]
    b = worst_ground_height(math.radians(-1.5), ROOF, 12.0)[0]
    assert a == pytest.approx(b, abs=1e-6)


def test_the_car_s_lidar_is_safe_to_about_1_46_degrees_at_the_costmap_s_12_m():
    safe = math.degrees(max_safe_roll(ROOF, 0.3, 12.0))
    assert safe == pytest.approx(1.46, abs=0.03)
    # A shorter range is safer, a longer one less so.
    assert math.degrees(max_safe_roll(ROOF, 0.3, 8.0)) > 2.0
    assert math.degrees(max_safe_roll(ROOF, 0.3, 30.0)) < safe


def test_the_vlp16_has_16_beams_2_degrees_apart():
    assert len(VLP16_ELEVATIONS) == 16
    assert math.degrees(VLP16_ELEVATIONS[0]) == pytest.approx(-15.0)
