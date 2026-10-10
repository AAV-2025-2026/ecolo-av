"""
Read config/vehicle.yaml and derive what other nodes need from it.

The launch files use this so the car's measurements live in one file:

    from aav_description import vehicle
    v = vehicle.load()['vehicle']
    vehicle.min_turning_radius(v)    # Nav2 SmacPlannerHybrid, MPPI Ackermann
    vehicle.footprint(v)             # Nav2 costmaps
    vehicle.ego_params(v)            # ego
"""

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


def footprint(v):
    """Return the outline in the string form Nav2's costmaps take for `footprint`."""
    return '[' + ', '.join(f'[{x:.3f}, {y:.3f}]' for x, y in footprint_points(v)) + ']'


def ego_params(v):
    return {
        'wheelbase': float(v['wheelbase']),
        'max_steering_angle': float(v['max_steering_angle']),
    }


def spine_params(v):
    return {
        'wheelbase': float(v['wheelbase']),
        'track': float(v['track']),
    }


def nav2_rewrites(v):
    """Values to substitute into aav_navigation/config/nav2.yaml (RewrittenYaml leaf keys)."""
    r = min_turning_radius(v)
    return {
        'footprint': footprint(v),
        'minimum_turning_radius': f'{r:.3f}',   # SmacPlannerHybrid
        'min_turning_r': f'{r:.3f}',            # MPPI AckermannConstraints
    }
