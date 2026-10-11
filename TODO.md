# TODO (overnight, 2026-10-09 → 10-10)

Ben's asks from tonight, in work order. Tick them off as they land; each tick = a commit.
His messages, word for word: `docs/history/messages-2026-10-09.md`.

## Today on Ben's Mac (10-10)

Ben's messages, word for word: `docs/history/messages-2026-10-10.md`. "Our version" is
`aav/aav` (`~/Code/aav/aav` on the Mac); this work was done in a clone at `~/aav` while that
folder downloaded, and moves into it as a fast-forward.

- [x] **Build and test on the Mac.** *`pixi run test` green after the `coreutils` fix. The
      turtle, Gazebo headless, a Nav2 goal, the Rust listener, the docs, the doctor and
      recording all run. `record.sh` now goes through `tools/ros.sh` (SIP again).*
- [x] **Email everything we talk about, in detail, with sections** (a standing request).
      *Sent at 12:16, 12:32, 12:39, and with the docs PDF.*
- [x] **Docs for a new team member:** first day, starting points, packages, work,
      decisions, infrastructure, build a driver, the costmap exercise, the older code.
      *The driver page and the costmap exercise were run as written, in a scratch copy.*
- [x] **`.gitignore` in `aav/aav`:** restored at 12:35. *The app's per-message snapshots
      were taking in the Linux `.pixi` files as scp copied them.*
- [x] **A `.gitignore` for every kind of code.** *Applied in 593db7f.*
- [x] **A `vendor/` folder** for downloaded source (Ben, 17:03): `vendor/ros2-src.repos`
      (121 repos) and `vendor/ros2-rust.repos` (9), at exact commits, in git; the 559 MB
      out of it. `pixi run vendor` downloads; `tools/test.sh` checks `COLCON_IGNORE`.
- [ ] **Prune the snapshots from `aav/aav/.git`** (149 MB down to about 1 MB)? *Ben to
      decide: it removes the app's undo points.*
- [x] **Move today's commits from `~/aav` into `aav/aav`** once the download finishes.
      *Done 16:13: the scp was still copying the server's Linux build output after six hours,
      so it was stopped and rsync brought the rest. The copy matches the server, Ben's
      uncommitted work is intact, and 55 commits fast-forwarded in. The Linux `.pixi`,
      `install` and Rust `target` went to `~/Code/aav/aav-linux-build-output`, not deleted.
      Built (25 packages, Ben's `aav_imu_yahboom` too) and tested green on the Mac.*
- [x] **Gazebo's window on the Mac:** Ben saw the screenshots (16:34).
- [ ] **Look at RViz and rqt_graph on the Mac**, and say what they show.
- [x] **The firmware requirements in `vendor/`, built out of the box** (Ben, 20:54).
      *A `firmware` environment with PlatformIO; its downloads go in `vendor/platformio/`.
      `pixi run -e firmware legacy-esp32` built today's ESP32 firmware from a clean
      checkout on the Mac (48 s). The tools to flash an ARM chip (`probe-rs`, a UF2
      converter) aren't on conda-forge: they come with the first board program.*
- [x] **CARLA: 4 or 5, and do we need it?** (20:54) *Parked this year: no Jazzy
      support, no Mac version. Gazebo and bench mode cover the car graph (Q31).*
- [ ] **The small fixes** listed at the end of `docs/work.md`.

## This afternoon (10-10): "merge in all of this", then "stub in the rest"

- [x] **Perception in:** `aav_yolo` (YOLO, detections, the stop-sign watcher and its mux
      lock), `aav_object_detection` (radar clustering), `aav_lane_geometry` (lane keeping
      on `/cmd_vel/ai`), the camera calibrations in `cameras.launch.py`, the `ml` environment.
- [x] **The graph down to the sensors:** bench mode (`pixi run bench`): spine_sim runs
      spine-core on the CAN frames and drives a model car; pretend IMU, GPS, camera,
      battery and radar. `pixi run bench-check`: 7 of 7. `gps_nmea.launch.py`,
      `perception.launch.py`, udev placeholders.
- [x] **Rust drivers for the spine's devices:** jrk-g2, ad5311, pca9555, ibus, spine-board
      (98 tests); all seven firmware crates build no_std for the Pico 2 in `pixi run test`.
- [x] **The HUD's back end on our topics:** `aav_hud`, 86 tests.
- [x] **Docs:** Bench mode and Perception pages; every page brought up to date.
- [ ] **Ben: commit the server work** (`aav_imu_yahboom` and its three edited files). Then
      perception and the bench become parts in `car.launch.py`'s machine files.
- [ ] **The board program for the spine's chip** (implements `spine-board`'s `Board`): waits
      on the chip (Q10-Q13).
