"""Tests for the Lichtblick layout: every topic it shows is one the contract has."""

import json
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout_check  # noqa: E402, I100

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads((ROOT / 'src/aav_bringup/lichtblick/car.json').read_text())
TOPICS = set(yaml.safe_load((ROOT / 'docs/interfaces.yaml').read_text())['topics'])


def test_every_topic_is_in_the_contract():
    shown = layout_check.shown_topics(LAYOUT)
    assert shown, 'the layout shows no topics'
    assert shown <= TOPICS, f'not in docs/interfaces.yaml: {sorted(shown - TOPICS)}'


def test_every_panel_in_the_layout_has_its_settings():
    def leaves(node):
        if isinstance(node, str):
            yield node
        else:
            yield from leaves(node['first'])
            yield from leaves(node['second'])
    assert sorted(leaves(LAYOUT['layout'])) == sorted(LAYOUT['configById'])


def test_the_optional_topics_are_ones_the_layout_shows():
    assert set(layout_check.OPTIONAL) <= layout_check.shown_topics(LAYOUT)


def test_the_bridge_topics_come_from_its_advertise_messages():
    payloads = [
        json.dumps({'op': 'serverInfo', 'name': 'foxglove_bridge'}),
        json.dumps({'op': 'advertise', 'channels': [{'id': 1, 'topic': '/vehicle/odom'},
                                                    {'id': 2, 'topic': '/plan'}]}),
        json.dumps({'op': 'advertise', 'channels': [{'id': 3, 'topic': '/tf'}]}),
    ]
    assert layout_check.advertised(payloads) == {'/vehicle/odom', '/plan', '/tf'}
