"""sensors.py: the CARLA car's sensors, their settings and their raw data."""

import math
import os

from aav_carla import sensors
import numpy as np
import pytest
import yaml


def test_the_camera_matches_gazebos_lens():
    # Gazebo's cameras: 640 x 360, focal length 343 px. The field of view must give it back.
    fov = float(sensors.CAMERA['fov'])
    info = sensors.camera_matrix(640, 360, fov)
    assert info['k'][0] == pytest.approx(343.0, rel=1e-4)
    assert info['k'][2] == 320.0 and info['k'][5] == 180.0
    assert info['p'][0] == info['k'][0]


def test_every_attribute_is_a_string():
    for s in sensors.chosen():
        assert all(isinstance(v, str) for v in s.attributes.values()), s.name


def test_chosen_and_sources():
    names = [s.name for s in sensors.chosen(cameras=False, radar=False, lidar=False)]
    assert names == ['imu']
    every = sensors.chosen()
    assert {s.name for s in every} == {'imu', 'camera_front_left', 'camera_front_right',
                                       'camera_rear', 'radar', 'lidar'}
    src = dict(sensors.sources(every))
    assert src['gps'] == '/sensors/gps/fix'
    assert src['odometry'] == '/vehicle/odom'
    assert src['imu'] == '/sensors/imu/data_raw'
    assert src['lidar'] == '/sensors/lidar/points'


def test_every_sensor_sits_on_a_vehicle_yaml_link():
    path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'bringup', 'aav_description',
                        'config', 'vehicle.yaml')
    with open(path) as f:
        links = yaml.safe_load(f)['sensors']
    for s in sensors.chosen():
        assert s.link in links, s.link


def test_topics_start_with_their_area():
    for s in sensors.chosen():
        assert s.topic.startswith('/sensors/'), s.topic
    rear = '/sensors/camera/rear/'
    assert sensors.info_topic(rear + 'image_raw') == rear + 'camera_info'


def test_bgra_to_bgr():
    raw = bytes([1, 2, 3, 255, 4, 5, 6, 255])          # two pixels
    assert sensors.bgra_to_bgr(raw, 2, 1) == bytes([1, 2, 3, 4, 5, 6])
    with pytest.raises(ValueError):
        sensors.bgra_to_bgr(raw, 3, 1)


def test_lidar_points_flip_y():
    raw = np.array([[1.0, 2.0, 3.0, 0.5]], dtype=np.float32).tobytes()
    assert sensors.lidar_points(raw).tolist() == [[1.0, -2.0, 3.0, 0.5]]


def test_a_radar_detection_to_the_right_lands_on_negative_y():
    # velocity, azimuth (+ right), altitude, depth
    raw = np.array([[-1.5, math.radians(30), 0.0, 4.0],
                    [0.0, 0.0, math.radians(5), 2.0]], dtype=np.float32).tobytes()
    p = sensors.radar_points(raw)
    assert p.shape == (2, 5)
    assert p[0, 0] == pytest.approx(4 * math.cos(math.radians(30)), rel=1e-6)
    assert p[0, 1] == pytest.approx(-2.0, rel=1e-6)
    assert p[0, 4] == pytest.approx(-1.5)
    assert p[1, 2] == pytest.approx(2 * math.sin(math.radians(5)), rel=1e-6)
    assert sensors.radar_points(b'').shape == (0, 5)


def test_wheel_speeds_straight_and_turning():
    w = sensors.wheel_speeds(2.0, 0.0, 1.57, 0.77)
    assert set(w.values()) == {2.0}
    w = sensors.wheel_speeds(2.0, 0.5, 1.57, 0.77)             # turning left
    assert w['rear_right'] > w['rear_left']
    assert w['front_left'] > w['rear_left']                  # the front wheels go further
    assert sensors.wheel_speeds(-1.0, 0.0, 1.57, 0.77)['front_left'] == -1.0
