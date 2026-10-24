# Getting started

This guide takes a new laptop from nothing to driving the TurtleSim turtle.
Target: under 30 minutes (T1.1). If it takes longer, tell the integration team where you got stuck.

Works on Linux (x86-64) and macOS (Intel or Apple Silicon). No admin rights needed.
You need about 4 GB of free disk space.

## 1. Install Pixi

Pixi installs ROS 2 Jazzy and every other tool into this project's folder,
pinned to the same versions for everyone.

    curl -fsSL https://pixi.sh/install.sh | sh

Close and reopen your terminal, then check:

    pixi --version

## 2. Get the code

You need access to the AAV-2025-2026 GitHub organization. Ask the integration lead if you cannot open
https://github.com/AAV-2025-2026/ecolo-av.

    git clone git@github.com:AAV-2025-2026/ecolo-av.git
    cd ecolo-av

## 3. Install the environment

    pixi install

The first run downloads ROS 2 and the toolchains. Later runs are instant.

## 4. Run the demo

Terminal 1:

    pixi run turtlesim

A window with a turtle opens.

Terminal 2 (in the same `ecolo-av` folder):

    pixi run teleop

Keep terminal 2 focused and press `i`, `j`, `l`, `,` to drive the turtle. `k` stops it. `Ctrl+C` quits.

## 5. Run the tests

    pixi run test

This runs the same checks as CI on every push. All of them should pass.

## Troubleshooting

- **The turtle does not move.** Make sure terminal 2 (teleop) has keyboard focus, not the TurtleSim window.
- **You see other people's turtles or topics.** ROS 2 finds every node on the same network. On shared Wi-Fi,
  run `export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` in both terminals before the `pixi run` commands.
- **`pixi: command not found`.** Reopen the terminal after installing, or add `~/.pixi/bin` to your `PATH`.
