#!/usr/bin/env python3
"""
The car's linear model: print its poles, step responses and margins, and draw them.

    pixi run vehicle-model                      today's numbers (vehicle.yaml)
    pixi run vehicle-model --set throttle_lag=0.25 --set steer_lag=0.15
                                                the car day's numbers, from the actuator tests
    pixi run vehicle-model --no-figures         the tables only

The maths: src/ego/aav_ego/aav_ego/vehicle_model.py. The page: docs/vehicle-model.md.
The figures go to docs/img/vehicle-model-*.png, drawn with matplotlib (in Pixi's default
environment, through ROS's rqt); without it, the tables only. No ROS needed.
"""

import argparse
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'ego' / 'aav_ego'))

from aav_ego import vehicle_model as vm  # noqa: E402
import numpy as np  # noqa: E402

VEHICLE_YAML = ROOT / 'src/aav_description/config/vehicle.yaml'
GAZEBO_XACRO = ROOT / 'src/aav_description/urdf/aav.gazebo.xacro'
IMG = ROOT / 'docs' / 'img'


def table(title, rows):
    """Return a table as aligned text."""
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    line = '  '.join('-' * w for w in widths)
    out = [title, line]
    for n, r in enumerate(rows):
        out.append('  '.join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        if n == 0:
            out.append(line)
    return '\n'.join(out)


def gazebo_steer_gain(path=GAZEBO_XACRO):
    """Gazebo's AckermannSteering steer_p_gain: its joints turn at gain x error (1/s)."""
    found = re.search(r'<steer_p_gain>([\d.]+)</steer_p_gain>', Path(path).read_text())
    return float(found.group(1)) if found else 1.0      # gz-sim's own default


def gazebo_rows(model):
    """Gazebo's car against the model: its steering has one more lag, 1 / steer_p_gain."""
    gain = gazebo_steer_gain()
    extra = 1.0 / gain
    rows = [['v m/s', 'the car (model)', f'Gazebo (+{extra * 1000:.0f} ms lag)',
             'the car: delay left', 'Gazebo: delay left']]
    for v in vm.lateral_speeds():
        ol = model.lateral_open_loop(v)
        gz = vm.series(ol, (np.array([1.0]), np.array([extra, 1.0])))
        T = model.delays.lateral('typical')
        a, b = vm.margins(ol, T), vm.margins(gz, T)
        rows.append([f'{v:g}', f'PM {a.phase_margin_deg:.0f} deg',
                     f'PM {b.phase_margin_deg:.0f} deg',
                     f'{a.max_delay * 1000:.0f} ms', f'{b.max_delay * 1000:.0f} ms'])
    return gain, rows


def figures(model, out_dir):
    """Draw the step responses, the Bode plots and the pole map. Return the files."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.size': 11, 'axes.grid': True, 'grid.alpha': 0.3,
                         'axes.spines.top': False, 'axes.spines.right': False})
    blue, orange, grey, green = '#2a6fb0', '#d9822b', '#7a7a7a', '#3a9a5b'
    files = []

    # 1. Step responses: the speed loop, the steering, the lateral recovery.
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    ax = axes[0]
    t, y = vm.step(model.speed_closed_loop(), t_end=25.0)
    ax.plot(t, y, color=blue, label="spine's PI + throttle lag")
    t2, y2 = vm.step(model.speed_closed_loop(vm.SpeedLoopGains(kp=0.3, ki=0.0)), t_end=25.0)
    ax.plot(t2, y2, color=orange, ls='--', label='P only (ki = 0)')
    ax.axhline(1.0, color=grey, lw=0.8)
    ax.set(title='Speed: a 1 m/s step in the set speed', xlabel='s', ylabel='m/s')
    ax.legend(frameon=False, fontsize=9)
    ax = axes[1]
    t, y = vm.step(model.steer_tf(), t_end=0.8)
    ax.plot(t, model.steer_step * y, color=blue, label='second-order model')
    ramp = np.minimum(t * model.steer_rate, model.steer_step)
    lag = np.zeros_like(t)
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        lag[i] = lag[i - 1] + (ramp[i] - lag[i - 1]) * (1 - math.exp(-dt / model.steer_lag))
    ax.plot(t, lag, color=orange, ls='--', label='rate limit, then lag')
    ax.set(title=f'Steering: a {model.steer_step:g} rad step', xlabel='s', ylabel='rad')
    ax.legend(frameon=False, fontsize=9)
    ax = axes[2]
    for v, c in ((0.5, orange), (1.0, blue), (3.0, green)):
        acl = model.lateral_closed_loop(v)
        ts = np.linspace(0, 12, 1201)
        x0 = np.array([0.5, 0.0, 0.0])
        ys = [(np.real(_expm(acl * tt) @ x0))[0] for tt in ts]
        ax.plot(ts, ys, color=c, label=f'{v:g} m/s')
    ax.axhline(0.0, color=grey, lw=0.8)
    ax.set(title='Lateral: 0.5 m off the path, pure pursuit', xlabel='s',
           ylabel='lateral error, m')
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    files.append(save(fig, out_dir / 'vehicle-model-steps.png'))

    # 2. Bode: the speed loop and the lateral loop at 1 m/s, with and without the delays.
    w = np.logspace(-2, 2, 2000)
    fig, axes = plt.subplots(2, 2, figsize=(12, 6), sharex='col')
    loops = (('Speed loop L(s)', model.speed_open_loop(),
              lambda c: model.delays.speed(c, model.gains.tick)),
             ('Lateral loop L(s), 1 m/s', model.lateral_open_loop(1.0), model.delays.lateral))
    for col, (title, ol, delay) in enumerate(loops):
        for case, c, ls in (('none', blue, '-'), ('worst', orange, '--')):
            T = delay(case)
            mag, ph = vm.freq_response(ol, w, T)
            m = vm.margins(ol, T)
            axes[0, col].semilogx(w, 20 * np.log10(mag), color=c, ls=ls,
                                  label=f'delay {T * 1000:.0f} ms')
            axes[1, col].semilogx(w, ph, color=c, ls=ls,
                                  label=f'PM {m.phase_margin_deg:.0f} deg')
            axes[1, col].plot([m.gain_crossover], [m.phase_margin_deg - 180], 'o', color=c)
        axes[0, col].axhline(0, color=grey, lw=0.8)
        axes[1, col].axhline(-180, color=grey, lw=0.8)
        axes[0, col].set(title=title, ylabel='gain, dB')
        axes[1, col].set(xlabel='rad/s', ylabel='phase, deg', ylim=(-360, 0))
        axes[0, col].legend(frameon=False, fontsize=9)
        axes[1, col].legend(frameon=False, fontsize=9)
    fig.tight_layout()
    files.append(save(fig, out_dir / 'vehicle-model-bode.png'))

    # 3. Pole map: the speed loop, the steering, the lateral loop at each speed.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    ax = axes[0]
    sp = vm.poles(model.speed_closed_loop())
    ax.plot(sp.real, sp.imag, 'x', color=blue, ms=9, mew=2, label='speed loop (spine PI)')
    st = vm.poles(model.steer_tf())
    ax.plot(st.real, st.imag, 'x', color=green, ms=9, mew=2, label='steering')
    for v, c in ((0.5, orange), (1.0, blue), (3.0, green)):
        p = np.linalg.eigvals(model.lateral_closed_loop(v))
        ax.plot(p.real, p.imag, 'o', mfc='none', color=c, ms=8, label=f'lateral, {v:g} m/s')
    ax.axvline(0, color=grey, lw=0.8)
    ax.set(title='Closed-loop poles (s-plane)', xlabel='real, 1/s', ylabel='imaginary, rad/s')
    ax.legend(frameon=False, fontsize=8, loc='upper left')
    ax = axes[1]
    ax.plot(sp.real, sp.imag, 'x', color=blue, ms=9, mew=2)
    for v, c in ((0.5, orange), (1.0, blue), (3.0, green)):
        p = np.linalg.eigvals(model.lateral_closed_loop(v))
        ax.plot(p.real, p.imag, 'o', mfc='none', color=c, ms=8)
    ax.axvline(0, color=grey, lw=0.8)
    ax.set(title='Zoomed in: the slow poles', xlabel='real, 1/s', xlim=(-1.2, 0.1),
           ylim=(-1.1, 1.1))
    fig.tight_layout()
    files.append(save(fig, out_dir / 'vehicle-model-poles.png'))
    plt.close('all')
    return files


def _expm(a):
    from scipy.linalg import expm
    return expm(a)


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # No date in the file: the same numbers draw the same picture.
    fig.savefig(path, dpi=110, metadata={'Software': None, 'Creation Time': None})
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[1].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vehicle', default=str(VEHICLE_YAML), help='vehicle.yaml to read')
    ap.add_argument('--set', action='append', default=[], metavar='KEY=VALUE',
                    help='a measured number: throttle_lag=0.25, actuators.steer_lag=0.15, '
                         'steer_overshoot=0.1 (repeat it)')
    ap.add_argument('--no-figures', action='store_true', help='print the tables only')
    ap.add_argument('--out', default=str(IMG), help='where the figures go')
    args = ap.parse_args(argv)

    measured = {}
    for item in args.set:
        key, _, value = item.partition('=')
        measured[key.strip()] = float(value)
    model = vm.from_vehicle_yaml(args.vehicle).with_measured(measured)
    print(f"The car's linear model, from {Path(args.vehicle).name}"
          + (f' with {", ".join(args.set)}' if args.set else ' (every actuator number a GUESS)'))
    print()
    for title, rows in vm.summary(model):
        print(table(title, rows))
        print()
    gain, rows = gazebo_rows(model)
    print(table(f"Gazebo's car: steer_p_gain {gain:g} adds a {1000 / gain:.0f} ms lag after "
                'the actuator model (typical delays)', rows))
    print()
    if args.no_figures:
        return 0
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print('no matplotlib here: the tables only (pixi run vehicle-model has it)')
        return 0
    for f in figures(model, Path(args.out)):
        print(f'wrote {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
