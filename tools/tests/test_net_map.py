"""Tests for tools/net_map.py: the parts that need no network."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import net_map  # noqa: E402

MAC_ARP = """\
? (192.168.1.41) at 34:19:4d:95:95:2c on en0 ifscope [ethernet]
? (192.168.1.73) at 6c:1f:8a:30:2:9e on en0 ifscope [ethernet]
? (192.168.1.2) at (incomplete) on en0 ifscope [ethernet]
"""
LINUX_NEIGH = """\
192.168.1.10 dev eth0 lladdr 48:b0:2d:01:02:03 REACHABLE
192.168.1.11 dev eth0  FAILED
"""
MAC_IFCONFIG = """\
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
\tinet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tinet 192.168.1.98 netmask 0xffffff00 broadcast 192.168.1.255
"""
LINUX_IP = """\
1: lo    inet 127.0.0.1/8 scope host lo
2: eth0    inet 10.0.0.5/16 brd 10.0.255.255 scope global eth0
"""


def test_mac_zeros_come_back():
    assert net_map.normal_mac('6c:1f:8a:30:2:9e') == '6c:1f:8a:30:02:9e'
    assert net_map.normal_mac('(incomplete)') is None


def test_arp_on_a_mac_skips_incomplete():
    assert net_map.parse_arp(MAC_ARP) == {
        '192.168.1.41': '34:19:4d:95:95:2c', '192.168.1.73': '6c:1f:8a:30:02:9e'}


def test_ip_neigh_on_linux():
    assert net_map.parse_arp(LINUX_NEIGH) == {'192.168.1.10': '48:b0:2d:01:02:03'}


def test_interfaces_from_ifconfig_and_ip():
    assert [str(i) for i in net_map.parse_interfaces(MAC_IFCONFIG)] == ['192.168.1.98/24']
    assert [str(i) for i in net_map.parse_interfaces(LINUX_IP)] == ['10.0.0.5/16']


def test_makers():
    assert net_map.maker('dc:a6:32:00:00:01') == 'Raspberry Pi'
    assert net_map.maker('48:b0:2d:00:00:01').startswith('NVIDIA')
    assert 'random' in net_map.maker('72:41:9c:06:f3:57')   # locally administered
    assert net_map.maker('34:19:4d:95:95:2c') == ''


def test_domain_ports():
    assert net_map.domain_of_port(7400) == 0
    assert net_map.domain_of_port(7400 + 250 * 42) == 42
    assert net_map.domain_of_port(7401) is None


def test_rtps_packets():
    packet = b'RTPS\x02\x03\x01\x0f' + bytes(range(12)) + b'rest'
    assert net_map.read_rtps(packet) == ('Fast DDS', bytes(range(12)).hex())
    assert net_map.read_rtps(b'HTTP/1.1 200 OK and more bytes') is None
    assert net_map.read_rtps(b'RTPS') is None


def test_table():
    assert net_map.table([['a', 'b']], ['X', 'Y']) == '| X | Y |\n|---|---|\n| a | b |'
