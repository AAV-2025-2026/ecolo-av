import math
from pathlib import Path
import re
import shutil
import subprocess

from aav_description import vehicle
import pytest
import yaml

CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'vehicle.yaml'
ROOT = Path(__file__).resolve().parents[3]
SPINE_RS = ROOT / 'firmware/spine/crates/spine-core/src/spine.rs'
NAV2_YAML = ROOT / 'src/drivers/aav_navigation/config/nav2.yaml'


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
                      'collision_monitor.ros__parameters.StopZone.points',
                      'planner_server.ros__parameters.GridBased.motion_model_for_search',
                      'controller_server.ros__parameters.FollowPath.allow_reversing',
                      'controller_server.ros__parameters.MPPI.vx_min',
                      'lidar_scan.ros__parameters.min_height',
                      'lidar_scan.ros__parameters.max_height'}
    assert r['minimum_turning_radius'] == r['min_turning_r']
    # RewrittenYaml can't index into a list: none of these may try.
    assert not any(key.split('.')[-1].isdigit() for key in r)


def test_nav2_forward_only_or_reversing():
    v = {'wheelbase': 1.57, 'max_steering_angle': 0.5, 'max_reverse_speed': 0.4,
         'body': {'length': 2.0, 'width': 1.0, 'height': 1.5, 'rear_overhang': 0.2}}
    forward = vehicle.nav2_rewrites(v)
    back = vehicle.nav2_rewrites(v, reversing=True)
    model = 'planner_server.ros__parameters.GridBased.motion_model_for_search'
    allow = 'controller_server.ros__parameters.FollowPath.allow_reversing'
    vx_min = 'controller_server.ros__parameters.MPPI.vx_min'
    assert (forward[model], forward[allow], forward[vx_min]) == ('DUBIN', 'false', '0.000')
    assert (back[model], back[allow], back[vx_min]) == ('REEDS_SHEPP', 'true', '-0.400')


NAV2_SMALL = {
    'velocity_smoother': {'ros__parameters': {'min_velocity': [-0.5, 0.0, -1.0],
                                              'max_velocity': [1.0, 0.0, 1.0]}},
    'controller_server': {'ros__parameters': {'FollowPath': {'desired_linear_vel': 1.0}}},
    'collision_monitor': {'ros__parameters': {'observation_sources': ['radar']}},
    'local_costmap': {'local_costmap': {'ros__parameters': {
        'plugins': ['static_layer', 'obstacle_layer', 'lidar_layer', 'ghost_layer',
                    'inflation_layer']}}},
}


def test_the_lidar_feeds_the_costmap_and_the_stop_zone_only_when_it_runs():
    v = {'max_reverse_speed': 0.4}

    def picked(**sensors):
        cfg = vehicle.nav2_tuned(NAV2_SMALL, v, **sensors)
        return (cfg['collision_monitor']['ros__parameters']['observation_sources'],
                cfg['local_costmap']['local_costmap']['ros__parameters']['plugins'])

    sources, layers = picked()                       # the default: the radar alone
    assert sources == ['radar'] and 'lidar_layer' not in layers
    sources, layers = picked(radar=True, lidar=True)
    assert sources == ['radar', 'lidar'] and 'lidar_layer' in layers
    sources, layers = picked(radar=False, lidar=True)
    assert sources == ['lidar'] and layers[-1] == 'inflation_layer'


def test_the_ghost_is_its_own_source_and_layer_only_when_asked_for():
    v = {'max_reverse_speed': 0.4}

    def picked(**sensors):
        cfg = vehicle.nav2_tuned(NAV2_SMALL, v, **sensors)
        return (cfg['collision_monitor']['ros__parameters']['observation_sources'],
                cfg['local_costmap']['local_costmap']['ros__parameters']['plugins'])

    sources, layers = picked()
    assert 'ghost' not in sources and 'ghost_layer' not in layers
    # On top of the real sensors: they keep their own layers and sources.
    sources, layers = picked(radar=True, lidar=True, ghost=True)
    assert sources == ['radar', 'lidar', 'ghost']
    assert layers == ['static_layer', 'obstacle_layer', 'lidar_layer', 'ghost_layer',
                      'inflation_layer']
    sources, layers = picked(radar=False, ghost=True)
    assert sources == ['ghost'] and 'lidar_layer' not in layers and 'ghost_layer' in layers


def test_the_lidar_ignores_the_road_and_what_the_car_passes_under():
    low, high = vehicle.obstacle_heights({'body': {'height': 1.5}})
    assert 0.0 < low < 0.5          # over the road and its kerbs
    assert high > 1.5               # over the roof, so nothing the car hits is dropped
    rewrites = vehicle.nav2_rewrites(vehicle.load(CONFIG)['vehicle'])
    assert float(rewrites['lidar_scan.ros__parameters.max_height']) > 1.5


