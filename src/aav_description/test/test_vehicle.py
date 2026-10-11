import math
from pathlib import Path
import re

from aav_description import vehicle

CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'vehicle.yaml'
ROOT = Path(__file__).resolve().parents[3]
SPINE_RS = ROOT / 'firmware/spine/crates/spine-core/src/spine.rs'


def rust_const(path, name):
    """Return the number in `pub const NAME: f32 = <number>;` from a Rust file."""
    found = re.search(rf'pub const {name}: f32 = ([-0-9.e]+);', path.read_text())
    assert found, f'no `pub const {name}: f32 = ...;` in {path}'
    return float(found.group(1))


def test_config_loads_and_has_what_the_launch_files_read():
    cfg = vehicle.load(CONFIG)
    v = cfg['vehicle']
    for key in ('wheelbase', 'track', 'wheel_diameter', 'max_steering_angle', 'body'):
        assert key in v
    for name in ('imu_link', 'gps_link', 'radar_link'):
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
                      'collision_monitor.ros__parameters.StopZone.points',
                      'planner_server.ros__parameters.GridBased.motion_model_for_search',
                      'controller_server.ros__parameters.FollowPath.allow_reversing',
                      'controller_server.ros__parameters.MPPI.vx_min'}
    assert r['minimum_turning_radius'] == r['min_turning_r']
    # RewrittenYaml can't index into a list: none of these may try.
    assert not any(key.split('.')[-1].isdigit() for key in r)


def test_nav2_forward_only_or_reversing():
    v = {'wheelbase': 1.57, 'max_steering_angle': 0.5, 'max_reverse_speed': 0.4,
         'body': {'length': 2.0, 'width': 1.0, 'rear_overhang': 0.2}}
    forward = vehicle.nav2_rewrites(v)
    back = vehicle.nav2_rewrites(v, reversing=True)
    model = 'planner_server.ros__parameters.GridBased.motion_model_for_search'
    allow = 'controller_server.ros__parameters.FollowPath.allow_reversing'
    vx_min = 'controller_server.ros__parameters.MPPI.vx_min'
    assert (forward[model], forward[allow], forward[vx_min]) == ('DUBIN', 'false', '0.000')
    assert (back[model], back[allow], back[vx_min]) == ('REEDS_SHEPP', 'true', '-0.400')


def test_the_smoother_gets_the_reverse_speed_as_a_list():
    v = {'max_reverse_speed': 0.4}
    nav2 = {'velocity_smoother': {'ros__parameters': {'min_velocity': [-0.5, 0.0, -1.0]}}}
    assert vehicle.nav2_node_params(v, nav2) == {
        'velocity_smoother': {'min_velocity': [0.0, 0.0, -1.0]}}
    assert vehicle.nav2_node_params(v, nav2, reversing=True) == {
        'velocity_smoother': {'min_velocity': [-0.4, 0.0, -1.0]}}


def test_ego_gets_the_reverse_speed():
    v = vehicle.load(CONFIG)['vehicle']
    assert vehicle.ego_params(v)['max_reverse_speed'] == v['max_reverse_speed']


def test_the_firmware_copies_match_vehicle_yaml():
    # spine-core can't read vehicle.yaml, so it keeps copies. Change both together.
    v = vehicle.load(CONFIG)['vehicle']
    assert rust_const(SPINE_RS, 'MAX_STEERING_ANGLE') == v['max_steering_angle']
    assert rust_const(SPINE_RS, 'MAX_REVERSE_SPEED') == v['max_reverse_speed']
