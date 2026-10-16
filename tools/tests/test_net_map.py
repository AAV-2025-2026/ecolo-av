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


# Friday's setup (Ben, 15 Oct): the phone's hotspot on WiFi for the internet, and a USB
# Ethernet dongle to the car's switch.
HOTSPOT_AND_DONGLE = """\
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
\tinet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tinet 172.20.10.4 netmask 0xfffffff0 broadcast 172.20.10.15
en7: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tinet 192.168.1.50 netmask 0xffffff00 broadcast 192.168.1.255
"""
MAC_ROUTE = """\
   route to: default
destination: default
    gateway: 172.20.10.1
  interface: en0
"""


def test_interfaces_keep_their_names():
    named = net_map.parse_named_interfaces(HOTSPOT_AND_DONGLE)
    assert [(n, str(i)) for n, i in named] == [('en0', '172.20.10.4/28'),
                                               ('en7', '192.168.1.50/24')]
    assert [(n, str(i)) for n, i in net_map.parse_named_interfaces(LINUX_IP)] == [
        ('eth0', '10.0.0.5/16')]


def test_the_car_is_the_network_that_is_not_the_internet():
    named = net_map.parse_named_interfaces(HOTSPOT_AND_DONGLE)
    internet = net_map.route_interface(MAC_ROUTE)
    assert internet == 'en0'
    (name, iface), why = net_map.choose_interface(named, internet)
    assert (name, str(iface)) == ('en7', '192.168.1.50/24') and 'en0' in why
    assert net_map.route_interface('default via 10.0.0.1 dev eth0 proto dhcp') == 'eth0'


def test_asking_for_an_interface_wins_and_a_wrong_one_says_what_exists():
    named = net_map.parse_named_interfaces(HOTSPOT_AND_DONGLE)
    assert net_map.choose_interface(named, 'en0', 'en0')[0][0] == 'en0'
    try:
        net_map.choose_interface(named, 'en0', 'en9')
    except ValueError as e:
        assert 'en7 192.168.1.50/24' in str(e)
    else:
        raise AssertionError('en9 should have been refused')
    one = net_map.parse_named_interfaces(MAC_IFCONFIG)
    assert net_map.choose_interface(one, 'en0')[0][0] == 'en0'  # the only one, even if internet
