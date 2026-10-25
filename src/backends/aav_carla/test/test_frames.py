"""frames.py: CARLA's left-handed degrees to REP-103's right-handed radians, and back."""

import math

from aav_carla import frames
import pytest

DATUM = (45.3860, -75.6960)


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_a_point_flips_its_y_and_back():
    assert frames.location_to_ros(1.0, 2.0, 3.0) == (1.0, -2.0, 3.0)
    assert frames.ros_to_location(*frames.location_to_ros(1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_a_right_turn_in_carla_is_a_negative_yaw_in_ros():
    roll, pitch, yaw = frames.rotation_to_ros(0.0, 0.0, 90.0)   # CARLA: facing its +y, right
    assert yaw == pytest.approx(-math.pi / 2)
    # Nose up in CARLA (pitch +) is nose up in ROS too, which REP-103 writes as pitch -.
    assert frames.rotation_to_ros(0.0, 10.0, 0.0)[1] == pytest.approx(-math.radians(10.0))
    assert frames.rotation_to_ros(5.0, 0.0, 0.0)[0] == pytest.approx(math.radians(5.0))


def test_rotations_go_there_and_back():
    r = (0.1, -0.2, 2.5)
    assert close(frames.rotation_to_ros(*frames.ros_to_rotation(*r)), r)


def test_a_heading_and_its_velocity_agree():
    # A CARLA car facing yaw 30 deg (to the right of +x) moving forward at 2 m/s: its
    # velocity is (cos 30, sin 30) * 2 in CARLA; in ROS it must be forward along its yaw.
    yaw_c = 30.0
    v_c = (2 * math.cos(math.radians(yaw_c)), 2 * math.sin(math.radians(yaw_c)), 0.0)
    vx, vy, _ = frames.location_to_ros(*v_c)
    yaw = frames.rotation_to_ros(0.0, 0.0, yaw_c)[2]
    fwd, left = frames.body_velocity(vx, vy, yaw)
    assert fwd == pytest.approx(2.0)
    assert left == pytest.approx(0.0, abs=1e-12)


def test_a_left_turn_reads_positive_yaw_rate():
    # Turning left in CARLA: its yaw (degrees, + right) goes down, so the rate about its z
    # is negative; ours is positive, rad/s.
    assert frames.angular_velocity_to_ros(0.0, 0.0, -57.29577951)[2] == pytest.approx(1.0)
    assert frames.gyroscope_to_ros(0.0, 0.0, -0.4)[2] == pytest.approx(0.4)


@pytest.mark.parametrize('rpy', [(0.0, 0.0, 0.0), (0.0, 0.0, 1.2), (0.3, -0.2, -2.0)])
def test_the_quaternion_is_a_unit_one_with_the_right_yaw(rpy):
    x, y, z, w = frames.quaternion(*rpy)
    assert x * x + y * y + z * z + w * w == pytest.approx(1.0)
    if rpy[0] == rpy[1] == 0.0:
        assert 2 * math.atan2(z, w) == pytest.approx(rpy[2])


@pytest.mark.parametrize('a, wrapped', [(0.0, 0.0), (math.pi, math.pi), (-math.pi, math.pi),
                                        (3 * math.pi / 2, -math.pi / 2), (7.0, 7.0 - 2 * math.pi)])
def test_wrap(a, wrapped):
    assert frames.wrap(a) == pytest.approx(wrapped)


def test_the_spawn_point_becomes_the_origin_facing_east():
    f = frames.SpawnFrame(10.0, -5.0, math.pi / 2)    # facing north, ROS axes
    assert close(f.point(10.0, -5.0), (0.0, 0.0))
    # 3 m ahead of a car facing north is 3 m east in our frame (it faces east there).
    assert close(f.point(10.0, -2.0), (3.0, 0.0))
    assert close(f.vector(0.0, 1.0), (1.0, 0.0))
    assert f.heading(math.pi / 2) == pytest.approx(0.0)


def test_metres_to_degrees_and_back_round_carleton():
    lat, lon, alt = frames.enu_to_geodetic(*DATUM, 70.0, 100.0, 200.0, 1.5)
    # A degree of latitude is about 111.1 km here, a degree of longitude about 78.4 km.
    assert (lat - DATUM[0]) * 111_140 == pytest.approx(200.0, rel=2e-3)
    assert (lon - DATUM[1]) * 78_440 == pytest.approx(100.0, rel=3e-3)
    assert alt == pytest.approx(71.5)
    e, n, u = frames.geodetic_to_enu(*DATUM, 70.0, lat, lon, alt)
    assert close((e, n, u), (100.0, 200.0, 1.5), 1e-6)


def test_a_twin_round_the_datum_is_the_world_frame():
    # CARLA's origin 30 m east and 40 m north of the datum: our point = CARLA's + offset.
    lat, lon, _ = frames.enu_to_geodetic(*DATUM, 0.0, 30.0, 40.0, 0.0)
    f, kind = frames.map_frame(lat, lon, *DATUM, spawn=(5.0, 5.0, 1.0))
    assert kind == 'world'
    assert close(f.point(0.0, 0.0), (30.0, 40.0), 1e-6)
    assert f.heading(0.3) == pytest.approx(0.3)


def test_a_stock_town_uses_the_spawn_point():
    f, kind = frames.map_frame(0.0, 0.0, *DATUM, spawn=(5.0, 5.0, 1.0))
    assert kind == 'spawn'
    assert f == frames.SpawnFrame(5.0, 5.0, 1.0)
    # ... unless asked otherwise, either way.
    assert frames.map_frame(0.0, 0.0, *DATUM, (5.0, 5.0, 1.0), frame='world')[1] == 'world'
    assert frames.map_frame(*DATUM, *DATUM, (5.0, 5.0, 1.0), frame='spawn')[1] == 'spawn'
    with pytest.raises(ValueError):
        frames.map_frame(0.0, 0.0, *DATUM, (0.0, 0.0, 0.0), frame='town')


def test_a_sensor_mount_moves_from_base_link_to_the_actor():
    # A camera 1.75 m ahead of the rear axle, 0.29 m LEFT, 1.55 m up, turned to look back.
    m = frames.mount([1.75, 0.29, 1.55], [0.0, 0.0, math.pi], rear_axle_x=-1.4, ground_z=-0.05)
    assert (m.x, m.y, m.z) == pytest.approx((0.35, -0.29, 1.50))
    assert abs(m.yaw) == pytest.approx(180.0)


def test_wheels_in_centimetres_in_the_world_end_up_in_metres_on_the_car():
    # A car at (100, 50) m turned 90 deg (facing CARLA's +y); wheels 1.4 m ahead and
    # behind, 0.8 m to each side, given in world centimetres as CARLA 0.9 does.
    ax, ay, yaw = 100.0, 50.0, 90.0
    body = [(1.4, -0.8), (1.4, 0.8), (-1.4, -0.8), (-1.4, 0.8)]   # FL, FR, RL, RR
    world_cm = [((ax - y) * 100, (ay + x) * 100) for x, y in body]
    got = frames.wheels_in_actor(world_cm, ax, ay, yaw)
    assert all(close(g, b, 1e-6) for g, b in zip(got, body))
    rear, wheelbase = frames.rear_axle(got)
    assert (rear, wheelbase) == pytest.approx((-1.4, 2.8))
    # In metres it's left alone.
    world_m = [(ax - y, ay + x) for x, y in body]
    got = frames.wheels_in_actor(world_m, ax, ay, yaw)
    assert all(close(g, b, 1e-6) for g, b in zip(got, body))


def test_rear_axle_refuses_nonsense():
    with pytest.raises(ValueError):
        frames.rear_axle([(1.0, 0.0)] * 3)
    with pytest.raises(ValueError):
        frames.rear_axle([(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)])


def test_offset_and_seconds():
    assert close(frames.offset(1.0, 2.0, math.pi / 2, 3.0, 0.0), (1.0, 5.0))
    assert frames.split_seconds(12.25) == (12, 250_000_000)
    assert frames.split_seconds(0.0) == (0, 0)
