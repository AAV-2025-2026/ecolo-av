"""
Tests for the Foxglove/Lichtblick layouts in tools/foxglove/.

Every topic they show is one the contract has, and one the bridge's WiFi list lets
through.
"""

import json
from pathlib import Path
import re
import struct
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout_check  # noqa: E402, I100

ROOT = Path(__file__).resolve().parents[2]
TOPICS = set(yaml.safe_load((ROOT / 'docs/interfaces.yaml').read_text())['topics'])
BRIDGE = yaml.safe_load((ROOT / 'src/aav_bringup/config/foxglove_bridge.yaml').read_text())
WIFI = BRIDGE['foxglove_bridge']['ros__parameters']['topic_whitelist']
LAYOUTS = {p.stem: json.loads(p.read_text()) for p in layout_check.LAYOUTS}


def test_the_three_layouts_are_there():
    assert set(LAYOUTS) == {'driving', 'sensors-health', 'map'}


@pytest.mark.parametrize('name', sorted(LAYOUTS))
def test_every_topic_is_in_the_contract(name):
    shown = layout_check.shown_topics(LAYOUTS[name])
    assert shown, 'the layout shows no topics'
    unknown = shown - TOPICS - layout_check.NAV2_OWN
    assert not unknown, f'not in docs/interfaces.yaml: {sorted(unknown)}'


@pytest.mark.parametrize('name', sorted(LAYOUTS))
def test_every_topic_gets_through_the_wifi_list(name):
    # The car's bridge leaves the big topics out: a layout that shows one shows nothing.
    blocked = {t for t in layout_check.shown_topics(LAYOUTS[name])
               if not any(re.fullmatch(p, t) for p in WIFI)}
    assert not blocked, f'the bridge does not send these over WiFi: {sorted(blocked)}'


@pytest.mark.parametrize('name', sorted(LAYOUTS))
def test_every_panel_in_the_layout_has_its_settings(name):
    def leaves(node):
        if isinstance(node, str):
            yield node
        else:
            yield from leaves(node['first'])
            yield from leaves(node['second'])
    layout = LAYOUTS[name]
    assert sorted(leaves(layout['layout'])) == sorted(layout['configById'])


def test_the_optional_topics_are_ones_a_layout_shows():
    shown = set().union(*(layout_check.shown_topics(x) for x in LAYOUTS.values()))
    assert set(layout_check.OPTIONAL) <= shown
    assert layout_check.NAV2_OWN <= shown


def test_the_driving_layout_shows_the_cameras_preview_not_its_pictures():
    shown = layout_check.shown_topics(LAYOUTS['driving'])
    assert '/perception/camera/front_left/preview/compressed' in shown
    assert not any(t.endswith('/image_raw') or t.endswith('/image') for t in shown)


def test_an_unknown_panel_is_refused():
    with pytest.raises(ValueError, match='Gauge!x'):
        layout_check.shown_topics({'configById': {'Gauge!x': {}}})


def test_the_bridge_topics_come_from_its_advertise_messages():
    payloads = [
        json.dumps({'op': 'serverInfo', 'name': 'foxglove_bridge'}),
        json.dumps({'op': 'advertise', 'channels': [{'id': 1, 'topic': '/vehicle/odom'},
                                                    {'id': 2, 'topic': '/plan'}]}),
        json.dumps({'op': 'advertise', 'channels': [{'id': 3, 'topic': '/tf'}]}),
        json.dumps({'op': 'unadvertise', 'channelIds': [2]}),
    ]
    assert layout_check.advertised(payloads) == {'/vehicle/odom': 1, '/tf': 3}


def test_message_data_is_the_subscription_and_the_message_size():
    frame = bytes([0x01]) + struct.pack('<IQ', 7, 123) + b'abcde'
    assert layout_check.message_data(frame) == (7, 5)
    assert layout_check.message_data(bytes([0x02, 0, 0])) is None   # another op
