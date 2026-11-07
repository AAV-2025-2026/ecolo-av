"""
What each Gazebo world gives the car. No ROS imports: the launch files and tests read it.

A world renders the car's camera and radar stand-in (aav_description's
aav.sensors.gazebo.xacro) only if it loads Gazebo's Sensors system, which needs a GPU,
or ogre2 on a Mac. So the world file itself says whether the car has them: today
worlds/road.sdf, worlds/test_lot.sdf and the campus do. The empty world renders nothing, and
runs headless anywhere.
"""

from __future__ import annotations

import os
from typing import Tuple
from xml.etree import ElementTree

import yaml

SENSORS = 'gz::sim::systems::Sensors'

# The bench's obstacle (aav_bench/config/bench.yaml mock_radar: boxes 15-16 m east, -0.5 to
# 0.5 m north): where obstacle:=true puts models/obstacle, the centre of its base (m).
OBSTACLE: Tuple[float, float] = (15.5, 0.0)

# Carleton: too big for git, so tools/campus_world.py makes it (pixi run campus). These paths
# are from the repo's root, where pixi runs everything, like maps/ndt/test_lot.pcd.
CAMPUS = 'campus'
CAMPUS_SDF = os.path.join('maps', 'campus', 'campus.sdf')
CAMPUS_MAP = os.path.join('maps', 'campus', 'campus.yaml')
CAMPUS_PLACE = os.path.join('maps', 'campus', 'place.yaml')
CAMPUS_NDT = os.path.join('maps', 'ndt', 'campus.pcd')
# NDT's poor-fit floor on the campus. ndt.yaml's 2.3 is the test lot's: walls close by. Here
# (5 Nov, 60 s drive at P11's road) fits scored 1.73-1.94 on the guess and 2.00-2.31 on a
# recorded map, and stayed within 0.12 m of the truth. Whether a WRONG pose can score this
# high isn't measured, so don't feed it to the EKF here (ndt_ekf) until it is.
CAMPUS_NDT_MIN_SCORE = 1.5
# The grass is a kerb up, 0.30 m (Ben, 5 Nov), right on the car's usual 0.3 m floor, so half of
# every hit on it would count as an obstacle, or as a wall for NDT. NDT looks above it. The
# screen's cubes look below it, so the kerb and the grass show as the lidar's rings.
CAMPUS_NDT_FLOOR = 0.45
# m/s: the campus's roads are long. The car's own limit stays 1 m/s; this is Gazebo only.
CAMPUS_SPEED = '2.5'
CAMPUS_CUBE_FLOOR = 0.12


def world_file(share: str, world: str) -> str:
    """Return the path of a world in aav_gazebo's share folder, or say which ones exist."""
    if world == CAMPUS:
        path = os.path.abspath(CAMPUS_SDF)
        if not os.path.isfile(path):
            raise ValueError(f'world:={CAMPUS}: no {CAMPUS_SDF}. Make it with `pixi run campus`')
        return path
    folder = os.path.join(share, 'worlds')
    path = os.path.join(folder, f'{world}.sdf')
    if not os.path.isfile(path):
        known = sorted(f[:-len('.sdf')] for f in os.listdir(folder) if f.endswith('.sdf'))
        raise ValueError(f'world:={world}: no such world. Pick one of {known}')
    return path


def campus_start(place_text: str) -> Tuple[float, float, float]:
    """Return where place.yaml says the car starts on the campus: x, y (m), yaw (rad)."""
    start = yaml.safe_load(place_text)['start']
    return float(start['x']), float(start['y']), float(start['yaw'])


def has_sensors(path: str) -> bool:
    """Return True if the world loads the Sensors system, so it renders cameras and lidars."""
    root = ElementTree.parse(path).getroot()
    return any(p.get('name') == SENSORS for p in root.iter('plugin'))
