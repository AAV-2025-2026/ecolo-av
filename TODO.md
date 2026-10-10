# TODO (overnight, 2026-10-09 → 10-10)

Ben's asks from tonight, in work order. Tick them off as they land; each tick = a commit.
His messages, word for word: `docs/history/messages-2026-10-09.md`.

## Tonight

- [x] **Build on this machine** with Pixi + RoboStack Jazzy (no admin, no Homebrew).
      `colcon build`, `colcon test`, then run `turtle.launch.py` headless and drive it.
      If something can't build, write down why.
      *Done: all 19 packages build in 11 s; our tests pass; the turtle drives through
      mux → ego; check_graph: 0 failures. Left: lint failures in 3 inherited packages.*
- [ ] **Mac tomorrow.** The same `pixi.toml` for macOS (Apple Silicon). Check that every
      package resolves for `osx-arm64`. Write the steps: no Homebrew.
      *Resolves for `osx-arm64` and `osx-64` (macOS 14+). Steps: `docs/mac.md`. Fixed the
      one known build blocker (B921600 in the IMU driver). Left: Ben tries it on his Mac.*
- [ ] **Port everything to Jazzy as is.** Apply the fixes the audits found (configs,
      inherited code, missing dependencies). Reports: `docs/history/audit-2026-10-10-*.md`.
      - ~~Spine safety, before any firmware is written~~ *Done 10-10: B1 arming always
        sends the 0→1 edge; B2 the spine boots latched; W1 `cmd_timeout` 0.1; W2 driver
        faults stop and latch; W3 `max_decel` 2.5. Each has a test (Rust 47, bridge 4).*
      - Legacy path: steering gain differs left/right (`to_legacy`); `encoder_udp` must go
        quiet, not report 0 m/s, when packets stop; which computer gets the encoder's UDP?
      - pixi.toml: add flask, flask-socketio, scipy, ros-jazzy-topic-tools.
      - Inherited packages: `tests_require` → `extras_require`; yahboom lint; `sudo chmod`
        in TI.py; maincar NameErrors; `.warn(` → `.warning(`; CMake 3.8 → 3.10.
      - The live config check of sim, car and replay didn't finish (usage limit): redo it.
- [ ] **The graph.** Every topic has the right publisher, subscriber, type and QoS.
      Check it live with `tools/check_graph.py` on the turtle run.
- [x] **Docs as HTML (and PDF)**, short pages, sections, red and white, a picture of how
      it fits together. Markdown stays as the source.
      *Done: `docs/html/index.html` and `pixi run docs` (PDF). Four pictures; pages for
      each point below.*
      - What ROS 2 is, and how we extend it (stock modules vs our nodes)
      - How Python, C++ and Rust fit into Jazzy, and what we give up with Rust
      - How the dual EKF works ("local injects, global reads local + GPS")
      - Run it: turtle, keyboard, Gazebo
      - src vs firmware; one interface, several drivers (the IMU example)
- [ ] **Email progress** to cmail, red and white, every few hours and when something lands.
- [x] **Naming and code style** for all code. Inherited code is ours to edit now.
      *Done: `docs/conventions.md`, `pixi run lint` passes. Renaming the inherited
      packages is proposed and waits for the team.*
- [ ] **Rust:** pull `rclrs` and the message crates through cargo. Build one example in
      the Pixi environment. Write down what a Rust rewrite would take (ESP32, Pi).
- [ ] **Design doc:** fix the ten "last year's", and update the tree, profiles and decisions.
- [ ] **CLAUDE.md:** record tonight's decisions, so no session starts from scratch.

## Questions Ben asked (answer in the docs and the morning email)

- Is `aav_turtlesim` different from the regular turtlesim?
- What languages are used now, and should everything be Rust?
- Can it compile on a Mac without Homebrew?
- What does the claude.ai chat (fe09d020…) say? I can't open claude.ai chats, so Ben
  needs to paste the key parts.

## Decided tonight

- Teleop (keyboard, joystick, remote) is a **driver**: it feeds the mux, then ego, then
  the turtle or the car.
- **Bare metal: wait.** Only the spine firmware is bare metal.
- **Port to Jazzy as is first**, then consider rewriting in Rust.
- **Simulator:** start with a Gazebo test world.
- **Docs:** short, sectioned, HTML or PDF. Ben is dyslexic, so use tables and pictures
  over walls of text.

## Later

- Rewrite parts in Rust and cross-compile for the ESP32 and the Pi.
- Measure the car and replace every guessed number in `vehicle.yaml`.
- Rotate the leaked secrets, and back up the Orin and Pis before any reflash.
- Answer Q1–Q34 with the team.
