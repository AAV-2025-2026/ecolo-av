#!/usr/bin/env python3
"""
Check that this computer can join the car's ROS network, and say what to fix.

usage: pixi run doctor          (or: tools/ros.sh python3 tools/doctor.py)

Each line says OK, WARN or FIX. Nothing here changes a setting. The steps behind
each fix are in docs/mac.md ("Join the car's network").
"""

import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CAR_NODES = ('/ego', '/twist_mux')   # running on the car whenever it can drive
CAR_SUBNET = '192.168.1.'           # the 2025-26 car network

counts = {'OK': 0, 'WARN': 0, 'FIX': 0}


def say(status, what, detail):
    counts[status] += 1
    colour = {'OK': '32', 'WARN': '33', 'FIX': '31'}[status]
    tag = f'\033[1;{colour}m{status:<4}\033[0m' if sys.stdout.isatty() else f'{status:<4}'
    print(f'  {tag}  {what:<16} {detail}')


def run(cmd, timeout=10):
    """Return a command's output, or '' if it can't run."""
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return done.stdout + done.stderr
    except (OSError, subprocess.TimeoutExpired):
        return ''


def addresses():
    """Return this computer's IPv4 addresses, without 127.x."""
    for cmd in (['ip', '-4', '-o', 'addr', 'show'], ['ifconfig']):
        out = run(cmd)
        if out:
            found = re.findall(r'inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)', out)
            return [a for a in found if not a.startswith('127.')]
    return []


def multicast_works():
    """Send one multicast packet to ourselves, the way ROS finds other computers."""
    receiver = subprocess.Popen(['ros2', 'multicast', 'receive'], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(3):
            try:   # give the receiver time to start, then send
                return 'Received' in receiver.communicate(timeout=1.5)[0]
            except subprocess.TimeoutExpired:
                run(['ros2', 'multicast', 'send'], timeout=5)
        try:
            return 'Received' in receiver.communicate(timeout=1.5)[0]
        except subprocess.TimeoutExpired:
            return False
    finally:
        receiver.kill()


def clock_offset():
    """Return how far the car's clock is ahead of ours (s), from one /tf stamp, or None."""
    out = run(['ros2', 'topic', 'echo', '--once', '--no-daemon', '/tf',
               'tf2_msgs/msg/TFMessage'], timeout=10)
    m = re.search(r'sec: (\d+)\s+nanosec: (\d+)', out)
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) * 1e-9 - time.time()


def main():
    env = os.environ
    print("AAV doctor: can this computer join the car's ROS network?\n")

    distro = env.get('ROS_DISTRO', '')
    if distro == 'jazzy':
        say('OK', 'ROS 2', 'Jazzy')
    else:
        say('FIX', 'ROS 2', f'{distro or "not found"}: run this as `pixi run doctor`')
        return

    if (ROOT / 'install' / 'setup.bash').exists():
        say('OK', 'Workspace', 'built')
    else:
        say('FIX', 'Workspace', 'not built: `pixi run build`')

    rmw = env.get('RMW_IMPLEMENTATION', '')
    if rmw in ('', 'rmw_fastrtps_cpp'):
        say('OK', 'Middleware', 'Fast DDS, the same as the car')
    else:
        say('FIX', 'Middleware', f'{rmw}: the car uses Fast DDS. `unset RMW_IMPLEMENTATION`')

    domain = env.get('ROS_DOMAIN_ID', '')
    if domain:
        say('OK', 'Domain ID', f"{domain}: it must match the car's")
    else:
        say('WARN', 'Domain ID', "not set (0). Set the car's: `export ROS_DOMAIN_ID=<n>`")

    reach = env.get('ROS_AUTOMATIC_DISCOVERY_RANGE', '') or 'SUBNET'
    if reach == 'SUBNET':
        say('OK', 'Discovery', 'the whole local network')
    elif reach == 'LOCALHOST':
        say('WARN', 'Discovery', 'this computer only: `unset ROS_AUTOMATIC_DISCOVERY_RANGE`')
    else:
        say('FIX', 'Discovery', f'{reach}: `unset ROS_AUTOMATIC_DISCOVERY_RANGE`')
    if env.get('ROS_STATIC_PEERS'):
        say('OK', 'Static peers', env['ROS_STATIC_PEERS'])

    addrs = addresses()
    if not addrs:
        say('FIX', 'Network', "no network address: join the car's WiFi")
    elif any(a.startswith(CAR_SUBNET) for a in addrs):
        # Many home routers use this range too: only "The car" below proves it's the car.
        say('OK', 'Network', f'{", ".join(addrs)}: in the car\'s range ({CAR_SUBNET}x), as '
                             'many home routers are. "The car" below confirms it')
    else:
        say('WARN', 'Network', f'{", ".join(addrs)}: the car used {CAR_SUBNET}x. '
                               'On its WiFi?')

    if multicast_works():
        say('OK', 'Multicast', 'works on this computer')
    else:
        say('WARN', 'Multicast', 'blocked here: allow it, or set ROS_STATIC_PEERS')

    if sys.platform == 'darwin':
        state = run(['/usr/libexec/ApplicationFirewall/socketfilterfw', '--getglobalstate'])
        if 'enabled' in state:
            say('WARN', 'Mac firewall', 'on: click Allow when python3 or rviz2 asks')
        elif state:
            say('OK', 'Mac firewall', 'off')

    nodes = run(['ros2', 'node', 'list', '--no-daemon', '--spin-time', '3'], timeout=20)
    nodes = [n for n in nodes.split() if n.startswith('/')]
    seen = [n for n in CAR_NODES if n in nodes]
    if seen:
        say('OK', 'The car', f'{len(nodes)} nodes visible, including {" and ".join(seen)}')
        offset = clock_offset()
        if offset is None:
            say('WARN', 'Clock', 'no /tf message to compare with')
        elif abs(offset) > 1e8:
            say('OK', 'Clock', 'the stack runs on simulated time: nothing to compare')
        elif abs(offset) < 0.5:
            say('OK', 'Clock', f"within {abs(offset):.2f} s of the car's")
        else:
            say('WARN', 'Clock', f"{offset:+.1f} s from the car's: RViz will drop data. "
                                 'Sync the clocks (docs/mac.md)')
    elif nodes:
        say('WARN', 'The car', f'{len(nodes)} nodes, but not ego or twist_mux: is this '
                               'stack running on the car, on Jazzy?')
    else:
        say('WARN', 'The car', 'no nodes visible: is the car on, with the same domain ID?')

    if counts['FIX']:
        print(f"\n{counts['FIX']} to fix. See docs/mac.md.")
    elif counts['WARN']:
        print('\nNothing blocks. Check the WARN lines before joining the car (docs/mac.md).')
    else:
        print('\nAll set.')


if __name__ == '__main__':
    main()
    sys.exit(1 if counts['FIX'] else 0)