def test_the_smoother_gets_the_reverse_speed_as_a_list():
    v = {'max_reverse_speed': 0.4}
    smoother = 'velocity_smoother'
    forward = vehicle.nav2_tuned(NAV2_SMALL, v)[smoother]['ros__parameters']
    back = vehicle.nav2_tuned(NAV2_SMALL, v, reversing=True)[smoother]['ros__parameters']
    assert forward['min_velocity'] == [0.0, 0.0, -1.0]
    assert back['min_velocity'] == [-0.4, 0.0, -1.0]
    # A copy: the loaded file stays as it was.
    assert NAV2_SMALL[smoother]['ros__parameters']['min_velocity'] == [-0.5, 0.0, -1.0]


def test_max_speed_raises_the_controller_and_the_smoother_together():
    v = {'max_reverse_speed': 0.4}
    same = vehicle.nav2_tuned(NAV2_SMALL, v)
    assert same['controller_server'] == NAV2_SMALL['controller_server']
    fast = vehicle.nav2_tuned(NAV2_SMALL, v, reversing=True, max_speed=3)
    assert fast['controller_server']['ros__parameters']['FollowPath']['desired_linear_vel'] == 3.0
    smoother = fast['velocity_smoother']['ros__parameters']
    assert smoother['max_velocity'] == [3.0, 0.0, 1.0]
    assert smoother['min_velocity'] == [-0.4, 0.0, -1.0]   # reversing stays as slow


def test_mppi_follows_the_path_under_the_name_the_trees_ask_for():
    # The behaviour trees ask for FollowPath: mppi puts a copy of the MPPI block there.
    v = {'max_reverse_speed': 0.4}
    nav2 = yaml.safe_load(NAV2_YAML.read_text())
    servers = 'controller_server'
    rpp = vehicle.nav2_tuned(nav2, v)[servers]['ros__parameters']
    assert rpp['FollowPath'] == nav2[servers]['ros__parameters']['FollowPath']
    assert 'RegulatedPurePursuit' in rpp['FollowPath']['plugin']
    mppi = vehicle.nav2_tuned(nav2, v, reversing=True, max_speed=3, controller='mppi')
    follow = mppi[servers]['ros__parameters']['FollowPath']
    assert follow['plugin'] == 'nav2_mppi_controller::MPPIController'
    assert follow['motion_model'] == 'Ackermann'
    assert (follow['vx_min'], follow['vx_max']) == (-0.4, 3.0)
    assert follow['enforce_path_inversion'] is True     # it reverses where the path does
    assert 'desired_linear_vel' not in follow
    forward = vehicle.nav2_tuned(nav2, v, controller='mppi')[servers]['ros__parameters']
    assert (forward['FollowPath']['vx_min'], forward['FollowPath']['vx_max']) == (0.0, 1.0)
    assert forward['FollowPath']['enforce_path_inversion'] is False
    # The MPPI block itself stays as the file has it, where nav2_rewrites expects it.
    assert mppi[servers]['ros__parameters']['MPPI'] == nav2[servers]['ros__parameters']['MPPI']
    with pytest.raises(ValueError, match='pick one of rpp, mppi'):
        vehicle.nav2_tuned(nav2, v, controller='dwb')


def test_every_rewrite_lands_on_a_key_nav2_yaml_has():
    # RewrittenYaml drops a whole dotted path that isn't in the file, silently.
    nav2 = yaml.safe_load(NAV2_YAML.read_text())
    v = vehicle.load(CONFIG)['vehicle']
    for key in vehicle.nav2_rewrites(v, reversing=True):
        if '.' not in key:
            continue
        node = nav2
        for part in key.split('.'):
            assert part in node, f'{key}: no {part!r} in nav2.yaml'
            node = node[part]
    tuned = vehicle.nav2_tuned(nav2, v, reversing=True, max_speed=2.0)
    smoother = tuned['velocity_smoother']['ros__parameters']
    assert smoother['min_velocity'][0] == -v['max_reverse_speed']
    assert smoother['max_velocity'][0] == 2.0


def test_nav2_yaml_is_forward_only_until_the_launch_file_says():
    # The file's own values are the safe ones: no launch file, no reversing.
    nav2 = yaml.safe_load(NAV2_YAML.read_text())
    follow = nav2['controller_server']['ros__parameters']['FollowPath']
    assert follow['allow_reversing'] is False
    assert nav2['controller_server']['ros__parameters']['MPPI']['vx_min'] == 0.0
    assert nav2['velocity_smoother']['ros__parameters']['min_velocity'][0] == 0.0
    grid = nav2['planner_server']['ros__parameters']['GridBased']
    assert grid['motion_model_for_search'] == 'DUBIN'


