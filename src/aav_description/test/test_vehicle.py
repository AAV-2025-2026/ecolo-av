import math
from pathlib import Path

from aav_description import vehicle

CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'vehicle.yaml'


def test_config_loads_and_has_what_the_launch_files_read():
    cfg = vehicle.load(CONFIG)
    v = cfg['vehicle']
    for key in ('wheelbase', 'track', 'wheel_diameter', 'max_steering_angle', 'body'):
        assert key in v
    for name in ('imu_link', 'gps_link', 'radar_link', 'camera_left_link',
                 'camera_right_link', 'camera_rear_link', 'lidar_link'):
        assert len(cfg['sensors'][name]['xyz']) == 3


def test_turning_radius_is_bicycle_model():
    v = {'wheelbase': 1.57, 'max_steering_angle': 0.5}
    assert math.isclose(vehicle.min_turning_radius(v), 1.57 / math.tan(0.5))
    assert 2.8 < vehicle.min_turning_radius(v) < 2.9


def test_footprint_encloses_base_link_and_is_nav2_string():
    v = {'body': {'length': 2.0, 'width': 1.0, 'rear_overhang': 0.2}}
    pts = vehicle.footprint_points(v)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert min(xs) == -0.2 and math.isclose(max(xs), 1.8)
    assert min(ys) == -0.5 and max(ys) == 0.5
    assert vehicle.footprint(v) == \
        '[[1.800, 0.500], [1.800, -0.500], [-0.200, -0.500], [-0.200, 0.500]]'


def test_stop_zone_is_ahead_of_the_bumper_and_wider_than_the_body():
    v = {'body': {'length': 2.0, 'width': 1.0, 'rear_overhang': 0.2}}
    pts = vehicle.stop_zone_points(v, ahead=1.0, margin=0.2)
    xs = sorted({round(p[0], 6) for p in pts})
    ys = sorted({round(p[1], 6) for p in pts})
    assert xs == [1.8, 2.8] and ys == [-0.7, 0.7]
    assert vehicle.polygon(pts) == \
        '[[2.800, 0.700], [2.800, -0.700], [1.800, -0.700], [1.800, 0.700]]'


def test_nav2_rewrites_keys():
    v = vehicle.load(CONFIG)['vehicle']
    r = vehicle.nav2_rewrites(v)
    assert set(r) == {'footprint', 'minimum_turning_radius', 'min_turning_r',
                      'collision_monitor.ros__parameters.StopZone.points'}
    assert r['minimum_turning_radius'] == r['min_turning_r']
