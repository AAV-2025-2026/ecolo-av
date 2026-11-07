#!/usr/bin/env python3
"""
A pretend ESP32 with `wifi-status`: its status lines, on this computer only.

It serves what the board's WiFi serves, so the page (and any reader of the lines, such as
hw_panel later) can be tried without a board:

| Path | Gives |
|---|---|
| `/` | the board's own page, `firmware/spine/boards/esp32-umod/page.html` |
| `/status.json` | the latest `status` line |
| `/scan` | a made-up scan that finds today's four devices |
| `/ws` | a WebSocket of `hb`, `status` and `event` lines (`firmware/status`) |

The lines start from `firmware/status/golden.jsonl` and move: the steering sweeps, the
brake comes on and off, the throttle ramps, the positions follow a little late, and the
mode changes now and then. `--lose` drops a line now and then, to see the gaps.

It listens on 127.0.0.1 only, and reads nothing it is sent: like the board, it is read
only. Python's standard library only.

    python3 tools/esp32_status_sim.py            # then open http://127.0.0.1:8765/
    python3 tools/esp32_status_sim.py --rate 20 --lose 50
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Iterator, List, Optional

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / 'firmware/status/golden.jsonl'
PAGE = ROOT / 'firmware/spine/boards/esp32-umod/page.html'
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'   # RFC 6455


def golden() -> List[dict]:
    """Return the contract's example lines."""
    return [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]


def dumps(line: dict) -> str:
    """One line as the firmware writes it: no spaces."""
    return json.dumps(line, separators=(',', ':'))


class Board:
    """The pretend board: makes the lines a real one would, from a made-up drive."""

    def __init__(self, rate_hz: float = 10.0, lose_every: int = 0):
        lines = golden()
        self.hb = next(line for line in lines if line['t'] == 'hb')
        self.status = next(line for line in lines if line['t'] == 'status')
        self.rate_hz = rate_hz
        self.lose_every = lose_every
        self.seq = 0
        self.made = 0
        self.up_ms = 0
        self.counter = 0
        self.frames = 0
        self.mode = 'computer'
        self.pos = {'steer': 1950.0, 'brake': 3500.0}
        self.latest: Optional[str] = None

    def _line(self, body: dict) -> Optional[str]:
        """Give a line its number; None if this one is 'lost' (the seq still moves on)."""
        line = {'t': body['t'], 'schema': 1, 'seq': self.seq, 'up_ms': self.up_ms}
        line.update({k: v for k, v in body.items() if k not in line})
        self.seq += 1
        self.made += 1
        if self.lose_every and self.made % self.lose_every == 0:
            return None
        return dumps(line)

    def step(self) -> Iterator[str]:
        """One status period: its lines, in order."""
        period_ms = round(1000 / self.rate_hz)
        self.up_ms += period_ms
        t = self.up_ms / 1000
        if self.up_ms // 1000 != (self.up_ms - period_ms) // 1000:
            hb = dict(self.hb, features='legacy-uart,wifi-status', build='sim')
            yield from filter(None, [self._line(hb)])
        # The mode: the computer drives for 20 s, then RC for 5 s.
        mode = 'computer' if t % 25 < 20 else 'rc'
        if mode != self.mode:
            yield from filter(None, [self._line(
                {'t': 'event', 'what': 'mode', 'from': self.mode, 'to': mode})])
            self.mode = mode
        steer = round(1950 + 900 * math.sin(t * 0.6))
        braking = math.sin(t * 0.25) < -0.3
        brake = 3500 if braking else 400
        dac = 0 if braking else round(350 + 300 * math.sin(t * 0.25))
        # The positions follow, a little behind, as a Jrk does.
        for key, target in (('steer', steer), ('brake', brake)):
            self.pos[key] += (target - self.pos[key]) * min(1.0, 4.0 / self.rate_hz)
        self.counter = (self.counter + 5) % 256
        self.frames += 5
        s = copy.deepcopy(self.status)
        s['rx'].update(counter=self.counter, check=(self.counter * 37) % 256,
                       steer=round((steer - 1950) / 1550, 3), speed=round(dac / 700, 3),
                       accel=-1.0 if braking else 0.0, age_ms=12)
        s['out'].update(steer_counts=steer, brake_counts=brake, dac=dac)
        s['low'].update(steer_counts=steer - 6, brake_counts=brake, dac=max(0, dac - 6))
        s['high'].update(steer_counts=steer + 6, brake_counts=brake, dac=dac)
        s['pos'].update(steer=round(self.pos['steer']), brake=round(self.pos['brake']))
        s['link'].update(frames=self.frames)
        s['state'].update(mode=self.mode)
        s['rc']['switch'] = 'computer' if self.mode == 'computer' else 'direct'
        line = self._line(s)
        if line:
            self.latest = line
            yield line


