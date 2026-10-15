"""
The model test: each local model plans every request in eval_set.py, and is scored.

    pixi run -e llm llm-eval                                  the four default models
    pixi run -e llm llm-eval --models mlx-community/Qwen3-8B-4bit --out results.json

Each request gets a fresh pretend car: the drive server with --fake, over MCP stdio, as
the agent uses it. Only the plan is scored (nothing runs). Per model: correct plans (all,
moves, at-once, refusals), unreadable replies, seconds per model step, the most memory
MLX held, and the size on disk.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import statistics
import sys
import time

from aav_language import eval_set, react
from aav_language.agent import drive_session, server_command

MODELS = [
    'mlx-community/Llama-3.2-1B-Instruct-4bit',      # Ben's mcpsearch model
    'mlx-community/Qwen3-4B-Instruct-2507-4bit',
    'mlx-community/Qwen3.5-4B-4bit',
    'mlx-community/Qwen3-8B-4bit',
    'mlx-community/Meta-Llama-3.1-8B-Instruct-4bit',
]


def disk_gb(model_id: str) -> float:
    """Return the model's size in the Hugging Face cache, in GB (0 if not there)."""
    base = Path(os.environ.get('HF_HOME', Path.home() / '.cache' / 'huggingface')) / 'hub'
    snap = base / ('models--' + model_id.replace('/', '--')) / 'snapshots'
    total = 0
    for f in snap.rglob('*'):
        if f.is_file():
            total += f.stat().st_size      # follows the links into blobs/
    return total / 1e9


async def one_item(llm, item, json_actions: bool):
    async with drive_session(server_command(True, False, None)) as (call_tool, tools):
        status = json.loads(await call_tool('status', {}))
        agent = react.ReactAgent(llm, call_tool, react.tool_schemas(tools),
                                 status.get('limits'), json_actions=json_actions)
        plan = await agent.plan(item['say'])
    ok, why = eval_set.score(item, plan)
    return plan, ok, why


async def run_model(model_id: str, json_actions: bool, verbose: bool) -> dict:
    from aav_language.llm_mlx import MlxChat, peak_memory_gb, reset_peak_memory
    reset_peak_memory()
    t0 = time.monotonic()
    llm = MlxChat(model_id)
    load_s = time.monotonic() - t0
    use_json = json_actions or not llm.native_tools
    rows, step_times, bad = [], [], 0
    for item in eval_set.ITEMS:
        plan, ok, why = await one_item(llm, item, use_json)
        times = [s.seconds for s in plan.steps]
        step_times += times
        bad += sum(1 for s in plan.steps if s.call is None and s.observation.startswith('error'))
        rows.append({'id': item['id'], 'say': item['say'], 'kind': eval_set.kind(item),
                     'ok': ok, 'why': why, 'steps': len(plan.steps),
                     'seconds': round(sum(times), 2),
                     'queued': [c.text() for c in plan.queued],
                     'ran_now': [c.text() for c in plan.ran_now],
                     'answer': plan.answer[:300],
                     'raw': [s.raw[:400] for s in plan.steps]})
        mark = 'ok ' if ok else 'BAD'
        print(f'  {mark} {item["id"]:10s} {sum(times):5.1f} s  {why}', flush=True)
        if verbose and not ok:
            for s in plan.steps:
                print('       raw:', s.raw[:300].replace('\n', ' | '))
    by_kind = {}
    for k in ('move', 'now', 'refuse'):
        sel = [r for r in rows if r['kind'] == k]
        by_kind[k] = f'{sum(r["ok"] for r in sel)}/{len(sel)}'
    return {'model': model_id, 'format': 'json actions' if use_json else 'native tools',
            'correct': sum(r['ok'] for r in rows), 'total': len(rows), 'by_kind': by_kind,
            'unreadable_replies': bad, 'load_s': round(load_s, 1),
            'step_s_median': round(statistics.median(step_times), 2) if step_times else None,
            'step_s_max': round(max(step_times), 2) if step_times else None,
            'request_s_mean': round(sum(r['seconds'] for r in rows) / len(rows), 2),
            'peak_memory_gb': round(peak_memory_gb(), 2), 'disk_gb': round(disk_gb(model_id), 2),
            'rows': rows}


def table(results) -> str:
    lines = ['| Model | Correct | Moves | At once | Refusals | Unreadable | s/step (median) '
             '| s/request | Memory GB | Disk GB |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in results:
        lines.append(
            f'| {r["model"].split("/")[-1]} | **{r["correct"]}/{r["total"]}** | '
            f'{r["by_kind"]["move"]} | {r["by_kind"]["now"]} | {r["by_kind"]["refuse"]} | '
            f'{r["unreadable_replies"]} | {r["step_s_median"]} | {r["request_s_mean"]} | '
            f'{r["peak_memory_gb"]} | {r["disk_gb"]} |')
    return '\n'.join(lines)


async def main_async(args):
    results = []
    for model_id in args.models:
        print(f'== {model_id}', flush=True)
        results.append(await run_model(model_id, args.json_actions, args.verbose))
        print(table(results[-1:]), flush=True)
        if args.out:
            Path(args.out).write_text(json.dumps(results, indent=1))
    print('\n' + table(results))


def main(argv=None):
    p = argparse.ArgumentParser(description='Score local models on the plain-English test.')
    p.add_argument('--models', nargs='+', default=MODELS)
    p.add_argument('--out', help='also write every plan and score to this JSON file')
    p.add_argument('--json-actions', action='store_true',
                   help="JSON actions for every model, not the model's own tool format")
    p.add_argument('--only', nargs='+', help='only these item ids (eval_set.py)')
    p.add_argument('-v', '--verbose', action='store_true')
    args = p.parse_args(argv)
    if args.only:
        eval_set.ITEMS[:] = [i for i in eval_set.ITEMS if i['id'] in args.only]
    asyncio.run(main_async(args))
    return 0


if __name__ == '__main__':
    sys.exit(main())
