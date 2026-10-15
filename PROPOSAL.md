# The proposal: what we plan to do this year, and what's already done

Written 15 October 2026, for Ben and the team (Ben: "a file called proposal that lists
everything we have talked about that we think we can get working"). This is the **draft**
for the written proposal: every part of the car, what's built, what's left, and how sure
we are. Details live in the pages linked from each row.

> **The short version**
> - **The goal:** the 2025-26 car drives itself from one GPS point to another, safely, with a person watching on two screens.
> - **Already built and tested in simulation:** the whole software stack on ROS 2 Jazzy. Sensors, position (EKFs), Nav2, ego, the safety path, perception, two screens, plain-English driving. Linux and Mac.
> - **Not yet done:** almost everything **on the real car**. Measuring it, the sensors it's missing for closed-loop control, the Jetson upgrade, and real drives.
> - **Status words:** ✅ done and tested · 🧪 built, tested only in simulation or on the bench · 🔧 to build, confident · 🎯 stretch goal.

## 1. The system, in one picture

```text
 SENSORS             POSITION            DECIDE                 ACT                    CAR
 GPS, IMU,      →   EKF local    →   Nav2 (paths,     →   twist_mux → ego    →   spine (CAN) → throttle,
 wheel speed,       EKF global       obstacles)            (one command,          steering, brake
 cameras, radar,    navsat           drivers: keyboard,     Ackermann,            e-stop always wins
 lidar                               joystick, plain        speed limits)
                                     English, search box
        └──────────── everything also runs in Gazebo (the full car) and on a bench ────────────┘
 SCREENS: the instrument cluster (small) · the map with Ottawa streets and search (big) · Lichtblick
```

## 2. What's done, by part

| Part | What we have | Status | Read |
|---|---|---|---|
| **The graph** | one contract for every topic and node (`docs/interfaces.yaml`), checked against the running system; topic names by area (`/sensors/`, `/vehicle/`, `/safety/`...) | ✅ | [interfaces](docs/interfaces.md), [naming](docs/naming.md) |
| **Car model** | the car's shape, sensors and frames from one file (`vehicle.yaml`); zero point under the rear axle | ✅ the numbers are **guesses** until measured | [measure the car](READ-ME-MEASURE-THE-CAR.md) |
| **Ackermann** | the steering maths (speed + turn → wheel angle), with its own tests | ✅ | [conventions](docs/conventions.md) |
| **ego** | turns every driver's command into one Ackermann command, with speed caps (1 m/s on the car; faster only in sim) | ✅ | |
| **twist_mux** | picks which driver is in charge (joystick > keyboard > Nav2...) and stops stale ones | ✅ | |
| **EKFs** | robot_localization: local (wheels + IMU) and global (+ GPS) | 🧪 sim: within 0.15 m of the truth; replay: 0.03 m | [maps and position](READ-ME-MAPS-AND-POSITION.md) |
| **Maps** | Nav2 maps for an empty world and a test lot; GPS datum ties them to the real world | 🧪 | |
| **Nav2** | paths, obstacles (radar, camera), collision monitor that stops the car | 🧪 sim: goals reached, stops 0.44 m before a box | |
| **Simulation** | Gazebo: the whole car, 3 cameras, radar, lidar, GPS, IMU, wheel speed, an actuator model, a SIMULATED banner; one command opens everything | 🧪 | [full simulation](READ-ME-FULL-SIMULATION.md) |
| **Bench** | the real CAN messages, the spine's logic and both e-stops, without the car | ✅ `bench-check` | |
| **Perception** | YOLO11 (stop signs and objects), lane keeping, radar clustering (Rust) | 🧪 bench and sim | [perception](READ-ME-PERCEPTION-AND-HUD-MAP.md) |
| **Core ML and TensorRT** | the same YOLO model exported for the Mac (Core ML) and the Jetson Orin (TensorRT, built on the Orin) | 🧪 Mac done; Orin after its upgrade | [perception](docs/perception.md) |
| **Instrument cluster (small screen)** | raylib HUD in Rust: speed, mode, gear, e-stop button, camera, GPS, topic health; full screen on its own monitor at boot (ready to install) | 🧪 | [HUD](docs/hud.md), [two screens](docs/car-screens.md) |
| **Map (big screen)** | Nav2's map over offline Ottawa streets (OpenStreetMap), the car, the path, distance and time left; **search a place and send the car there**; full screen at boot, like the HUD | 🧪 | [HUD](docs/hud.md), [two screens](docs/car-screens.md) |
| **Plain-English driving** | a local language model (Qwen3, on the Mac with MLX) plans "drive 10 m forward"; you type yes | 🧪 sim: drove 10.02 m | [plain English](docs/plain-english.md) |
| **Rust port** | firmware in Rust: the spine (on today's ESP32 control board too, over its UART or CAN), the wheel encoder, the status display, the CAN wheel nodes' logic; the IMU driver and radar clustering in Rust | 🧪 321 tests in `firmware/spine`; builds for the Pico 2 and the ESP32; never flashed | [Rust firmware](docs/rust-firmware.md) |
| **Linux and Mac** | one `pixi.toml`: the same commands on Ubuntu, AlmaLinux and macOS, no admin rights; nightly Mac CI | ✅ | [Mac](docs/mac.md) |
| **Watching** | Lichtblick / Foxglove, RViz, recording and replaying drives | ✅ | |
| **Testing** | unit tests (Python, Rust), graph checks, `sim-check`, `bench-check`, CI on every push | ✅ | [tests](READ-ME-TESTS.md) |
| **The car audit** | tools to map the car's network and survey every computer, read-only | ✅ ready for 16 Oct | [Friday](FRIDAY-TODO.md) |

## 3. What's left, and how sure we are

| # | Work | Why | Needs the car? | How sure |
|---|---|---|---|---|
| 1 | **The audit**: every computer, what runs, what's plugged in, what exists only there (the stop-sign model, `best.pt`) | we can't plan the car without it | yes | 🔧 16 Oct |
| 2 | **Measure the car**: sensor positions, wheelbase, steering angles, weight (scales) | the model, Nav2 and the sim all use these | yes | 🔧 |
| 3 | **Back up and upgrade the Jetson Orin** to a current JetPack, then ROS 2 Jazzy on every car computer | one ROS version everywhere; TensorRT for YOLO | yes | 🔧 |
| 4 | **The missing sensors for closed loop** (below) | today the car is driven **open loop**: we send commands but can't see what the actuators did | yes | 🔧 |
| 5 | **The safety timeout** in the actuator board: brake if commands stop | today a lost cable keeps the car going | yes | 🔧 must come first |
| 6 | **Actuator tests**: speed up, brake, steering sweep, circles; numbers into the sim. The script is built and proven in Gazebo (15 Oct: `pixi run actuator-test`) | the sim behaves like the real car; the car knows how hard it can brake | yes | 🔧 |
| 7 | **GPS-to-GPS movement**: from A to B by GPS in an empty lot, with a smooth stop at B | the main goal | yes | 🔧 |
| 8 | **The spine in the loop** in Gazebo, sensor failures on purpose, the lidar into Nav2 | test the safety logic without the car | no | 🔧 |
| 9 | **The real lidar driver** (likely a Velodyne) and the real cameras into perception | more of the world seen | yes | 🔧 |
| 10 | **Newer models**: YOLO26 or RF-DETR for perception; Qwen3.5, Gemma 4 or Granite for plain English, on the Orin too | better and freer models since 2024 | no | 🔧 test, then pick |
| 11 | **Touchscreen keyboard** for the map's search | type a destination in the car | no | 🔧 |
| 12 | **OSRM road routes**: follow real streets, not just a lot | driving beyond a parking lot | yes | 🎯 |
| 13 | **Flash the Rust firmware** on the real boards, replacing the 2025-26 C++ | one language, tested logic | yes | 🎯 board by board |
| 14 | **A Gazebo copy of the real test lot** | practise the exact drive at home | no | 🎯 |

### The missing sensors for closed loop

| Actuator | We command it | We need to read back | Plan |
|---|---|---|---|
| **Steering** | yes | the real wheel angle | the Jrk motor controller already reports its position (the 2024-25 firmware read it); wire it into `/vehicle/steering` |
| **Throttle** | yes | wheel speed: is it moving as asked? | the wheel encoder exists (one wheel); check it's reliable. Or a Hall sensor on each front wheel (the KEFC plan): CAN v0.2.0 and `spine_bridge` already read them into `/vehicle/wheels` and `/vehicle/odom` (bench, 15 Oct) |
| **Brake** | yes | brake position or pressure | a position sensor on the brake actuator: to choose after the audit |
| **E-stop** | the red button | its state | the spine reads it; never in its path |

The topics for all four already exist (`/vehicle/steering`, `/throttle`, `/brake`, `/wheels`); the simulator fills them today, and the bench fills `/wheels` from the CAN wheel frames.

## 4. The order

```text
 Oct: audit · measure · safety timeout     Nov: Jetson upgrade · Jazzy on the car · actuator tests
        │                                         │
        ▼                                         ▼
 Dec: closed-loop sensors · real numbers into the sim · drives on stands
        │
        ▼
 Winter: empty-lot drives · GPS A to B · smooth stop      Stretch: OSRM streets · Rust firmware on the car
```

| Phase | Done when |
|---|---|
| 1. Know the car | the audit is written up; every measurement is in `vehicle.yaml` |
| 2. Safe to move | the timeout works (test 3.9); both e-stops stop the car |
| 3. Closed loop | steering, speed and brake read back, and match the commands |
| 4. Drives itself | A to B by GPS in an empty lot, stopping within 1 m of B, with a safety driver |

The tests for each step, in order: [READ-ME-TESTS.md](READ-ME-TESTS.md).

## 5. Risks

| Risk | What we do |
|---|---|
| The car's hardware isn't what the old repos say | the audit first; nothing changes until it's written up |
| No timeout today: a lost cable keeps the car going | fixed before any drive (TEAM-TODO B2) |
| Upgrading the Jetson loses the only copy of something | back up the whole disk first |
| Leaked passwords and keys in the old repos | changed, never copied (Q34) |
| GPS isn't accurate enough near buildings | an RTK fix, and the EKF with the wheels and IMU |
| The sim lies, because its numbers are guesses | measure, then test on stands before the ground |

## 6. Ideas we've talked about (not yet in the plan)

| Idea | Note |
|---|---|
| Ghost obstacles: a simulated person in Nav2 while the real car drives | safe way to test stopping |
| The car's pictures labelled for our own stop-sign model | only if the stock one fails |
| CARLA instead of Gazebo | parked (Q31) |
| An AI assistant that reads the live graph (MCP, read-only) | built: `docs/mcp.md` |

**Where decisions live:** the design doc (Q1-Q34), `docs/decisions.md`, and `docs/history/`.
