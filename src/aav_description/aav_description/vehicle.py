"""
Read config/vehicle.yaml and derive what other nodes need from it.

The launch files use this so the car's measurements live in one file:

    from aav_description import vehicle
    v = vehicle.load()['vehicle']
    vehicle.min_turning_radius(v)    # Nav2 SmacPlannerHybrid, MPPI Ackermann
    vehicle.footprint(v)             # Nav2 costmaps
    vehicle.stop_zone_points(v)      # Nav2 collision_monitor
    vehicle.nav2_rewrites(v, reversing)         # Nav2's file: forward only, or reversing too
    vehicle.nav2_tuned(nav2, v, reversing, max_speed)  # what RewrittenYaml can't write
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
    return {
        'footprint': footprint(v),
        'minimum_turning_radius': f'{r:.3f}',   # SmacPlannerHybrid
        'min_turning_r': f'{r:.3f}',            # MPPI AckermannConstraints
        'collision_monitor.ros__parameters.StopZone.points': polygon(stop_zone_points(v)),
        'planner_server.ros__parameters.GridBased.motion_model_for_search':
            'REEDS_SHEPP' if reversing else 'DUBIN',
        'controller_server.ros__parameters.FollowPath.allow_reversing': str(reversing).lower(),
        'controller_server.ros__parameters.MPPI.vx_min': f'{reverse_limit(v, reversing):.3f}',
    }


def nav2_tuned(nav2, v, reversing=False, max_speed=None):
    """
    Return a copy of nav2.yaml's settings (`nav2`, loaded) with what RewrittenYaml can't write.

    RewrittenYaml writes only strings and numbers: a list comes out as a string, and an
    index into a list (`min_velocity.0`) raises a TypeError. So the launch file writes
    these into a copy of the file instead:
    - the velocity smoother's lowest speed, the last stop for a negative speed inside Nav2:
      0, or -max_reverse_speed with `reversing`;
    - with `max_speed` (m/s, sim.launch.py sim_speed:=), the controller's speed and the
      smoother's top speed.
    """
    out = copy.deepcopy(nav2)
    smoother = out['velocity_smoother']['ros__parameters']
    smoother['min_velocity'] = ([reverse_limit(v, reversing)] +
                                [float(x) for x in smoother['min_velocity'][1:]])
    if max_speed is not None:
        follow = out['controller_server']['ros__parameters']['FollowPath']
        follow['desired_linear_vel'] = float(max_speed)
        smoother['max_velocity'][0] = float(max_speed)
    return out
