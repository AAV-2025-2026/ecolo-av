#!/usr/bin/env python3
r"""
Time the diffusion planner on this computer, against its budget: for the Orin.

    pixi run measure diffusion                                   (Pixi's learn environment)
    pixi run measure diffusion --provider CoreMLExecutionProvider        (a Mac's GPU)
    python3 ros/drivers/aav_diffusion_planner/training/measure.py \\
        --provider TensorrtExecutionProvider                     (the Orin, JetPack's Python)

For each plan, as the node does it: the costmap crop, the model (16 samples, its steps),
the guard (smoothing and G1-G8). It prints each part's mean, 95th percentile and worst
against the budget (engines.BUDGET: crop 2, model 50, guard 10, total 100 ms; the hard
stop 150 ms, after which the node takes the lattice's path), and says OK or OVER.

Needs only Python 3, NumPy and ONNX Runtime (no ROS, no PyTorch): on the Orin, the Python
that has JetPack's ONNX Runtime with the GPU (docs/car-day.md, the diffusion trial). The
first start with TensorRT builds its engine (minutes) into models/diffusion/engines/,
where the node finds it again. The plans: the ones a Gazebo run recorded (--recorded), or
made-up ones on a lot with boxes (the model's time doesn't depend on the map; the
guard's does a little).
"""

import argparse
import glob
import json
import math
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from aav_diffusion_planner import engines, guard, window  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
MODEL = os.path.join(ROOT, 'models', 'diffusion', 'planner.onnx')
# The car's outline padded as the costmap pads it, and 0.95 x full lock (train.py works
# them out from vehicle.yaml; here only for timing, so fixed).
FOOTPRINT = [[1.85, 0.55], [1.85, -0.55], [-0.25, -0.55], [-0.25, 0.55]]
MIN_RADIUS = 2.73


def made_up_plans(n, seed=0):
    """Return n plans (grid, start, goal) on an 80 x 60 m lot with random boxes."""
    rng = np.random.default_rng(seed)
    res = 0.25
    data = np.zeros((240, 320), dtype=np.int8)
    data[:2, :] = data[-2:, :] = 100
    data[:, :2] = data[:, -2:] = 100
    for _ in range(12):
        r, c = rng.integers(10, 220), rng.integers(10, 300)
        data[r:r + rng.integers(4, 24), c:c + rng.integers(4, 24)] = 100
    grid = window.Grid(data, 0.0, 0.0, res)
    plans = []
    while len(plans) < n:
        sx, sy = rng.uniform(5, 75), rng.uniform(5, 55)
        d, a = rng.uniform(5, 40), rng.uniform(-math.pi, math.pi)
        gx, gy = sx + d * math.cos(a), sy + d * math.sin(a)
        if not (3 < gx < 77 and 3 < gy < 57):
            continue
        plans.append((grid, (sx, sy, rng.uniform(-math.pi, math.pi)),
                      (gx, gy, rng.uniform(-math.pi, math.pi)), True))
    return plans


def recorded_plans(folder, n):
    """Return up to n plans the node recorded (diffusion_record:=)."""
    out = []
    for f in sorted(glob.glob(os.path.join(folder, '**', 'plan_*.npz'), recursive=True))[:n]:
        d = np.load(f)
        grid = window.Grid(d['costmap'], float(d['origin'][0]), float(d['origin'][1]),
                           float(d['resolution']))
        out.append((grid, tuple(d['start']), tuple(d['goal']), bool(d['reversing'])))
    return out


def stats(values):
    v = np.sort(np.asarray(values, dtype=np.float64))
    return {'mean': round(float(v.mean()), 1),
            'p95': round(float(v[min(len(v) - 1, int(0.95 * len(v)))]), 1),
            'worst': round(float(v[-1]), 1)}


