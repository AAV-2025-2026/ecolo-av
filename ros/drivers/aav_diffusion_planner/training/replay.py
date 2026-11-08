#!/usr/bin/env python3
"""
Replay the plans a Gazebo run recorded through a model, offline: the guard's score, by check.

    pixi run diffusion replay <folder>... [--model planner.onnx] [--samples 16]

The node saves each plan's inputs with diffusion_record:=<folder> (or `pixi run measure
controllers --planners diffusion --diffusion-record <folder>`): the global costmap, the
start, the goal, the lattice's path, and what the node chose then. This runs the same
requests through any model, with the node's own crop, smoothing and guard, so a new model
or sampler is scored on the very plans the car asked for, without Gazebo.

Runs in the learn environment (no ROS). It prints, and with --json writes: plans, the share
with a sample that passes, samples passed, refusals by check, the model's time a plan,
and the same split by what the node chose in the run (to compare before and after).
"""

import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from aav_diffusion_planner import guard, window  # noqa: E402
import numpy as np  # noqa: E402
import train  # noqa: E402


def load(folders):
    """Return each recorded plan's npz, in order, from every folder (and its subfolders)."""
    files = []
    for folder in folders:
        files += sorted(glob.glob(os.path.join(folder, '**', 'plan_*.npz'), recursive=True))
    return [(f, np.load(f)) for f in files]


def replay(plans, run, samples, seed=0, gear_smooth=True):
    """
    Return the guard's score of `run` on recorded plans.

    run(crop (1,1,S,S), cond (1,COND), noise (K,POINTS,CHANNELS)) -> (K,POINTS,CHANNELS).
    """
    poly, lock = train.vehicle_numbers()
    fp = guard.footprint_points(poly)
    rng = np.random.default_rng(seed)
    out = {'plans': 0, 'plans_with_a_pass': 0, 'samples': 0, 'samples_passed': 0,
           'refusals_by_check': dict.fromkeys(guard.CHECKS, 0), 'model_ms': [],
           'guard_ms': [], 'by_run_source': {}}
    for name, d in plans:
        grid = window.Grid(d['costmap'], float(d['origin'][0]), float(d['origin'][1]),
                           float(d['resolution']))
        start, goal = tuple(d['start']), tuple(d['goal'])
        rev = bool(d['reversing'])
        lattice = d['lattice']
        lattice_len = guard.length(lattice) if len(lattice) > 1 else None
        win = window.window_for(start, goal)
        crop = window.crop(grid, win)
        cond = window.cond(win, start, goal, rev)
        noise = rng.standard_normal((samples, window.POINTS, window.CHANNELS)).astype(
            np.float32)
        t0 = time.perf_counter()
        raw = run(crop[None, None].astype(np.float32), cond[None], noise)
        out['model_ms'].append(1000.0 * (time.perf_counter() - t0))
        t0 = time.perf_counter()
        paths, gears = window.decode_paths(win, raw)
        lim = guard.Limits(min_radius=0.95 * lock, reversing=rev)
        smoothed, again = window.smoothed(paths, gears, by_gear=gear_smooth)
        best, _, refusals, passed = guard.choose(smoothed, grid, start, goal, lim, fp,
                                                 lattice_len, again)
        out['guard_ms'].append(1000.0 * (time.perf_counter() - t0))
        out['plans'] += 1
        out['plans_with_a_pass'] += best is not None
        out['samples'] += len(smoothed)
        out['samples_passed'] += passed
        for c, n in refusals.items():
            out['refusals_by_check'][c] += n
        then = str(d['source'])
        split = out['by_run_source'].setdefault(then, {'plans': 0, 'now_pass': 0})
        split['plans'] += 1
        split['now_pass'] += best is not None
    for key in ('model_ms', 'guard_ms'):
        ms = sorted(out[key])
        out[key] = ({'mean': round(float(np.mean(ms)), 1), 'worst': round(ms[-1], 1)}
                    if ms else None)
    if out['plans']:
        out['share_with_a_pass'] = round(out['plans_with_a_pass'] / out['plans'], 3)
        out['share_samples_passed'] = round(out['samples_passed'] / out['samples'], 3)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('folders', nargs='+', help='folders the node recorded into')
    parser.add_argument('--model', default=os.path.join(train.OUT, 'planner.onnx'))
    parser.add_argument('--provider', default='CPUExecutionProvider')
    parser.add_argument('--samples', type=int, default=train.SAMPLES)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--average-smooth', action='store_true',
                        help="2 Nov's smoothing: one average over the whole path")
    parser.add_argument('--json', help='also write the score here')
    args = parser.parse_args()
    plans = load(args.folders)
    if not plans:
        sys.exit(f'no plan_*.npz in {", ".join(args.folders)}')
    score = replay(plans, train.onnx_fn(args.model, args.provider), args.samples, args.seed,
                   gear_smooth=not args.average_smooth)
    score['smoothing'] = 'average' if args.average_smooth else 'by gear'
    score['model'] = os.path.abspath(args.model)
    score['samples_a_plan'] = args.samples
    text = json.dumps(score, indent=1)
    print(text)
    if args.json:
        with open(args.json, 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
