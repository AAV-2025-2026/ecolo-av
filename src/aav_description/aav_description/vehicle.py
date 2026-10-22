"""
Read config/vehicle.yaml and derive what other nodes need from it.

The launch files use this so the car's measurements live in one file:

    from aav_description import vehicle
    v = vehicle.load()['vehicle']
    vehicle.min_turning_radius(v)    # Nav2 SmacPlannerHybrid, MPPI Ackermann
    vehicle.footprint(v)             # Nav2 costmaps
    vehicle.stop_zone_points(v)      # Nav2 collision_monitor
    vehicle.obstacle_heights(v)      # the lidar's band of obstacle heights (lidar_scan)
    vehicle.nav2_rewrites(v, reversing)         # Nav2's file: forward only, or reversing too
    vehicle.nav2_tuned(nav2, v, reversing, max_speed, radar, lidar, ghost,  # what
                       controller)                              # RewrittenYaml can't write
    vehicle.ego_params(vehicle.load())          # ego: the whole file (the actuators too)
    vehicle.centre_of_mass(v, front, rear, front_lifted, lift)   # from the scales (M7, M7b)
    vehicle.wheel_angles(v, centre)  # each front wheel's angle for a centre (bicycle) angle
    vehicle.centre_angle(v, inner, outer)       # the reverse: from M5's two measured angles
    vehicle.gazebo_steering_limit(v) # Gazebo's AckermannSteering steering_limit
"""

import copy
import math
import os

import yaml


def config_path():
    from ament_index_python.packages import get_package_share_directory
    return os.path.join(get_package_share_directory('aav_description'), 'config', 'vehicle.yaml')


def load(path=None):
    with open(path or config_path()) as f:
        return yaml.safe_load(f)


def min_turning_radius(v):
    """Radius of the path of base_link (the rear axle centre) at full lock, in metres."""
    return v['wheelbase'] / math.tan(v['max_steering_angle'])


# max_steering_angle is the virtual wheel in the middle of the front axle: the bicycle
# model's angle, which ego and Nav2 use. With Ackermann steering both front wheels point
# at one turning centre on the rear axle's line, so the inner wheel turns further and the
# outer less (READ-ME-MEASURE-THE-CAR.md M5 measures both):
#
#     cot(outer) - cot(inner) = track / wheelbase,   cot(centre) = (cot(inner) + cot(outer)) / 2


def wheel_angles(v, centre):
    """Return (inner, outer) front wheel angles (rad, >= 0) for a centre angle (rad)."""
    c = abs(centre)
    if c == 0.0:
        return 0.0, 0.0
    radius = v['wheelbase'] / math.tan(c)       # rear axle centre to the turning centre
    half = v['track'] / 2.0
    return (math.atan2(v['wheelbase'], radius - half),
            math.atan2(v['wheelbase'], radius + half))


def centre_angle(v, inner, outer):
    """Return the centre (bicycle) angle from both measured front wheel angles (rad)."""
    if inner <= 0.0 or outer <= 0.0:
        raise ValueError('measure both wheels turned the same way, each > 0')
    return math.atan(2.0 / (1.0 / math.tan(inner) + 1.0 / math.tan(outer)))


def gazebo_steering_limit(v):
    """
    Return the steering_limit for Gazebo's AckermannSteering system (rad).

    It is not the centre angle, nor the inner wheel's (gz-sim 8, AckermannSteering.cc,
    UpdateVelocity): Gazebo turns it into a smallest radius, wheelbase / sin(limit), then
    sets the centre angle to atan(wheelbase / radius). Given max_steering_angle itself,
    the car stops at atan(sin(0.5)) = 0.447 rad, not 0.5. So pass the limit whose sine
    is tan(max_steering_angle): the smallest radius is then wheelbase / tan(max), the
    bicycle model's, and the centre wheel reaches max_steering_angle.
    """
    t = math.tan(v['max_steering_angle'])
    if not 0.0 < t < 1.0:
        raise ValueError("Gazebo's AckermannSteering can't steer 45 degrees or more")
    return math.asin(t)


def footprint_points(v):
    """Return the body outline as [x, y] corners in base_link, front-left first."""
    body = v['body']
    rear = -body['rear_overhang']
    front = rear + body['length']
    half = body['width'] / 2.0
    return [[front, half], [front, -half], [rear, -half], [rear, half]]


