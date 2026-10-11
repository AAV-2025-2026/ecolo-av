"""Tests for tools/mcp_parts.py: the MCP server's parts that need neither ROS nor MCP."""

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_parts as parts  # noqa: E402

FILES = parts.readable_files()
SPEC = parts.load_contract()


def test_offers_the_docs_and_the_contracts():
    for f in ('README.md', 'CLAUDE.md', 'TODO.md', 'docs/perception.md',
              'docs/history/conversation.md', *parts.CONTRACTS):
        assert f in FILES
    assert [f for f in FILES if f.startswith('docs/html/')] == []
    assert [f for f in FILES if not f.endswith(('.md', '.yaml', '.dbc'))] == []


def test_never_offers_a_file_outside_git(tmp_path):
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'README.md').write_text('in git\n')
    (tmp_path / 'secrets.md').write_text('not in git\n')
    subprocess.run(['git', 'add', 'README.md'], cwd=tmp_path, check=True)
    assert parts.readable_files(tmp_path) == ['README.md']


def test_short_names():
    assert parts.find_page('perception', FILES) == 'docs/perception.md'
    assert parts.find_page('perception.md', FILES) == 'docs/perception.md'
    assert parts.find_page('docs/perception.md', FILES) == 'docs/perception.md'
    assert parts.find_page('README', FILES) == 'README.md'
    assert parts.find_page('conversation', FILES) == 'docs/history/conversation.md'
    assert parts.find_page('vehicle.yaml', FILES) == 'src/aav_description/config/vehicle.yaml'


def test_nothing_outside_the_list():
    for name in ('../../etc/passwd', '/etc/passwd', 'docs/html/index.html', 'pixi.toml',
                 '.mcp.json', ''):
        assert parts.find_page(name, FILES) is None


def test_search_any_case_with_a_limit():
    hits = parts.search('TWIST_MUX', FILES)
    assert hits and all(h.count(':') >= 2 for h in hits)
    assert len(parts.search('the', FILES, limit=5)) == 5
    assert parts.search('  ', FILES) == []


def test_contract_summary():
    text = parts.contract_summary(SPEC)
    assert '  /cmd_vel/joy  geometry_msgs/msg/TwistStamped' in text
    assert '  /spine/arm  std_srvs/srv/SetBool' in text
    assert '  /scripted_drive  aav_interfaces/action/ScriptedDrive' in text


def test_contract_for_a_topic_with_or_without_the_slash():
    text = parts.contract_for(SPEC, '/cmd_vel/joy')
    assert text == parts.contract_for(SPEC, 'cmd_vel/joy')
    assert 'geometry_msgs/msg/TwistStamped' in text and 'twist_mux' in text


def test_contract_for_a_node_or_a_frame():
    assert '/spine/arm' in parts.contract_for(SPEC, 'spine_bridge')
    assert 'rear axle' in parts.contract_for(SPEC, 'base_link')
    assert parts.contract_for(SPEC, 'no_such_thing') is None


def test_qos_asks_only_for_what_every_publisher_offers():
    assert parts.choose_qos([]) == (False, False)
    assert parts.choose_qos([(True, False), (True, False)]) == (True, False)
    assert parts.choose_qos([(True, True), (False, True)]) == (False, True)
    assert parts.choose_qos([(True, True)]) == (True, True)


def test_graph_text():
    text = parts.graph_text(
        ['/ego', '/twist_mux'],
        {'/cmd_vel': (['geometry_msgs/msg/TwistStamped'], ['twist_mux'], ['ego'])},
        {'/ego/get_parameters': ['rcl_interfaces/srv/GetParameters'],
         '/spine/arm': ['std_srvs/srv/SetBool']},
        'ROS domain 7, discovery range LOCALHOST')
    assert text.startswith('ROS domain 7, discovery range LOCALHOST')
    assert '  /cmd_vel  geometry_msgs/msg/TwistStamped' in text
    assert 'pub: twist_mux   sub: ego' in text
    assert '/spine/arm' in text and 'get_parameters' not in text


def test_shorten():
    assert parts.shorten('abc', 10) == 'abc'
    cut = parts.shorten('x' * 25, 10)
    assert cut.startswith('x' * 10) and '15 more characters' in cut


def test_the_server_never_writes_to_ros():
    source = (parts.ROOT / 'tools' / 'mcp_server.py').read_text()
    assert [w for w in parts.WRITES if w in source] == []


def test_the_profiles_match_check_graph():
    source = (parts.ROOT / 'tools' / 'check_graph.py').read_text()
    assert all(f"'{p}'" in source for p in parts.PROFILES)
