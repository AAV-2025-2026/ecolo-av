"""
talk: type what the car should do in plain English; a local model plans; you say yes.

    pixi run -e llm talk                          ask, plan, confirm, drive (a loop)
    pixi run -e llm talk "drive 10 m forward"     one request
    pixi run -e llm talk --fake                   a pretend car, no ROS

It starts the drive server (drive_server.py) as its own child, over MCP stdio, with the
same ROS settings. The plan (every tool call, with its numbers) is printed first, and
nothing moves until you type "yes". "stop" and "estop" typed alone skip the model and run
at once; Ctrl-C while the car moves calls stop(). How it plans: react.py.

--yes (no question asked) is only for the automated tests: the server must say it may
drive here (a stand-in: LOCALHOST or a simulator), and --car is then not allowed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import signal
import sys
from typing import List, Optional

from aav_language import react
from aav_language.llm_mlx import DEFAULT_MODEL


def server_command(fake: bool, car: bool, max_speed: Optional[float]) -> List[str]:
    """Return the command that starts the drive server, with this same Python."""
    cmd = [sys.executable, '-m', 'aav_language.drive_server']
    if fake:
        cmd.append('--fake')
    if car:
        cmd.append('--car')
    if max_speed is not None:
        cmd += ['--max-speed', str(max_speed)]
    return cmd


@contextlib.asynccontextmanager
async def drive_session(cmd: List[str]):
    """Open an MCP session with the drive server; yield call_tool and the tool list."""
    import os

    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    params = StdioServerParameters(command=cmd[0], args=cmd[1:], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = (await session.list_tools()).tools
            tools = [t.model_dump(by_alias=True, exclude_none=True) for t in listed]

            async def call_tool(name: str, args: dict) -> str:
                result = await session.call_tool(name, args)
                text = '\n'.join(b.text for b in result.content if hasattr(b, 'text'))
                if result.is_error:
                    return json.dumps({'ok': False, 'message': text})
                return text
            yield call_tool, tools


def ask_yes(plan_text: str) -> bool:
    print(plan_text)
    try:
        answer = input('Type yes to drive it, anything else to cancel: ')
    except EOFError:
        return False
    return answer.strip().lower() == 'yes'


async def run_with_stop(agent: react.ReactAgent, plan: react.Plan, call_tool) -> list:
    """Run the plan; Ctrl-C meanwhile calls stop() (the drive then ends, slowing down)."""
    loop = asyncio.get_running_loop()
    stopping = []

    def on_ctrl_c():
        if not stopping:
            print('\nCtrl-C: stopping...', flush=True)
            stopping.append(loop.create_task(call_tool('stop', {})))
    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGINT, on_ctrl_c)
    try:
        done = await agent.execute(plan, lambda c, r: print('  ' + react.describe(c, r),
                                                            flush=True))
    finally:
        with contextlib.suppress(NotImplementedError):
            loop.remove_signal_handler(signal.SIGINT)
    for t in stopping:
        print('  stop:', json.loads(await t).get('message'))
    return done


async def handle(request: str, agent: react.ReactAgent, call_tool, auto_yes: bool,
                 verbose: bool) -> Optional[react.Plan]:
    fast = react.FAST.get(request.strip().lower().rstrip('!.'))
    if fast:
        print(f'  {fast}():', json.loads(await call_tool(fast, {})).get('message'))
        return None
    plan = await agent.plan(request)
    if plan.answer and (verbose or not plan.queued):
        # With a plan, the plan speaks: the model's own words ("the car has started...")
        # come before anything has moved, and can mislead.
        print(f'\n{plan.answer}')
    for call, why in plan.refused:
        print(f'  refused by the server: {call.text()}: {why}')
    if not plan.queued:
        return plan
    if auto_yes:
        print(plan.text() + '\n  (--yes: driving without asking; a stand-in only)')
    elif not ask_yes('\n' + plan.text()):
        print('Cancelled: nothing moved.')
        return plan
    await run_with_stop(agent, plan, call_tool)
    return plan


async def main_async(args) -> int:
    from aav_language.llm_mlx import MlxChat

    print(f'Loading {args.model} (the first time, it downloads)...', flush=True)
    llm = MlxChat(args.model)
    cmd = server_command(args.fake, args.car, args.max_speed)
    async with drive_session(cmd) as (call_tool, tools):
        status = json.loads(await call_tool('status', {}))
        if args.yes and (args.car or not status.get('may_drive_here')):
            print('--yes needs a stand-in (turtle, sim, bench: tools/ros.sh --local) and no '
                  '--car. ' + status.get('why_not', ''))
            return 2
        if not status.get('may_drive_here'):
            print(f'Note: the server will refuse to move here: {status.get("why_not")}')
        schemas = react.tool_schemas(tools)
        json_actions = args.json_actions or not llm.native_tools
        agent = react.ReactAgent(llm, call_tool, schemas, status.get('limits'),
                                 json_actions=json_actions,
                                 echo=print if args.verbose else (lambda s: None))
        if args.request:
            await handle(' '.join(args.request), agent, call_tool, args.yes, args.verbose)
            return 0
        print('Type what the car should do ("drive 10 m forward", "where are we?"). '
              '"stop" stops at once. Ctrl-D to quit.')
        while True:
            try:
                request = input('> ').strip()
            except EOFError:
                print()
                return 0
            if request:
                await handle(request, agent, call_tool, False, args.verbose)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Drive in plain English, through a local model.')
    p.add_argument('request', nargs='*', help='one request; none = ask in a loop')
    p.add_argument('--model', default=DEFAULT_MODEL, help='an MLX model on Hugging Face')
    p.add_argument('--fake', action='store_true', help='a pretend car: no ROS')
    p.add_argument('--car', action='store_true',
                   help='the REAL car (passed to the drive server); not with --yes')
    p.add_argument('--yes', action='store_true',
                   help='drive without asking: tests on a stand-in only')
    p.add_argument('--max-speed', type=float, default=None, help="the server's speed cap")
    p.add_argument('--json-actions', action='store_true',
                   help="JSON actions instead of the model's own tool format")
    p.add_argument('-v', '--verbose', action='store_true', help='print each Thought/Action')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.yes and args.car:
        sys.exit('--yes is for stand-ins only: never with --car')
    sys.exit(asyncio.run(main_async(args)))


if __name__ == '__main__':
    main()
