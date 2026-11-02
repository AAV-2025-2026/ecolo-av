#!/usr/bin/env python3
"""
Draw the pictures for docs/whats-new.md.

Three diagrams (Graphviz) and five charts (matplotlib), into docs/img/whats-new-*.svg
and *.png.

    pixi run python3 tools/whats_new_figures.py

Every number is a Gazebo result already written in docs/trials.md (the run named beside
each chart there); change it there first, then here. Light mode only: the page is printed.
"""

from pathlib import Path
import subprocess

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / 'docs' / 'img'

# The validated reference palette (light mode): slot 1 for "ours / the pick", a recessive
# grey for the rest, ink for text. One series per chart, so no legend is needed.
PICK = '#2a78d6'
OTHER = '#b5b3ad'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e2dc'
SURFACE = '#fcfcfb'

# --- diagrams ------------------------------------------------------------------------

STYLE = ('graph [fontname="Helvetica", bgcolor="transparent", rankdir=LR, nodesep=0.35, '
         'ranksep=0.5, pad=0.2];\n'
         'node [fontname="Helvetica", fontsize=13, shape=box, style="rounded,filled", '
         'color="#c9c7c0", fillcolor="#f4f3ef", fontcolor="#0b0b0b", margin="0.18,0.10"];\n'
         'edge [color="#7a7873", arrowsize=0.7, fontname="Helvetica", fontsize=11, '
         'fontcolor="#52514e"];\n')
NEW = 'fillcolor="#dcebfb", color="#2a78d6"'     # built in the last few pull requests

DIAGRAMS = {
    'whats-new-stack': """
  rankdir=TB;
  sensors [label="Sensors\\nlidar, GPS, IMU,\\nwheels, cameras, radar"];
  loc [label="Localization\\nEKFs, NDT, KISS-ICP", %(new)s];
  per [label="Perception\\nRF-DETR, lanes,\\nscan or cubes", %(new)s];
  nav [label="Navigation\\nplanners, followers", %(new)s];
  ego [label="ego\\nthe car's limits"];
  car [label="The car\\nspine, ESP32"];
  sensors -> loc -> nav; sensors -> per -> nav; nav -> ego -> car;
  screens [label="Screens\\nhardware panel,\\ndebug screen", %(new)s];
  lang [label="Language\\nQwen, MCP, Claude", %(new)s];
  screens -> ego [style=dashed, label="buttons"]; lang -> nav [style=dashed, label="goals"];
""",
    'whats-new-localization': """
  cloud [label="Lidar\\npoint cloud"];
  gps [label="GPS +\\nGPS heading"];
  wheels [label="Wheels + IMU"];
  ndt [label="NDT\\nmatch to a saved map", %(new)s];
  kiss [label="KISS-ICP\\nhow far it moved", %(new)s];
  local [label="EKF local\\nodom -> base_link"];
  global [label="EKF global\\nmap -> odom"];
  health [label="Health checks\\n(warn only)", %(new)s];
  cloud -> ndt; ndt -> global [label="ndt_ekf"];
  cloud -> kiss; kiss -> local [label="kiss_ekf"];
  gps -> global; wheels -> local; wheels -> global;
  local -> health [style=dashed]; global -> health [style=dashed];
""",
    'whats-new-language': """
  rankdir=TB;
  you [label="You\\n\\"drive 10 m forward\\""];
  qwen [label="talk\\nQwen 3 (4B), on the laptop\\nour ReAct harness", %(new)s];
  claude [label="Claude Code"];
  drive [label="Drive server (MCP)\\nhard limits", %(new)s];
  read [label="Read-only server (MCP)\\ndocs, contract, graph", %(new)s];
  car [label="The car's actions\\ndrive, turn, go to GPS, stop"];
  you -> qwen; qwen -> drive [label="asks yes first"]; claude -> drive; claude -> read;
  drive -> car;
""",
}


