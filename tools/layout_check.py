#!/usr/bin/env python3
"""
Check our Lichtblick layout against a live foxglove_bridge: each topic, served or not.

    python3 tools/layout_check.py                          # ws://localhost:8765 (the sim)
    python3 tools/layout_check.py ws://192.168.1.140:8765  # the Jetson

It connects as Lichtblick does (a WebSocket, subprotocol foxglove.sdk.v1, or the older
foxglove.websocket.v1), collects the topics the bridge advertises for a few seconds, and
lists each of the layout's topics as served or missing. Some come only from parts that are
off by default (OPTIONAL): those are missing without being a fault.

No ROS and no extra Python packages: it runs on any Mac. It only reads: it never
subscribes, so the bridge sends it nothing but the topic list.
Exit status: 0 if every topic that isn't optional is served.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / 'src/aav_bringup/lichtblick/car.json'
PROTOCOLS = ('foxglove.sdk.v1', 'foxglove.websocket.v1')   # newest first
# The layout's topics that come from parts that are off unless asked for.
OPTIONAL = {
    '/safety/ghost/marker': 'ghost:=true (aav_ghost)',
    '/drivers/nav/route/path': 'the street router, once it has a route',
}


def shown_topics(layout):
    """Return the set of topics a layout's panels read, from each panel's own setting."""
    shown = set()
    for panel, config in layout['configById'].items():
        kind = panel.split('!')[0]
        if kind == '3D':
            shown |= set(config['topics'])
        elif kind == 'Image':
            shown.add(config['imageMode']['imageTopic'])
        elif kind == 'Indicator':
            shown.add(config['path'].split('.')[0])
        elif kind == 'Plot':
            shown |= {p['value'].split('.')[0] for p in config['paths']}
        elif kind == 'RawMessages':
            shown.add(config['topicPath'].split('.')[0])
    return shown


def advertised(payloads):
    """Return the set of topics in the bridge's text messages (its 'advertise' ops)."""
    topics = set()
    for payload in payloads:
        message = json.loads(payload)
        if message.get('op') == 'advertise':
            topics |= {channel['topic'] for channel in message['channels']}
    return topics


class Connection:
    """A bare WebSocket client: enough to read a foxglove_bridge's text frames."""

    def __init__(self, url, protocol, timeout=5.0):
        parts = urlparse(url)
        self.host, self.port = parts.hostname, parts.port or 8765
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (f'GET {parts.path or "/"} HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n'
             'Upgrade: websocket\r\nConnection: Upgrade\r\n'
             f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
             f'Sec-WebSocket-Protocol: {protocol}\r\n\r\n').encode())
        self.buf = b''
        while b'\r\n\r\n' not in self.buf:
            self.buf += self._recv()
        head, self.buf = self.buf.split(b'\r\n\r\n', 1)
        self.status = head.split(b'\r\n')[0].decode(errors='replace')
        self.ok = ' 101 ' in self.status

    def _recv(self):
        chunk = self.sock.recv(65536)
        if not chunk:
            raise EOFError('the bridge closed the connection')
        return chunk

    def _take(self, n):
        while len(self.buf) < n:
            self.buf += self._recv()
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def text_frames(self, seconds):
        """Yield the text frames' payloads for `seconds` (the server's frames aren't masked)."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                first, second = self._take(2)
                n = second & 0x7f
                if n == 126:
                    (n,) = struct.unpack('>H', self._take(2))
                elif n == 127:
                    (n,) = struct.unpack('>Q', self._take(8))
                payload = self._take(n)
            except (socket.timeout, EOFError):
                return
            if first & 0x0f == 1:
                yield payload

    def close(self):
        self.sock.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('url', nargs='?', default='ws://localhost:8765')
    ap.add_argument('--layout', default=str(LAYOUT))
    ap.add_argument('--seconds', type=float, default=5.0, help='how long to listen')
    args = ap.parse_args()

    want = shown_topics(json.loads(Path(args.layout).read_text()))
    for protocol in PROTOCOLS:
        try:
            conn = Connection(args.url, protocol)
        except OSError as e:
            print(f'no bridge at {args.url}: {e}. Is foxglove:=true on?')
            return 2
        if conn.ok:
            break
        conn.close()
    else:
        print(f'{args.url} refused both {" and ".join(PROTOCOLS)}: {conn.status}')
        return 2
    topics = advertised(conn.text_frames(args.seconds))
    conn.close()

    print(f'{args.url} ({protocol}) serves {len(topics)} topics; the layout shows {len(want)}:')
    faults = 0
    for topic in sorted(want):
        if topic in topics:
            print(f'  served    {topic}')
        elif topic in OPTIONAL:
            print(f'  off       {topic}   (only with {OPTIONAL[topic]})')
        else:
            print(f'  MISSING   {topic}')
            faults += 1
    return 1 if faults else 0


if __name__ == '__main__':
    sys.exit(main())
