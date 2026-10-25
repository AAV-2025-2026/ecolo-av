"""
Check the car's behaviour trees: forward-only and reversing twins, and no spinning.

Each navigator has two trees: *_car.xml (forward only) and *_car_reversing.xml (with
BackUp). They must stay the same apart from BackUp, and BackUp must stay inside the car's
reverse speed (vehicle.yaml). No ROS needed.
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
TREES = PACKAGE / 'behavior_trees'
VEHICLE = PACKAGE.parents[1] / 'bringup' / 'aav_description' / 'config' / 'vehicle.yaml'
NAV2 = PACKAGE / 'config' / 'nav2.yaml'
NAVIGATORS = ['navigate_to_pose', 'navigate_through_poses']


def tree(name):
    return ET.parse(TREES / name).getroot()


def shape(element):
    """Return the tree as nested tuples: tag, attributes, children (comments dropped)."""
    return (element.tag, sorted(element.attrib.items()),
            [shape(child) for child in element])


def without_backup(element):
    for parent in element.iter():
        for child in list(parent):
            if child.tag == 'BackUp':
                parent.remove(child)
    return element


@pytest.mark.parametrize('navigator', NAVIGATORS)
def test_the_twins_differ_only_by_backup(navigator):
    forward = tree(f'{navigator}_car.xml')
    reversing = tree(f'{navigator}_car_reversing.xml')
    assert not list(forward.iter('BackUp'))
    assert len(list(reversing.iter('BackUp'))) == 1
    assert shape(without_backup(reversing)) == shape(forward)


@pytest.mark.parametrize('navigator', NAVIGATORS)
def test_backing_up_stays_inside_the_reverse_speed(navigator):
    limit = yaml.safe_load(VEHICLE.read_text())['vehicle']['max_reverse_speed']
    (backup,) = tree(f'{navigator}_car_reversing.xml').iter('BackUp')
    assert 0.0 < float(backup.get('backup_speed')) <= limit
    assert 0.0 < float(backup.get('backup_dist')) <= 2.0


@pytest.mark.parametrize('name', sorted(p.name for p in TREES.glob('*.xml')))
def test_no_tree_spins(name):
    # A car can't turn on the spot.
    assert not list(tree(name).iter('Spin'))


def test_the_behavior_server_can_back_up():
    plugins = yaml.safe_load(NAV2.read_text())['behavior_server']['ros__parameters']
    assert 'backup' in plugins['behavior_plugins']
    assert 'spin' not in plugins['behavior_plugins']
