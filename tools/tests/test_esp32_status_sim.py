"""Tests for tools/esp32_status_sim.py: the pretend ESP32's status lines, and its server."""

import asyncio
import base64
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import esp32_status_sim as sim  # noqa: E402


def keys(d, prefix=''):
    out = set()
    for k, v in d.items():
        out.add(prefix + k)
        if isinstance(v, dict):
            out |= keys(v, prefix + k + '.')
    return out


def lines(board, periods):
    return [json.loads(line) for _ in range(periods) for line in board.step()]


def test_its_lines_have_the_golden_lines_fields():
    gold = {}
    for line in sim.golden():          # the first of each kind: its status has an rx
        gold.setdefault(line['t'], line)
    got = lines(sim.Board(rate_hz=10), 300)   # 30 s: a mode change too
    kinds = {line['t'] for line in got}
    assert kinds == {'hb', 'status', 'event', 'health', 'config', 'devices'}
    for line in got:
        assert keys(line) == keys(gold[line['t']]), line
        assert line['schema'] == 1


def test_seq_counts_up_by_one_and_lost_lines_leave_gaps():
    got = lines(sim.Board(), 50)
    seqs = [line['seq'] for line in got]
    assert seqs == list(range(len(seqs)))
    lossy = [line['seq'] for line in lines(sim.Board(lose_every=7), 50)]
    gaps = [b - a for a, b in zip(lossy, lossy[1:]) if b != a + 1]
    assert gaps and all(g == 2 for g in gaps)


def test_the_status_lines_come_at_the_rate():
    status = [line for line in lines(sim.Board(rate_hz=20), 40) if line['t'] == 'status']
    assert len(status) == 40
    assert status[1]['up_ms'] - status[0]['up_ms'] == 50
    hbs = [line for line in lines(sim.Board(rate_hz=10), 30) if line['t'] == 'hb']
    assert len(hbs) == 3


def test_the_values_stay_in_the_cars_ranges():
    for line in lines(sim.Board(), 600):
        if line['t'] == 'status':
            assert 400 <= line['out']['steer_counts'] <= 3500
            assert line['out']['brake_counts'] in (400, 3500)
            assert 0 <= line['out']['dac'] <= 700
            assert line['low']['dac'] <= line['out']['dac'] <= line['high']['dac']


def test_the_link_verdict_follows_the_mode():
    got = lines(sim.Board(rate_hz=10), 250)   # 25 s: computer, then RC
    status = [line for line in got if line['t'] == 'status']
    verdicts = {(s['state']['mode'], s['link']['verdict']) for s in status}
    assert verdicts == {('computer', 'ok'), ('rc', 'counter_frozen')}
    health = [line for line in got if line['t'] == 'health']
    assert len(health) == 25
    assert {h['link'] for h in health} == {'ok', 'counter_frozen'}
    assert sum(line['t'] == 'config' for line in got) == 3   # at start, 10 s, 20 s


def test_the_accept_key_is_rfc_6455s_example():
    assert sim.accept_key('dGhlIHNhbXBsZSBub25jZQ==') == 's3pPLMBiTxaQ9kYGzzhZRbK+xOo='


def test_the_server_gives_the_page_status_and_a_websocket():
    async def run():
        ready = asyncio.get_running_loop().create_future()
        task = asyncio.ensure_future(sim.serve(0, sim.Board(rate_hz=20), ready))
        port = await ready

        async def get(path):
            r, w = await asyncio.open_connection('127.0.0.1', port)
            w.write(f'GET {path} HTTP/1.1\r\nHost: x\r\n\r\n'.encode())
            data = await asyncio.wait_for(r.read(), 5)
            w.close()
            return data

        page = await get('/')
        assert page.startswith(b'HTTP/1.1 200') and b'read only' in page
        await asyncio.sleep(0.2)
        status = await get('/status.json')
        body = json.loads(status.split(b'\r\n\r\n', 1)[1])
        assert body['t'] == 'status'
        await asyncio.sleep(1.0)
        health = json.loads((await get('/health')).split(b'\r\n\r\n', 1)[1])
        assert health['t'] == 'health' and health['link'] == 'ok'
        config = json.loads((await get('/config')).split(b'\r\n\r\n', 1)[1])
        assert config['t'] == 'config' and config['idle_brake'] == 1.0
        assert (await get('/nothing')).startswith(b'HTTP/1.1 404')

        r, w = await asyncio.open_connection('127.0.0.1', port)
        key = base64.b64encode(os.urandom(16)).decode()
        w.write(('GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                 f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        head = await asyncio.wait_for(r.readuntil(b'\r\n\r\n'), 5)
        assert b'101' in head and sim.accept_key(key).encode() in head
        got = []
        for _ in range(3):
            b0, b1 = await asyncio.wait_for(r.readexactly(2), 5)
            assert b0 == 0x81
            n = b1 & 0x7F
            if n == 126:
                n = int.from_bytes(await r.readexactly(2), 'big')
            got.append(json.loads(await r.readexactly(n)))
        w.close()
        task.cancel()
        return got

    got = asyncio.run(run())
    assert all(line['schema'] == 1 for line in got)
    assert [line['seq'] for line in got] == sorted(line['seq'] for line in got)