- [ ] **Team decisions:** the steering on an e-stop; the brake after boot; a brake on the RC
      gear switch (docs/firmware.md).
- [ ] **Find `best.pt`**, the 2024-25 stop-sign model, and the 2025-26 lane finder.
      `best.pt` is probably on the team's Linux machine with the NVIDIA card (Ben, 10 Oct).
      No SSH to it today: later, once all the code is in place (Ben, 21:14).
- [ ] **The HUD app's small changes** (docs/hud.md).
- [ ] **Tune the speed loop on the car:** on the bench it trails a ramp by about a second.
- [x] **The first-day steps in `README.md`** (Ben, 17:03).
- [x] **`~/Code/aav/CLAUDE.md`:** every old folder, and what replaced it in `aav` (Ben, 17:03).
- [x] **An MCP server** (Ben, 17:03): read-only, over stdio. `tools/mcp_server.py`, `.mcp.json`
      and `docs/mcp.md`: 9 tools. Its smoke test reads a live topic.
- [x] **On GitHub** (Ben): `git@github.com:zander1976/aav.git`, private. CI: Linux on every push, a
      Mac every night. Commit messages give the intention, with no attribution lines; the
      README's Credits section covers who did what.
- [x] **Ben's Rust IMU driver** (`aav_imu_yahboom`, `imu_driver:=rust`): reviewed and
      committed; its tests now run in `pixi run test`.
- [x] **Cleaned up** (Ben approved): `~/aav`, the Linux build output and the old bundle.
- [ ] **Slim per-machine Pixi environments** (Orin, Motor Pi, laptop): at Phase 0.
- [ ] **An audit on the car's network** (Ben, 16:42: "at some point"): a read-only audit of
      the hardware. *Ready: the stand-ins stay on their own computer (`tools/ros.sh
      --local`, checked by `tools/test.sh`), so nothing pretend can reach the car.*

## Tonight

- [x] **Build on this machine** with Pixi + RoboStack Jazzy (no admin, no Homebrew).
      `colcon build`, `colcon test`, then run `turtle.launch.py` headless and drive it.
      If something can't build, write down why.
      *Done: all 19 packages build in 11 s; our tests pass; the turtle drives through
      mux → ego; check_graph: 0 failures. The inherited packages' lint failures were
      fixed on 10-10.*
- [x] **Mac tomorrow.** The same `pixi.toml` for macOS (Apple Silicon). Check that every
      package resolves for `osx-arm64`. Write the steps: no Homebrew.
      *Done 10-10 on Ben's Mac (Apple Silicon, macOS 27): build 18 s, `pixi run test` all
      green after one fix (GNU `coreutils`: SIP drops `DYLD_LIBRARY_PATH`). See below.*
- [x] **Port everything to Jazzy as is.** Apply the fixes the audits found (configs,
      inherited code, missing dependencies). Reports: `docs/history/audit-2026-10-10-*.md`.
      - ~~Spine safety, before any firmware is written~~ *Done 10-10: B1 arming always
        sends the 0→1 edge; B2 the spine boots latched; W1 `cmd_timeout` 0.1; W2 driver
        faults stop and latch; W3 `max_decel` 2.5. Each has a test (Rust 47, bridge 4).*
      - ~~Legacy path~~ *Done 10-10: `to_legacy` evens out the steering gain; `encoder_udp`
        goes quiet after 0.3 s without packets; it runs on the Motor Pi, where the
        Pico sends.*
      - ~~pixi.toml deps; inherited packages~~ *Done 10-10: flask, flask-socketio, scipy,
        topic_tools added for all 3 platforms. Radar, battery and IMU code restyled to
        ROS's lint rules and fixed (no `sudo chmod`, udev port names, clean shutdown);
        maincar's NameErrors and start-up fixed; CMake 3.10; `.warning(`. `pixi run test`
        is all green (colcon test: 77, 0 failures).*
      - ~~Live check of sim, car and replay~~ *Done 10-10: every config key is declared
        by its Jazzy node. Fixed: Nav2 on sim time, the sim GPS noise (degrees, not
        metres), a map on the car, steering speed and inflation in the sim, a replay
        profile. Nav2 goals now succeed in Gazebo. Left for the team: see below.*
