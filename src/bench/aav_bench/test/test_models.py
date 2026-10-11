import math
import random

from aav_bench import models
import pytest

DATUM = (45.3860, -75.6960)


def truth(x=0.0, y=0.0, yaw=0.0, speed=0.0, yaw_rate=0.0, t=0.0):
    return models.Truth(t, x, y, yaw, speed, yaw_rate)


def test_offset_turns_with_the_car():
    assert models.offset(truth(), [0.8, 0.0, 1.5]) == pytest.approx((0.8, 0.0))
    north = models.offset(truth(x=10.0, yaw=math.pi / 2), [0.8, 0.0, 1.5])
    assert north == pytest.approx((10.0, 0.8))


def test_geo_from_map_matches_the_earths_size_at_ottawa():
    lat, lon = models.geo_from_map(0.0, 0.0, *DATUM)
    assert (lat, lon) == DATUM
    # At 45.386 degrees north, 1 degree of latitude is about 111.1 km; of longitude, 78.3 km.
    lat, lon = models.geo_from_map(1000.0, 1000.0, *DATUM)
    assert (lat - DATUM[0]) * 111_132 == pytest.approx(1000.0, rel=2e-3)
    assert (lon - DATUM[1]) * 78_313 == pytest.approx(1000.0, rel=1e-3)


def test_imu_reads_speeding_up_turning_and_gravity():
    accel, gyro = models.imu_reading(truth(speed=1.5, yaw_rate=0.2, t=1.0),
                                     truth(speed=1.0, t=0.5))
    assert accel == pytest.approx((1.0, 0.3, models.G))
    assert gyro == (0.0, 0.0, 0.2)
    accel, _ = models.imu_reading(truth(speed=1.0), None)
    assert accel[0] == 0.0


def test_magnetic_field_points_north():
    east = models.magnetic_field(0.0)        # facing east, north is on the left
    assert east[0] == pytest.approx(0.0) and east[1] > 0 and east[2] < 0
    north = models.magnetic_field(math.pi / 2)
    assert north[0] == pytest.approx(models.FIELD_NORTH_T) and north[1] == pytest.approx(0.0)


def test_noise_is_seeded_and_unbiased():
    a = models.noisy((1.0, 2.0, 3.0), 0.1, random.Random(5))
    assert a == models.noisy((1.0, 2.0, 3.0), 0.1, random.Random(5))
    rng = random.Random(7)
    mean = sum(models.noisy((0.0,), 0.1, rng)[0] for _ in range(5000)) / 5000
    assert abs(mean) < 0.01


def test_battery_drains_and_stops_at_empty():
    assert models.battery_voltage(0.0, 50.9, 46.0, 2.0) == 50.9
    assert models.battery_voltage(1.0, 50.9, 46.0, 2.0) == pytest.approx(48.45)
    assert models.battery_voltage(9.0, 50.9, 46.0, 2.0) == 46.0


CAM = models.Camera([1.8, 0.29, 1.2], 640, 360, 343.0, 1.2)


def test_a_sign_ahead_grows_as_the_car_gets_closer():
    far = models.sign_in_view(CAM, truth(x=0.0), (25.0, -2.0), 2.0, 0.75)
    near = models.sign_in_view(CAM, truth(x=18.0), (25.0, -2.0), 2.0, 0.75)
    assert far is not None and near is not None
    assert near.size > far.size
    assert near.size == pytest.approx(343.0 * 0.75 / (25.0 - 18.0 - 1.8), rel=1e-6)
    assert near.u > CAM.width / 2 and near.v < CAM.height / 2, 'right of centre, above it'


def test_signs_behind_or_too_far_aside_are_not_seen():
    assert models.sign_in_view(CAM, truth(x=30.0), (25.0, -2.0), 2.0, 0.75) is None
    assert models.sign_in_view(CAM, truth(x=24.0), (25.0, -2.0), 2.0, 0.75) is None


def test_pairs():
    assert models.pairs([1.0, 2.0, 3.0, 4.0]) == [(1.0, 2.0), (3.0, 4.0)]
    with pytest.raises(ValueError):
        models.pairs([1.0])


def test_a_camera_tilted_down_sees_the_sign_higher_up():
    level = models.sign_in_view(CAM, truth(x=10.0), (25.0, -2.0), 2.0, 0.75)
    tilted = models.Camera([1.8, 0.29, 1.2], 640, 360, 343.0, 1.2, pitch=0.1)
    down = models.sign_in_view(tilted, truth(x=10.0), (25.0, -2.0), 2.0, 0.75)
    assert down.v < level.v - 30.0
    # The post's foot is on the ground: height / distance below the horizon.
    assert level.foot_v == pytest.approx(180.0 + 343.0 * 1.2 / (25.0 - 10.0 - 1.8))


def test_the_road_runs_east_and_bends_where_asked():
    straight = models.Road(y=1.0)
    assert straight.lateral(50.0, 1.5) == pytest.approx(0.5)
    assert straight.pose(10.0, 0.7, 0.1) == pytest.approx((-0.3, 0.1))
    left = models.Road(bend_x=30.0, bend_radius=60.0)
    # A quarter of the way round, the road heads north; its inside (west) is on the left.
    assert left.lateral(90.0, 60.0) == pytest.approx(0.0)
    assert left.lateral(89.0, 60.0) == pytest.approx(1.0)
    assert left.pose(90.0, 60.0, math.pi / 2) == pytest.approx((0.0, 0.0))
    assert left.lateral(20.0, 0.3) == pytest.approx(0.3), 'straight before the bend'
    right = models.Road(bend_x=30.0, bend_radius=-60.0)
    assert right.lateral(89.0, -60.0) == pytest.approx(-1.0)
    assert right.pose(90.0, -60.0, -math.pi / 2) == pytest.approx((0.0, 0.0))
