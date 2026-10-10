# AAV 2026–27 autonomy stack

The ROS 2 workspace and spine firmware for Carleton's autonomous vehicle capstone, built
by the 2026–27 team. Target: **ROS 2 Jazzy on Ubuntu 24.04** on the car's computers (the
Jetson AGX Orin and the Raspberry Pis); Pixi on Macs and other Linux machines.

**Sensors become telemetry, drivers become one command, and ego moves the car.**

## Read the docs

Open **`docs/html/index.html`** in a browser: short pages with pictures. There's also a
single PDF, built by `pixi run docs` into `docs/html/aav-docs.pdf`.

The pages are made from the markdown in `docs/`. Edit those, then run `pixi run docs`.

## Quick start (Mac or Linux)

```bash
curl -fsSL https://pixi.sh/install.sh | sh    # once; then open a new terminal
pixi install                                  # ROS 2 Jazzy and every dependency
pixi run build                                # our packages
pixi run turtle                               # terminal 1: a turtle that steers like the car
pixi run keyboard                             # terminal 2: hold i to drive, u or o to turn
```

Details, and what to do when it fails: [docs/run.md](docs/run.md).

## What's where

| Folder | What's in it |
|---|---|
| `src/` | ROS 2 packages, one folder per layer: sensors, localization, drivers, mux, ego, backends, plus the interfaces, the car description and the launch profiles |
| `firmware/` | the CAN contract (`can/aav.dbc`), the Rust `spine-core`, and the inherited C++ firmware |
| `tools/` | tests, keyboard, graph check, recording, the docs builder, the progress mailer |
| `docs/` | the docs (markdown sources, the HTML in `docs/html/`), the topic contract, and the history |
| `hud/` | the 2025-26 touchscreen app, not yet ported |

## Status

Everything builds on Jazzy, our tests pass, and the keyboard drives the turtle through
the mux and ego. What works, what's untested and what's missing:
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