- [x] **The graph.** Every topic has the right publisher, subscriber, type and QoS.
      Check it live with `tools/check_graph.py` on the turtle run.
      *Done 10-10: turtle, sim and replay have 0 failures. The car, with no hardware,
      fails only on `/imu/data_raw` and `/gps/fix`. No QoS mismatches.*
- [x] **Docs as HTML (and PDF)**, short pages, sections, red and white, a picture of how
      it fits together. Markdown stays as the source.
      *Done: `docs/html/index.html` and `pixi run docs` (PDF). Four pictures; pages for
      each point below.*
      - What ROS 2 is, and how we extend it (stock modules vs our nodes)
      - How Python, C++ and Rust fit into Jazzy, and what we give up with Rust
      - How the dual EKF works ("local injects, global reads local + GPS")
      - Run it: turtle, keyboard, Gazebo
      - src vs firmware; one interface, several drivers (the IMU example)
- [x] **Email progress** to cmail, red and white, every few hours and when something lands.
      *Sent at 22:49, 03:50, 04:07 (the morning summary, with the PDF) and 04:17 (the car
      must run Jazzy before a Mac can join it).*
- [x] **Naming and code style** for all code. Inherited code is ours to edit now.
      *Done: `docs/conventions.md`, `pixi run lint` passes. Renaming the inherited
      packages is proposed and waits for the team.*
- [x] **Rust:** pull `rclrs` and the message crates through cargo. Build one example in
      the Pixi environment. Write down what a Rust rewrite would take (ESP32, Pi).
      *Done: `examples/rust-listener` (rclrs 0.8 + ros-env 0.3 from crates.io; the
      message code ships with Jazzy) builds in 18 s and printed ego's commands live.
      `pixi run rust-listener`. The rewrite trade-offs are in docs/languages.md.*
- [x] **Design doc:** fix the ten "last year's", and update the tree, profiles and decisions.
      *Done 10-10 (doc rev 58): all ten now name 2024-25; the tree, the four profiles,
      the mux priorities, the tests, Gazebo before CARLA; Jazzy, one repo and Languages
      marked Decided; new rows: Macs (Decided), bare metal waits (Tentative), spine
      arming (Proposed).*
- [x] **CLAUDE.md:** record tonight's decisions, so no session starts from scratch.
      *Done: docs for a dyslexic reader, Macs first-class, `pixi run test` green, test
      isolation, the pytest skip trap, Rust nodes later, where the TODO and audits live.*

## Questions Ben asked

*Answered in the morning email and in the docs: `run.md`, `languages.md`, `mac.md`.*

- Is `aav_turtlesim` different from the regular turtlesim?
- What languages are used now, and should everything be Rust?
- Can it compile on a Mac without Homebrew?
- What does the claude.ai chat (fe09d020…) say? It can't be opened from here, so Ben
  needs to paste the key parts.

## For the team to decide

- **`ROS_DOMAIN_ID`** for the car and every laptop (any number 0–101 that no one nearby uses).
- **Spine arming rules** (design doc, Proposed): boot latched, arm on a 0→1 edge.
- **Move the car to Jazzy** before a laptop can join it (Humble and Jazzy don't mix):
  try Pixi on today's Ubuntu 22.04 first, then reflash the Orin to JetPack 7.2 after a
  backup (`docs/platforms.md`).
- **GPS driver** (B4): `ublox_dgnss` isn't in Pixi. Keep it (apt, on the car only), or
  switch to `ublox`, which Pixi has.
- **N2:** twist_mux hears `/estop` best-effort, and the joystick sends it once per press.
  The backends still brake. Send it repeatedly, or make the mux reliable?
- **N3:** no `respawn` on device nodes, and Nav2 gives up without TF. Add respawn?
- **N7:** Nav2's turn command flips sign about once a second in the sim. Try a longer
  lookahead.

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