def measure(model, provider, plans, samples, warmup=3, seed=0):
    """Return the times (ms) of each part over the plans, and the engine that ran."""
    import onnxruntime as ort
    cache = os.path.join(os.path.dirname(os.path.abspath(model)), 'engines')
    os.makedirs(cache, exist_ok=True)
    chain = engines.usable(engines.engines(provider, cache), ort.get_available_providers())
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    t0 = time.perf_counter()
    sess = ort.InferenceSession(model, sess_options=opts, providers=[n for n, _ in chain],
                                provider_options=[o for _, o in chain])
    rng = np.random.default_rng(seed)
    fp = guard.footprint_points(FOOTPRINT)
    times = {'crop': [], 'model': [], 'guard': [], 'total': []}
    first = None
    for i, (grid, start, goal, rev) in enumerate([plans[0]] * warmup + plans):
        t_start = time.perf_counter()
        win = window.window_for(start, goal)
        crop = window.crop(grid, win)
        cond = window.cond(win, start, goal, rev)
        t_crop = time.perf_counter()
        noise = rng.standard_normal((samples, window.POINTS, window.CHANNELS)).astype(
            np.float32)
        out = sess.run(['paths'], {'crop': crop[None, None].astype(np.float32),
                                   'cond': cond[None], 'noise': noise})[0]
        t_model = time.perf_counter()
        if first is None:
            first = 1000.0 * (t_model - t0)     # loading, building, and the first plan
        paths, gears = window.decode_paths(win, out)
        smoothed, again = window.smoothed(paths, gears)
        guard.choose(smoothed, grid, start, goal,
                     guard.Limits(min_radius=MIN_RADIUS, reversing=rev), fp, None, again)
        t_guard = time.perf_counter()
        if i < warmup:
            continue
        times['crop'].append(1000.0 * (t_crop - t_start))
        times['model'].append(1000.0 * (t_model - t_crop))
        times['guard'].append(1000.0 * (t_guard - t_model))
        times['total'].append(1000.0 * (t_guard - t_start))
    return sess.get_providers()[0], first, {k: stats(v) for k, v in times.items()}


def report(result):
    lines = [f"Diffusion planner timing: {result['machine']}",
             f"model {result['model']}, {result['samples']} samples, "
             f"{result['plans']} plans ({result['plans_from']})",
             f"engine asked {result['provider_asked']}, ran on {result['provider_used']}; "
             f"load and first plan {result['first_ms']:.0f} ms", '',
             f"{'part':<8}{'mean':>8}{'p95':>8}{'worst':>8}{'budget':>8}  verdict (p95)"]
    for part, s in result['times'].items():
        budget = engines.BUDGET[part]
        lines.append(f"{part:<8}{s['mean']:>8.1f}{s['p95']:>8.1f}{s['worst']:>8.1f}"
                     f"{budget:>8.0f}  {engines.verdict(s['p95'], budget)}")
    worst = result['times']['total']['worst']
    inside = ('inside it' if worst <= engines.STOP_MS else
              "OVER: those plans would be the lattice's")
    lines += ['', f'hard stop {engines.STOP_MS:.0f} ms: the worst plan {worst:.0f} ms, {inside}']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('--model', default=MODEL, help='the .onnx (planner.onnx, or the '
                        'FP16 one: planner_fp16.onnx)')
    parser.add_argument('--provider', default=engines.CPU, choices=list(engines.CHAINS))
    parser.add_argument('--samples', type=int, default=16)
    parser.add_argument('--plans', type=int, default=50)
    parser.add_argument('--recorded', help="a folder of the node's recorded plans")
    parser.add_argument('--json', help='also write the result here')
    args = parser.parse_args()
    if not os.path.isfile(args.model):
        sys.exit(f'no model at {args.model}: pixi run diffusion train (or copy one here)')
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        sys.exit(f'{sys.executable} has no ONNX Runtime: on a laptop, pixi install --locked '
                 "-e learn; on the Orin, the Python with JetPack's (docs/car-day.md)")
    plans = (recorded_plans(args.recorded, args.plans) if args.recorded
             else made_up_plans(args.plans))
    if not plans:
        sys.exit(f'no recorded plans in {args.recorded}')
    used, first, times = measure(args.model, args.provider, plans, args.samples)
    result = {'machine': f'{platform.node()} ({platform.machine()}, {platform.system()})',
              'model': os.path.abspath(args.model), 'samples': args.samples,
              'plans': len(plans), 'plans_from': args.recorded or 'made up',
              'provider_asked': args.provider, 'provider_used': used,
              'first_ms': round(first, 1), 'times': times,
              'budget_ms': engines.BUDGET, 'stop_ms': engines.STOP_MS}
    print(report(result))
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(result, f, indent=1)
    return 0 if times['total']['p95'] <= engines.BUDGET['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
