#!/usr/bin/env python3
"""
Start the MCP server the way an AI app does, over stdio, and check that it answers.

    pixi run -e mcp python3 tools/tests/mcp_smoke.py

tools/test.sh runs it when the mcp environment is installed. Everything stays on this
computer, on a ROS domain of its own: a stand-in publisher sends one test topic, and the
server must read it.
"""

import os
from pathlib import Path
import random
import signal
import subprocess
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[2]
TOOLS = {'list_pages', 'read_page', 'search_pages', 'contract', 'repo_status',
         'ros_graph', 'read_topic', 'check_contract', 'run_tests'}
TOPIC = '/aav_mcp_smoke'


async def call(session, tool, **arguments):
    result = await session.call_tool(tool, arguments)
    text = '\n'.join(block.text for block in result.content if hasattr(block, 'text'))
    assert not result.is_error, f'{tool}: {text}'
    return text


async def check(env):
    server = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / 'tools' / 'mcp_server.py')],
                                   cwd=str(ROOT), env=env)
    with anyio.fail_after(60):  # a stuck server fails the test, instead of hanging it
        return await talk(server, env)


async def talk(server, env):
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name: t for t in (await session.list_tools()).tools}
            assert set(tools) == TOOLS, sorted(tools)
            writers = sorted(n for n, t in tools.items() if not t.annotations.read_only_hint)
            assert writers == ['run_tests'], writers

            assert (await call(session, 'read_page', name='README')).startswith(
                '# file: README.md')
            assert 'No page called' in await call(session, 'read_page', name='../pixi.toml')
            assert 'docs/interfaces.yaml' in await call(session, 'list_pages')
            assert '/spine/arm' in await call(session, 'contract', name='spine_bridge')
            assert 'branch:' in await call(session, 'repo_status')

            graph = ''
            for _ in range(20):  # discovery takes a moment
                graph = await call(session, 'ros_graph')
                if TOPIC in graph:
                    break
                await anyio.sleep(0.5)
            where = f'ROS domain {env["ROS_DOMAIN_ID"]}, discovery range LOCALHOST'
            assert graph.startswith(where), graph[:120]
            assert TOPIC in graph, graph
            message = await call(session, 'read_topic', topic=TOPIC)
            assert 'data: smoke test' in message, message
            assert 'not on the graph' in await call(session, 'read_topic',
                                                    topic='/no_such_topic', timeout_s=1)
    return len(tools)


def stop(process):
    """Stop a process group started with start_new_session=True: politely, then not."""
    for sig in (signal.SIGINT, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except (ProcessLookupError, PermissionError):  # gone (on a Mac, only zombies left)
            return
        try:
            process.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def main():
    env = dict(os.environ, ROS_DOMAIN_ID=str(random.randint(60, 99)),
               ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST', AAV_MCP_DISCOVERY_WAIT='1')
    env.pop('ROS_STATIC_PEERS', None)
    # A stand-in publisher, in its own process group, so it's stopped with everything
    # it started, and nothing else.
    publisher = subprocess.Popen(
        ['ros2', 'topic', 'pub', '-r', '5', TOPIC, 'std_msgs/msg/String',
         '{data: smoke test}'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        count = anyio.run(check, env)
    finally:
        stop(publisher)
    print(f'the MCP server answers over stdio: {count} tools, and it read {TOPIC}')


if __name__ == '__main__':
    main()