def test_ego_gets_the_reverse_speed():
    v = vehicle.load(CONFIG)['vehicle']
    assert vehicle.ego_params(v)['max_reverse_speed'] == v['max_reverse_speed']


def test_the_firmware_copies_match_vehicle_yaml():
    # spine-core can't read vehicle.yaml, so it keeps copies. Change both together.
    v = vehicle.load(CONFIG)['vehicle']
    assert rust_const(SPINE_RS, 'MAX_STEERING_ANGLE') == v['max_steering_angle']
    assert rust_const(SPINE_RS, 'MAX_REVERSE_SPEED') == v['max_reverse_speed']


CAR = {'wheelbase': 1.57, 'track': 0.77, 'max_steering_angle': 0.5}


def test_the_inner_wheel_turns_further_than_the_centre_and_the_outer_less():
    inner, outer = vehicle.wheel_angles(CAR, 0.5)
    assert outer < 0.5 < inner
    assert math.isclose(inner, math.atan(1.57 / (1.57 / math.tan(0.5) - 0.385)))
    # Ackermann: both wheels point at the same turning centre.
    assert math.isclose(1 / math.tan(outer) - 1 / math.tan(inner), 0.77 / 1.57)
    assert vehicle.wheel_angles(CAR, 0.0) == (0.0, 0.0)
    assert vehicle.wheel_angles(CAR, -0.3) == vehicle.wheel_angles(CAR, 0.3)


def test_m5s_two_angles_give_the_centre_angle_back():
    for centre in (0.1, 0.3, 0.5, 0.6):
        inner, outer = vehicle.wheel_angles(CAR, centre)
        assert math.isclose(vehicle.centre_angle(CAR, inner, outer), centre)
    # 29 degrees each way: the centre is 29 degrees too.
    same = math.radians(29)
    assert math.isclose(vehicle.centre_angle(CAR, same, same), same)
    with pytest.raises(ValueError):
        vehicle.centre_angle(CAR, 0.5, 0.0)


def gazebo_centre_angle(v, steering_limit):
    """Gazebo's AckermannSteering at full lock (gz-sim 8, UpdateVelocity): the centre angle."""
    smallest_radius = v['wheelbase'] / math.sin(steering_limit)
    return math.atan(v['wheelbase'] / smallest_radius)


def test_gazebos_steering_limit_gives_the_centre_angle_at_full_lock():
    # Given max_steering_angle as it is, Gazebo stops 10% short: the 0.433 found by circles.
    assert gazebo_centre_angle(CAR, 0.5) < 0.45
    limit = vehicle.gazebo_steering_limit(CAR)
    assert limit > 0.5
    assert math.isclose(gazebo_centre_angle(CAR, limit), 0.5)
    # Its smallest radius is the bicycle model's: Nav2's minimum turning radius.
    assert math.isclose(CAR['wheelbase'] / math.sin(limit), vehicle.min_turning_radius(CAR))
    # The inner wheel's joint limit in aav.urdf.xacro (1.3 x max) leaves it room.
    v = vehicle.load(CONFIG)['vehicle']
    assert vehicle.wheel_angles(v, v['max_steering_angle'])[0] < 1.3 * v['max_steering_angle']
    with pytest.raises(ValueError):
        vehicle.gazebo_steering_limit({'max_steering_angle': math.radians(50)})


def find_share():
    try:
        from ament_index_python.packages import get_package_share_directory
        return get_package_share_directory('aav_description')
    except Exception:       # tools/test.sh: no ROS, or not built
        return None


@pytest.mark.skipif(shutil.which('xacro') is None or find_share() is None,
                    reason='needs xacro and the built package')
def test_gazebos_urdf_gets_the_derived_limit_and_refuses_none():
    urdf = Path(find_share()) / 'urdf' / 'aav.urdf.xacro'
    v = vehicle.load(CONFIG)['vehicle']
    limit = f'{vehicle.gazebo_steering_limit(v):.6f}'
    out = subprocess.run(['xacro', str(urdf), 'sim:=true', f'gz_steering_limit:={limit}'],
                         capture_output=True, text=True, check=True).stdout
    assert f'<steering_limit>{limit}</steering_limit>' in out
    missing = subprocess.run(['xacro', str(urdf), 'sim:=true'], capture_output=True)
    assert missing.returncode != 0
    car = subprocess.run(['xacro', str(urdf)], capture_output=True, text=True, check=True)
    assert 'steering_limit' not in car.stdout