def polygon(points):
    """Return [x, y] corners in the string form Nav2 takes for a polygon."""
    return '[' + ', '.join(f'[{x:.3f}, {y:.3f}]' for x, y in points) + ']'


def footprint(v):
    """Return the outline in the string form Nav2's costmaps take for `footprint`."""
    return polygon(footprint_points(v))


# collision_monitor's stop zone, ahead of the front bumper. At Nav2's 1 m/s, ego's 2 m/s^2
# stops the car in 0.25 m; add about 0.4 s for the radar's frame, the mux, ego and the
# brakes (0.4 m), and 0.35 m for the radar's range noise and the guessed measurements.
STOP_ZONE_AHEAD = 1.0   # m
STOP_ZONE_MARGIN = 0.2  # m each side of the body


def stop_zone_points(v, ahead=STOP_ZONE_AHEAD, margin=STOP_ZONE_MARGIN):
    """Return the stop zone's corners: from the front bumper to `ahead` past it, widened."""
    body = v['body']
    front = body['length'] - body['rear_overhang']
    half = body['width'] / 2.0 + margin
    return [[front + ahead, half], [front + ahead, -half], [front, -half], [front, half]]


# The lidar's obstacles: what lies between these heights above the road (base_link's z).
# Below: the road itself, kerbs, and the ground the lidar sees as its beams tilt with the
# car (0.3 m is the ground 10 m away, with the car pitched 1.7 degrees). Above the car's
# roof by more than OVERHEAD_MARGIN: branches, signs, a garage door the car passes under.
GROUND_CLEARANCE = 0.3  # m
OVERHEAD_MARGIN = 0.5   # m above the body's height


def obstacle_heights(v):
    """Return (lowest, highest) m above the road that counts as an obstacle for the lidar."""
    return GROUND_CLEARANCE, float(v['body']['height']) + OVERHEAD_MARGIN


def ego_params(cfg):
    """Return what ego takes from vehicle.yaml (the whole file): its geometry and its body."""
    v, act = cfg['vehicle'], cfg['actuators']
    return {
        'wheelbase': float(v['wheelbase']),
        'max_steering_angle': float(v['max_steering_angle']),
        'max_reverse_speed': float(v['max_reverse_speed']),
        'mass': float(v['mass']),
        'track': float(v['track']),
        'cg_height': float(v['centre_of_mass']['height']),
        'tyre_grip': float(v['tyre_grip']),
        'full_throttle_accel': float(act['max_accel']),
        'full_brake_decel': float(act['max_brake']),
    }


def centre_of_mass(v, front, rear, front_lifted=None, lift=None):
    """
    Return the centre of mass from the scales: (x ahead of the rear axle, height), m.

    front, rear: the weight on each axle, level (READ-ME-MEASURE-THE-CAR.md, M7; any unit).
    front_lifted, lift: the front axle again with both rear wheels on blocks `lift` m high
    (M7b). Without them the height is None.

    Level, the front axle carries the share of the weight that x is of the wheelbase.
    Lifted, the car tips forward by asin(lift / L), and a centre of mass h - r above the
    axles moves (h - r) tan(tilt) forward, so the front gains W (h - r) tan(tilt) / L.
    """
    L, total = float(v['wheelbase']), float(front + rear)
    x = L * front / total
    if front_lifted is None or not lift:
        return x, None
    tilt = math.asin(lift / L)
    r = float(v['wheel_diameter']) / 2.0
    return x, r + L * (front_lifted - front) / (total * math.tan(tilt))


def spine_params(v):
    return {
        'wheelbase': float(v['wheelbase']),
        'track': float(v['track']),
    }


def reverse_limit(v, reversing):
    """Return the lowest speed Nav2 may command (m/s): -max_reverse_speed, or 0 forward only."""
    return -float(v['max_reverse_speed']) if reversing else 0.0


# The planner plans turns this much wider than the car's tightest, so the controller has
# steering left to stay on the path. At full lock in the plan, both controllers cut the last
# turn before a goal, arrived 0.5 m off and facing wrong, and drove round again (22 Oct).
PLAN_TURN_MARGIN = 1.25

# Nav2's path followers (docs/controllers.md): rpp, Regulated Pure Pursuit, chases a point
# ahead on the path; mppi samples thousands of futures through its Ackermann model.
CONTROLLERS = ('rpp', 'mppi')


