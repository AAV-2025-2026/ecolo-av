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
    vehicle.nav2_tuned(nav2, v, reversing, max_speed, radar, lidar, ghost)  # what
                                                                # RewrittenYaml can't write
    vehicle.ego_params(v)            # ego
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


def ego_params(v):
    return {
        'wheelbase': float(v['wheelbase']),
        'max_steering_angle': float(v['max_steering_angle']),
        'max_reverse_speed': float(v['max_reverse_speed']),
    }


def spine_params(v):
    return {
        'wheelbase': float(v['wheelbase']),
        'track': float(v['track']),
    }


def reverse_limit(v, reversing):
    """Return the lowest speed Nav2 may command (m/s): -max_reverse_speed, or 0 forward only."""
    return -float(v['max_reverse_speed']) if reversing else 0.0


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
        'minimum_turning_radius': f'{r:.3f}',   # SmacPlannerHybrid
        'min_turning_r': f'{r:.3f}',            # MPPI AckermannConstraints
        'collision_monitor.ros__parameters.StopZone.points': polygon(stop_zone_points(v)),
        'planner_server.ros__parameters.GridBased.motion_model_for_search':
            'REEDS_SHEPP' if reversing else 'DUBIN',
        'controller_server.ros__parameters.FollowPath.allow_reversing': str(reversing).lower(),
        'controller_server.ros__parameters.MPPI.vx_min': f'{reverse_limit(v, reversing):.3f}',
    }


def nav2_tuned(nav2, v, reversing=False, max_speed=None, radar=True, lidar=False,
               ghost=False):
    """
    Return a copy of nav2.yaml's settings (`nav2`, loaded) with what RewrittenYaml can't write.

    RewrittenYaml writes only strings and numbers: a list comes out as a string, and an
    index into a list (`min_velocity.0`) raises a TypeError. So the launch file writes
    these into a copy of the file instead:
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
    out = copy.deepcopy(nav2)
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
        follow = out['controller_server']['ros__parameters']['FollowPath']
        follow['desired_linear_vel'] = float(max_speed)
        smoother['max_velocity'][0] = float(max_speed)
    return out
