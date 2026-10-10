# Working in this repository

The workspace of the 2026-27 Carleton AAV capstone team: one git repo = one colcon
workspace for ROS 2 **Jazzy on Ubuntu 24.04** (Python 3.12), plus the spine firmware.
Read `README.md` first, then `docs/how-it-fits.md` (how the stack fits together) and
`docs/status.md` (what works and what's missing).

These are the conventions decided so far. They apply to people and to Claude sessions alike.

## Where decisions live

- **Design doc** (Claude Doc "AAV 2026–27 Autonomy Stack — Architecture & Plan"): the
  architecture and its decisions (Decided / Tentative / Proposed), the roadmap, and the
  open questions **Q1–Q34**. The team answers by number ("Q12: …").
- **`docs/interfaces.yaml`**: the node-graph contract. Change it first, then run
  `tools/gen_interfaces_md.py > docs/interfaces.md`.
- **`firmware/can/aav.dbc`**: the CAN contract between ROS and the spine. After any change:
  1. update `can_codec.py` and `protocol.rs`;
  2. run `python3 firmware/can/gen_test_vectors.py`;
  3. run both test suites.
- **`src/aav_description/config/vehicle.yaml`**: the only place car measurements live.
- **`docs/history/conversation.md`**: the question-and-answer record of how we got here.
  Add new Q&A under its topic, and keep its "Open threads" list current.

## Rules

- **Names by year.** Write "the 2025-26 team" and "the 2024-25 team", never "last year's".
  Their code is in the GitHub orgs `AAV-2025-2026` and `Carleton-AAV-Capstone`.
- **Inherited code** keeps a `PROVENANCE.md`: where it came from (repo, branch, commit),
  and every change made since. Update it when you change such a file.
- **Secrets** never go in git, logs or docs. Write down only where a secret is and what
  type it is. The legacy firmware reads WiFi credentials from an untracked
  `secrets.h`; copy it from `secrets.h.example`. Old credentials in the inherited repos
  are public and must be rotated (Q34).
- **Units and frames** follow REP-103 and REP-105:
  - metres, radians and seconds;
  - x forward, y left, z up, positive steering = left;
  - `map → odom → base_link`, with `base_link` on the ground under the rear axle.
- **Commands:** drivers publish `TwistStamped` on `/cmd_vel/<driver>`. Ackermann appears
  only after ego (`/ego/actuator_cmd`). Exactly one backend runs at a time.
- **Prefer stock packages**:
  1. stock ROS packages (robot_localization, Nav2, twist_mux, teleop_twist_*);
  2. then code inherited from the previous teams;
  3. then a reasonable stub.
- **Languages:**
  - Python (rclpy) for every ROS node we write;
  - Rust (`no_std`) for the spine firmware;
  - C++ only for the reused IMU driver.
- **Keep the maths out of ROS.** A node's logic lives in a module with no ROS imports
  and has its own tests. Examples: `ackermann.py`, `can_codec.py`, `profile.py`,
  `legacy_protocol.py` and `vehicle.py`; in Rust, `spine-core`.
- **Each node's module docstring** lists what it subscribes, publishes, serves and calls.
- **Pins, I2C addresses and calibration belong in the firmware.** ROS never sees a pin.

## Testing

- `tools/test.sh` runs everything that doesn't need ROS: the Python unit tests, the
  `cargo test` for `firmware/spine`, and the interfaces.md check. Run it before every
  commit.
- With Jazzy, also run `pixi run build`, `pixi run test` (which adds `colcon test`), and
  `tools/check_graph.py --profile turtle|sim|car` against a running system.
- Pixi + RoboStack provide Jazzy without admin rights: on Ben's AlmaLinux workstation
  (oirp-spss), on Macs, and on any Linux. `pixi.toml` and `pixi.lock` define the
  environment; `pixi run <task>` runs a command inside it. That machine has no screen
  for GUIs: run headless there (`QT_QPA_PLATFORM=offscreen`, `gui:=false`).
- Say what you actually ran. A profile that hasn't been launched is "untested", not
  "works".

## Git

- `main` is local only. There is no GitHub org for 2026-27 yet (Q25), and the previous
  orgs are public, so don't push anywhere without the team's say-so.
- Commit in small steps that each pass `tools/test.sh`. Don't commit build output: no
  `build/`, `install/`, `log/` or `target/`.

## Not ours

These sit in `/home/ben/aav/` next to this repo and are not team code:
- **Read-only clones of the 2025-26 repos:** survey them with
  `grep -r --exclude-dir=ros2-src --exclude-dir=ros2-rust`.
- **`ros2-src/`:** the Jazzy source, for looking things up.
- **`ros2-rust/`:** the rclrs project.
- **Ben's own course code:** `SYSC3313/`, `c_code_example/` and `simplied.c`.