# --- the server: HTTP GET and a WebSocket, nothing more ---------------------------------

def accept_key(key: str) -> str:
    """Return the Sec-WebSocket-Accept for a client's Sec-WebSocket-Key (RFC 6455, 4.2.2)."""
    digest = hashlib.sha1((key + WS_GUID).encode()).digest()
    return base64.b64encode(digest).decode()


def text_frame(text: str) -> bytes:
    """One unmasked text frame, server to client."""
    data = text.encode()
    n = len(data)
    if n < 126:
        head = struct.pack('!BB', 0x81, n)
    elif n < 65536:
        head = struct.pack('!BBH', 0x81, 126, n)
    else:
        head = struct.pack('!BBQ', 0x81, 127, n)
    return head + data


class Server:
    def __init__(self, board: Board):
        self.board = board
        self.clients: List[asyncio.Queue] = []

    async def run_board(self):
        while True:
            for line in self.board.step():
                for q in self.clients:
                    if q.full():          # a slow reader loses the oldest, as on the board
                        q.get_nowait()
                    q.put_nowait(line)
            await asyncio.sleep(1 / self.board.rate_hz)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            writer.close()
            return
        request, *header_lines = head.decode(errors='replace').split('\r\n')
        headers = {k.strip().lower(): v.strip() for k, _, v in
                   (h.partition(':') for h in header_lines if h)}
        method, path = (request.split(' ') + ['', ''])[:2]
        path = path.split('?')[0]
        if method != 'GET':
            await self.reply(writer, '405 Method Not Allowed', 'text/plain', b'read only\n')
        elif path == '/ws' and headers.get('upgrade', '').lower() == 'websocket':
            await self.stream(reader, writer, headers.get('sec-websocket-key', ''))
        elif path == '/':
            await self.reply(writer, '200 OK', 'text/html', PAGE.read_bytes())
        elif path == '/status.json':
            await self.reply(writer, '200 OK', 'application/json',
                             (self.board.latest or '{}').encode())
        elif path == '/scan':
            await self.reply(writer, '200 OK', 'application/json',
                             b'{"scan":"done","found":[4,5,12,32]}')
        else:
            await self.reply(writer, '404 Not Found', 'text/plain', b'not found\n')

    @staticmethod
    async def reply(writer, status: str, kind: str, body: bytes):
        writer.write(f'HTTP/1.1 {status}\r\nContent-Type: {kind}\r\nContent-Length: '
                     f'{len(body)}\r\nConnection: close\r\n\r\n'.encode() + body)
        await writer.drain()
        writer.close()

    async def stream(self, reader, writer, key: str):
        writer.write(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                      'Connection: Upgrade\r\nSec-WebSocket-Accept: '
                      f'{accept_key(key)}\r\n\r\n').encode())
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        self.clients.append(q)
        # Whatever the client sends is read and dropped; its going away ends the stream.
        drain = asyncio.ensure_future(reader.read(-1))
        try:
            while not drain.done():
                get = asyncio.ensure_future(q.get())
                done, _ = await asyncio.wait({get, drain}, return_when=asyncio.FIRST_COMPLETED)
                if get not in done:
                    get.cancel()
                    break
                writer.write(text_frame(get.result()))
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            self.clients.remove(q)
            drain.cancel()
            writer.close()


async def serve(port: int, board: Board, ready: Optional[asyncio.Future] = None):
    server = Server(board)
    tcp = await asyncio.start_server(server.handle, '127.0.0.1', port)
    if ready is not None:
        ready.set_result(tcp.sockets[0].getsockname()[1])
    async with tcp:
        await asyncio.gather(tcp.serve_forever(), server.run_board())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split('\n\n')[0])
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--rate', type=float, default=10.0, help='status lines a second (5 to 20)')
    ap.add_argument('--lose', type=int, default=0, metavar='N',
                    help='drop every Nth line, to see gaps (0: none)')
    args = ap.parse_args(argv)
    print(f'A pretend ESP32 on http://127.0.0.1:{args.port}/ (the page), '
          f'ws://127.0.0.1:{args.port}/ws (the lines). Ctrl-C stops it.')
    try:
        asyncio.run(serve(args.port, Board(args.rate, args.lose)))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