def nav2_rewrites(v, reversing=False):
    """
    Values to substitute into aav_navigation/config/nav2.yaml.

    RewrittenYaml takes a leaf key (every key of that name) or a whole dotted path. With
    `reversing`, Nav2 may drive backwards, at up to max_reverse_speed: the planner plans
    Reeds-Shepp paths (forward and back), the controller follows them backwards, and MPPI
    may go negative. Without it, the planner plans forward only (Dubins paths). The velocity
    smoother's limit is a list, which RewrittenYaml can't write: see nav2_tuned.
    """
    r = min_turning_radius(v)
    low, high = obstacle_heights(v)
    return {
        'footprint': footprint(v),
        'lidar_scan.ros__parameters.min_height': f'{low:.3f}',
        'lidar_scan.ros__parameters.max_height': f'{high:.3f}',
        'minimum_turning_radius': f'{r * PLAN_TURN_MARGIN:.3f}',  # SmacPlannerHybrid
        'min_turning_r': f'{r:.3f}',            # MPPI AckermannConstraints: the car's own
        'collision_monitor.ros__parameters.StopZone.points': polygon(stop_zone_points(v)),
        'planner_server.ros__parameters.GridBased.motion_model_for_search':
            'REEDS_SHEPP' if reversing else 'DUBIN',
        'controller_server.ros__parameters.FollowPath.allow_reversing': str(reversing).lower(),
        'controller_server.ros__parameters.MPPI.vx_min': f'{reverse_limit(v, reversing):.3f}',
    }


def nav2_tuned(nav2, v, reversing=False, max_speed=None, radar=True, lidar=False,
               ghost=False, controller='rpp'):
    """
    Return a copy of nav2.yaml's settings (`nav2`, loaded) with what RewrittenYaml can't write.

    RewrittenYaml writes only strings and numbers: a list comes out as a string, and an
    index into a list (`min_velocity.0`) raises a TypeError. So the launch file writes
    these into a copy of the file instead:
    - the controller (CONTROLLERS): rpp keeps FollowPath, Regulated Pure Pursuit; mppi
      puts a copy of the MPPI block under FollowPath, the name the behaviour trees ask
      for, with the reverse speed (vx_min) and, with `reversing`, enforce_path_inversion
      (it changes direction where the planner's path does);
    - the velocity smoother's lowest speed, the last stop for a negative speed inside Nav2:
      0, or -max_reverse_speed with `reversing`;
    - with `max_speed` (m/s, sim.launch.py sim_speed:=), the controller's speed and the
      smoother's top speed;
    - the sensors collision_monitor reads: the radar, the lidar or both;
    - the local costmap's lidar_layer, only with the lidar: a layer that is there but
      disabled still subscribes to its topic;
    - with `ghost` (aav_ghost), the ghost as one more source, and its own layer,
      ghost_layer: it only adds a pretend obstacle, never clears the real sensors' marks.
    """
    if controller not in CONTROLLERS:
        raise ValueError(f'controller:={controller}: pick one of {", ".join(CONTROLLERS)}')
    out = copy.deepcopy(nav2)
    servers = out['controller_server']['ros__parameters']
    if controller == 'mppi':
        # A copy, so the MPPI block stays where nav2_rewrites' MPPI.vx_min expects it.
        mppi = copy.deepcopy(servers['MPPI'])
        mppi['vx_min'] = reverse_limit(v, reversing)
        mppi['enforce_path_inversion'] = bool(reversing)
        servers['FollowPath'] = mppi
    monitor = out['collision_monitor']['ros__parameters']
    monitor['observation_sources'] = [name for name, on in (('radar', radar), ('lidar', lidar),
                                                            ('ghost', ghost)) if on]
    local = out['local_costmap']['local_costmap']['ros__parameters']
    gone = {layer for layer, on in (('lidar_layer', lidar), ('ghost_layer', ghost)) if not on}
    local['plugins'] = [p for p in local['plugins'] if p not in gone]
    smoother = out['velocity_smoother']['ros__parameters']
    smoother['min_velocity'] = ([reverse_limit(v, reversing)] +
                                [float(x) for x in smoother['min_velocity'][1:]])
    if max_speed is not None:
        follow = servers['FollowPath']
        follow['vx_max' if controller == 'mppi' else 'desired_linear_vel'] = float(max_speed)
        smoother['max_velocity'][0] = float(max_speed)
    return out
