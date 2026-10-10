# AAV 2026–27 autonomy stack

The ROS 2 workspace and spine firmware for Carleton's autonomous vehicle capstone, built
by the 2026–27 team. Target: **ROS 2 Jazzy on Ubuntu 24.04** on the car's computers (the
Jetson AGX Orin and the Raspberry Pis); Pixi on Macs and other Linux machines.

**Sensors become telemetry, drivers become one command, and ego moves the car.**

## Read the docs

Open **`docs/html/index.html`** in a browser: short pages with pictures. There's also a
single PDF, built by `pixi run docs` into `docs/html/aav-docs.pdf`.

The pages are made from the markdown in `docs/`. Edit those, then run `pixi run docs`.

## Your first day

New to the team? Do these in order, on a Mac or on Linux.
[Your first day](docs/first-day.md) walks through each step, with what you should see.

| # | Do this | How long |
|---|---|---|
| 1 | Mac only: `xcode-select --install` | a few minutes, once |
| 2 | Install Pixi: the `curl` line below, then open a new terminal | under a minute, once |
| 3 | Get the code: `git clone` from GitHub, or from `aav.bundle` until the team has a GitHub org | seconds |
| 4 | `pixi install` | the first time, a few minutes: it downloads about 4 GB |
| 5 | `pixi run build`, then `pixi run test` | a few minutes the first time |
| 6 | `pixi run turtle`, or `pixi run sim` | ready |

The same steps, as commands:

```bash
xcode-select --install                        # 1. Mac only: Apple's git and compiler
curl -fsSL https://pixi.sh/install.sh | sh    # 2. Pixi; then open a new terminal
git clone ~/aav.bundle ~/aav && cd ~/aav      # 3. the code (or git clone from GitHub)
pixi install                                  # 4. ROS 2 Jazzy and every dependency
pixi run build && pixi run test               # 5. our packages, then every test
pixi run turtle                               # 6. terminal 1: a turtle that steers like the car
pixi run keyboard                             #    terminal 2: hold i to drive, u or o to turn
```

When something fails: [docs/run.md](docs/run.md).

## What's where

| Folder | What's in it |
|---|---|
| `src/` | ROS 2 packages, one folder per layer: sensors, localization, drivers, mux, ego, backends, plus the interfaces, the car description and the launch profiles |
| `firmware/` | the CAN contract (`can/aav.dbc`), the spine's Rust logic and device drivers (`spine/`), and the inherited C++ firmware (`legacy/`) |
| `tools/` | tests, keyboard, graph check, the network doctor, recording, the docs builder, the progress mailer |
| `examples/` | small runnable examples: a first ROS node in Rust (`rust-listener`) |
| `docs/` | the docs (markdown sources, the HTML in `docs/html/`), the topic contract, and the history |
| `hud/` | the 2025-26 touchscreen app. Its back end is ported, as `src/hud/aav_hud` |
| `models/` | the YOLO models, downloaded by `pixi run get-models` (not in git) |
| `vendor/` | the ROS 2 and ros2-rust source, for looking things up. Not ours, and not in git: `pixi run vendor` downloads it |

## Status

Everything builds on Jazzy, on Linux and on Macs, and every test passes. The turtle,
Gazebo and bench mode (the whole car's software, with stand-ins for the hardware) all
run. Nothing has run on the car yet. What works, what's untested and what's missing:
[docs/status.md](docs/status.md).

Decisions and open questions (**Q1–Q34**) are in the team design doc, *AAV 2026–27
Autonomy Stack — Architecture & Plan* (a Claude Doc). Conventions are in
[CLAUDE.md](CLAUDE.md).

## Where the code came from

New code was written for this design. Code reused from the 2025-26 team (GitHub org
`AAV-2025-2026`) and the 2024-25 team (`Carleton-AAV-Capstone`) carries a
`PROVENANCE.md`: the source repository, branch and commit, plus every change since.
Credentials committed to those public repositories were not copied. They still need to
be rotated (Q34).
