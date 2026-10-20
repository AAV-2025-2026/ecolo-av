"""Tests for the Lichtblick layout: every topic it shows is one the contract has."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads((ROOT / 'src/aav_bringup/lichtblick/car.json').read_text())
TOPICS = set(yaml.safe_load((ROOT / 'docs/interfaces.yaml').read_text())['topics'])


def shown_topics():
    """Yield each topic a panel reads, from its own way of naming it."""
    for panel, config in LAYOUT['configById'].items():
        kind = panel.split('!')[0]
        if kind == '3D':
            yield from config['topics']
        elif kind == 'Image':
            yield config['imageMode']['imageTopic']
        elif kind == 'Indicator':
            yield config['path'].split('.')[0]
        elif kind == 'Plot':
            yield from (p['value'].split('.')[0] for p in config['paths'])
        elif kind == 'RawMessages':
            yield config['topicPath'].split('.')[0]


def test_every_topic_is_in_the_contract():
    shown = set(shown_topics())
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