def diagram(name, body):
    """Render one diagram to SVG with Graphviz's dot."""
    source = 'digraph G {\n' + STYLE + body % {'new': NEW} + '}\n'
    out = IMG / f'{name}.svg'
    subprocess.run(['dot', '-Tsvg', '-o', str(out)], input=source.encode(), check=True)
    return out


# --- charts --------------------------------------------------------------------------

def bars(name, title, rows, unit, note, best='low', fmt='{:g}'):
    """
    Draw a horizontal bar chart, one series: rows = [(label, value, is_pick)].

    best: 'low' or 'high', said under the title so the reader knows which way is good.
    """
    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(rows) + 1.3), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    labels = [r[0] for r in rows][::-1]
    values = [r[1] for r in rows][::-1]
    colours = [PICK if r[2] else OTHER for r in rows][::-1]
    ax.barh(labels, values, color=colours, height=0.56, edgecolor=SURFACE, linewidth=2)
    top = max(values)
    for y, v in enumerate(values):
        ax.text(v + top * 0.015, y, fmt.format(v) + f' {unit}', va='center',
                fontsize=10, color=INK)
    ax.set_xlim(0, top * 1.22)
    ax.set_xticks([])
    for side in ('top', 'right', 'bottom'):
        ax.spines[side].set_visible(False)
    ax.spines['left'].set_color(GRID)
    ax.tick_params(axis='y', length=0, labelsize=10.5, labelcolor=INK)
    word = 'lower is better' if best == 'low' else 'higher is better'
    ax.set_title(f'{title}  ({word})', loc='left', fontsize=12, color=INK, pad=10)
    fig.text(0.01, 0.01, note, fontsize=8.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out = IMG / f'{name}.png'
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


CHARTS = [
    ('whats-new-planners', 'The lot tour, by planner, with reversing', [
        ('State Lattice (the default)', 184, True),
        ('Lattice, 32 headings', 197, False),
        ('Hybrid-A*', 213, False),
    ], 's', 'Gazebo, 30 Oct, MPPI; mean of 4 runs (lattice32: 3). '
            'Every planner finished every leg.', 'low'),
    ('whats-new-followers', 'Legs finished of 12, forward only', [
        ('Pure pursuit', 12, False),
        ('Stanley', 12, False),
        ('MPC', 12, False),
        ('RPP (Nav2)', 10, False),
        ('MPPI (Nav2, the default)', 8, True),
        ('LQR', 8, False),
    ], '', "Gazebo's lot, 29 Oct, 3 runs of 4 legs each. The U-turn decided it. "
           'MPPI stays the default: it reads the costmap.', 'high'),
    ('whats-new-ndt', 'How far EKF global is from the truth', [
        ('GPS only', 17, False),
        ('GPS + NDT (ndt_ekf)', 1.6, True),
        ('GPS off, no NDT', 120, False),
        ('GPS off + NDT', 1.6, True),
    ], 'cm', "Gazebo's lot tour, 30 Oct.", 'low'),
    ('whats-new-odometry', 'Drift per 100 m driven, no GPS', [
        ('Wheels + IMU (EKF local)', 0.33, False),
        ('KISS-ICP (lidar)', 0.04, True),
    ], 'm', "Gazebo's lot tour, 30 Oct. Gazebo's wheels barely slip: the car's will.", 'low'),
    ('whats-new-detector', 'A stop sign first found at', [
        ('RF-DETR Nano (ours)', 20, True),
        ('YOLO11n', 10, False),
    ], 'm', 'Gazebo road world, 20 Oct. RF-DETR: Apache-2.0, no false finds.', 'high'),
]


def main():
    for name, body in DIAGRAMS.items():
        print('wrote', diagram(name, body).relative_to(ROOT))
    for name, title, rows, unit, note, best in CHARTS:
        print('wrote', bars(name, title, rows, unit, note, best).relative_to(ROOT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
