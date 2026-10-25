"""Tests for .mcp.json: the AI apps' servers. The drive server there must never reach the car."""

import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
SERVERS = json.loads((ROOT / '.mcp.json').read_text())['mcpServers']
TASKS = tomllib.loads((ROOT / 'pixi.toml').read_text())['feature']['mcp']['tasks']


def test_both_servers_run_through_pixi():
    assert set(SERVERS) == {'aav', 'aav-drive'}
    for server in SERVERS.values():
        assert server['command'] == 'pixi'
        assert server['args'][:4] == ['run', '--frozen', '-e', 'mcp']


def test_the_drive_server_never_gets_the_car():
    # Without --car the server refuses unless it sees only stand-ins on this computer.
    assert '--car' not in SERVERS['aav-drive']['args']
    assert SERVERS['aav-drive']['args'][4] == 'drive-server'


def test_the_drive_task_keeps_ros_on_this_computer():
    assert TASKS['drive-server']['cmd'].startswith('tools/ros.sh --local ')
