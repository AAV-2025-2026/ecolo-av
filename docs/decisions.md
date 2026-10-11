# Decisions and open questions

What the team has decided, what's still open, and the 34 numbered questions. The source
is the team design doc, *AAV 2026–27 Autonomy Stack — Architecture & Plan* (a Claude Doc,
revision 61 on 10 October 2026). This page is a short copy, so you don't have to hunt.
When the two differ, the design doc wins.

## How to read the labels

| Label | Means | What you do |
|---|---|---|
| **Decided** | the team agreed | build on it; change it only after a team discussion |
| **Tentative** | the current direction, until a question is answered | build on it, but keep it easy to change |
| **Proposed** | a suggestion waiting for the team | accept or change it at the next team meeting |

Answer a question by its number, for example "Q12: targets". The design doc records the
answer.

## Decided

| # | Decision | Why |
|---|---|---|
| 1 | Commands follow one path: each driver → `twist_mux` → `ego` → one backend | Only ego talks to a backend; no driver reaches the actuators. Teleop (keyboard, remote, joystick) is a driver too (Ben, 9 Oct) |
| 2 | ego outputs Ackermann: `AckermannDriveStamped` | The real car, Gazebo, turtlesim and CARLA all take the same message, so a driver can't tell which one is running |
| 3 | Stock ROS packages: robot_localization (two EKFs), Nav2, nav2_costmap_2d, twist_mux | They replace the previous team's own estimator, planner, costmaps and command picking, where most of its bugs were |
| 4 | The joystick can drive the car with no autonomy running | Done with launch profiles |
| 5 | A CAN spine replaces the serial link from the Motor Pi to the ESP32 | Which signals cross the bus is still open: Q12 |
| 6 | ROS 2 Jazzy on every computer | Humble support ends in May 2027, Jazzy's in May 2029. ROS can't mix versions, so every computer moves together (Ben, 9 Oct) |
| 7 | One repo and one workspace, with folders by layer of the picture | One place to build, test and document everything |
| 8 | Languages: Python for every ROS node we write; Rust later; C++ only in the reused IMU driver | Our nodes run at 50 Hz or less, and the hard timing lives in the firmware. The spine logic is already Rust (`spine-core`) |
| 9 | Develop on Macs too, with Pixi and RoboStack | The same Jazzy on macOS and any Linux. The car's computers stay on Ubuntu 24.04; both use Fast DDS |

## Tentative

| Decision | Why | Waits on |
|---|---|---|
| No QNX | `twist_mux` takes over QNX's job of picking which command wins. Hard real-time safety moves into the spine firmware and the hardware e-stop | Q23 |
| GPS gives the global position; the model is unknown | Whether it uses RTK corrections decides how precise GPS A→B can be | Q18, Q19 |
| Bare metal waits: only the spine firmware runs without an operating system | Ben, 9 Oct: "Maybe we will wait on this." | |
| The spine runs on an ARM chip, a Pico 2 or an STM32, not the ESP32 | Ben, 10 Oct: yes. It keeps the whole toolchain in Pixi. An STM32 has CAN built in; a Pico 2 needs an add-on CAN chip | Q10–Q13 |

## Proposed: for the next team meeting

| Proposal | Why |
|---|---|
| `TwistStamped` on every `/cmd_vel*` topic | `twist_mux` expects it, and the timestamp lets ego drop stale commands. The code already does this |
| A car-safe Nav2: SmacPlannerHybrid with Regulated Pure Pursuit (or MPPI's Ackermann model), and no Spin in the behaviour tree | A car can't turn on the spot. The config already does this |
| The RC transmitter stays the top-priority override, in hardware | It works today, and doesn't depend on any computer |
| The spine boots latched, and arms only on a 0 → 1 edge; a driver fault stops the car | A reboot or a glitch never restarts the car by itself. It's in `spine-core` since 10 Oct |

## Ground rules

Rules for people and Claude sessions alike. They live in `CLAUDE.md`.

| Rule | In short |
|---|---|
| Units and frames | metres, radians, seconds; x forward, y left, z up; positive steering = left; `map → odom → base_link`, with `base_link` on the ground under the rear axle |
| Prefer stock | stock ROS packages first, then the previous teams' code, then a stub |
| Keep the maths out of ROS | a node's logic lives in a plain module, with its own tests |
| No pins in ROS | pins, I2C addresses and calibration stay in the firmware |
| Inherited code | keeps a `PROVENANCE.md`: where it came from, and every change since |
| Secrets | never in git, logs or docs: write down only where a secret is |
| Git | `main` lives on GitHub, in `zander1976/aav` (private), and CI tests every push; small commits, each passing the tests, with messages that give the intention |
| Docs | short pages, sections, tables and pictures; Ben is dyslexic |
| Port first | move everything to Jazzy as it is, then consider rewriting parts in Rust |
| Simulators | Gazebo and bench mode this year; CARLA parked until it supports Jazzy (Q31) |

## Decided on 10 October, on the Mac

| Decision | By |
|---|---|
| `aav/aav` is our version of the project. The other folders are the previous teams' code, or downloaded source | Ben |
| `aav` will become the merger of everything, in one organized project | Ben |
| Macs get GNU `coreutils` in their Pixi environment, so `colcon test` works on a Mac | a technical fix: see [Your Mac](mac.md) |
| Firmware and hardware drivers in Rust, not C or C++, even where the ROS nodes stay in Python. The 2025-26 C++ keeps running until each board's Rust version replaces it | Ben: see [Rust on the hardware](rust-firmware.md) |
| Bring perception in now, not next year: the YOLO detector, the camera calibrations, radar clustering, lane keeping | Ben: "Lets merge in all of this too" |
| Flesh out the whole graph down to the sensors, and stub in what the hardware and firmware don't have yet: bench mode | Ben: "get as much done as we can and stub in the rest" |
| PyTorch and YOLO live in a separate `ml` environment, so the default one stays small | a technical choice: see [Perception](perception.md) |
| Camera images are subscribed reliably, not best effort | measured on the Mac: best effort lost every image |
| The code lives in `git@github.com:zander1976/aav.git`, private (Q25) | Ben |
| CI runs `pixi run test` on Linux for every push, and on a Mac every night | Ben |
| Commit messages give the intention, with no attribution lines. The README's Credits section names the previous teams, the open-source projects and the AI assistant | Ben: "This is a school project" |
| The stand-ins (`turtle`, `sim`, `bench`, `view`, and the keyboard with `--sim` or `--local`) stay on the computer they run on, so a pretend car can never reach the real one | a safety choice, before the audit on the car's network: see [Simulation](simulation.md) |
| The car's red e-stop button always stops the car, whatever our software does. We don't rewire it; the spine only listens, through a spare contact, to report it and to stay stopped afterwards | Ben: "this already has an estop so we don't want to break that"; "I just want it to work" |
| No micro-ROS. Each board runs Rust and Embassy, and talks plain CAN, UART or UDP to a ROS node on Linux, which publishes | Ben, 10 Oct: "hardware with embassy and rust talking to an actual node running ros" |
| Our C++ moves to Rust: the IMU driver (Ben's twin), the radar clustering (a Rust ROS node), the encoder and display Picos (Embassy); the spine replaces the ESP32. Stock ROS packages stay | Ben, 10 Oct: "Can we change all the c++ to rust?" |
| ML: a detector on each machine with a GPU (the Orin, a laptop), each under its own name; no device aliases | Ben, 10 Oct: "the orin be one node and/or my laptop be another node" |
| Inference: TensorRT on the Orin (a `.engine` built there), Core ML on the MacBook Pro (a `.mlpackage`), both in our `aav_yolo` node. Isaac ROS's TensorRT detectors are the Orin's upgrade path | Ben, 10 Oct: "TensorRT on the Orin and CoreML ... on the macbook pro" |
| A read-only MCP server lets Claude or another AI app read the docs, the contracts and the live graph. It never writes to ROS, reads only files in git, and has its own `mcp` environment | Ben: "Yes, read-only": see [AI apps (MCP)](mcp.md) |
| Today's C++ boards build with PlatformIO, in a `firmware` environment. Its downloads go into `vendor/platformio/` | Ben: "We want everybody to be able to build this out of the box" |
| CARLA is parked for this year: Gazebo and bench mode cover driving, Nav2 and the sensors | recommended, after Ben asked "do we even care": see Q31 |
| The team's Linux machine with an NVIDIA card trains models. The 2024-25 `best.pt` is probably on it | Ben |

## Open questions

The design doc numbers 34 questions, and doesn't rank them. **Bold** marks the ones that
look like they block phase 0 or the first drives: a suggestion, for the team to change.
The design doc's next steps take Q1–Q9, Q18, Q20 and Q22 to the car with a tape measure.

### The car

| Q | Topic | The question |
|---|---|---|
| **Q1** | Dimensions | Wheelbase, track, overall size, steering limit, top speed? The old code disagrees: 1.3–1.57 m wheelbase |
| **Q2** | Steering feedback | Is the steering's position sensor wired to its Jrk G2? How do its counts map to the wheel angle? |
| **Q3** | Brake | How far does it travel, how hard does it brake, and what does it do if power is lost? That defines the safe state |
| **Q4** | Throttle | Which motor controller does the DAC drive? Does it brake on its own? Is reverse safe while moving? |
| Q5 | Wheel encoder | Which wheel, how many counts per turn, and can it wire straight to the spine? |
| **Q6** | E-stop | The car already has one (Ben, 10 Oct). Still open: what kind it is, what it cuts, and how it's wired |
| Q7 | RC override | Does the FlySky stay the top override? How does the spine know RC has taken over? |
| Q8 | Power | Battery voltage, the computers' supplies, and what the actuators do when a computer loses power |
| Q9 | Which computers stay | Orin, UI Pi, Motor Pi, radar Pi, camera Pi, QNX Pi? Suggested: the Orin, the spine and the HUD screen |

### The spine and the actuators

| Q | Topic | The question |
|---|---|---|
| **Q10** | Owner | Who owns the spine firmware and the CAN frame map? |
| Q11 | Starting firmware | Which firmware is on the ESP32 now? Build on AAV_cortex's, Motor_Steering's add-on, or the 2024-25 `FinalRev`? |
| **Q12** | What the spine accepts | Target speed and steering angle (the speed loop in the firmware), or raw throttle and brake? Suggested: targets |
| Q13 | Board | Add a CAN transceiver to today's ESP32 board, or a new board? Who changes the PCB? |
| Q14 | The Orin's side | Its built-in CAN with a transceiver, or a USB-CAN adapter? |
| Q15 | The bus | Bitrate, connectors, cable route, terminators, and what else shares it |
| Q16 | Watchdog | How long without a command before it acts, how hard it brakes, and what the steering does |
| Q17 | Wireless updates | Keep them? If so, how are they authenticated? |

### Sensors and localization

| Q | Topic | The question |
|---|---|---|
| **Q18** | GPS model | Which receiver is on the car? RTK or plain GPS? One antenna or two? It also picks the ROS driver |
| Q19 | Corrections | If RTK: which correction source, and is there internet at the test site? |
| Q20 | IMU | Keep the Yahboom on USB? Where is it mounted? Is its magnetometer usable on the car? |
| **Q21** | Test site | Where do we drive, and who gives permission? A surveyed point there becomes the map origin |
| Q22 | Lidar and cameras | Which models are on the car? Not needed until phase 4, but the URDF and the power budget need them |

### Software and process

| Q | Topic | The question |
|---|---|---|
| Q23 | QNX | Is it definitely dropped? Is it a course or sponsor requirement? |
| **Q24** | Jazzy on the car | Who images and reflashes the Orin, and when? Is there a spare machine to try JetPack 7.2 first? Until then, Pixi can run Jazzy on the car's Ubuntu 22.04 |
| Q25 | Repo | A new 2026-27 GitHub organization, or the existing one? **Answered by Ben, 10 Oct: `zander1976/aav`, private** |
| Q26 | Languages | Python for all our ROS nodes? C++ or Rust for the spine firmware? |
| Q27 | Steering at standstill | A speed-and-turn-rate command can't steer at zero speed. Should the joystick turn the wheels while stopped? |
| Q28 | Joystick handover | When the hold-to-drive button is released, go back to the autonomous driver, or stay stopped? |
| Q29 | HUD | Keep the Flutter app? Which screen runs it? Does it send GPS destinations this year? |
| Q30 | Remote driving | In scope this year? Over which link, with what latency limit? |
| Q31 | CARLA | Parked this year: no confirmed Jazzy support (the fix was closed unmerged, 26 May 2026), and no Mac version. If it comes back: the NVIDIA Linux machine, with CARLA 0.9.16 (Unreal Engine 4) or 0.10 (Unreal Engine 5) |
| **Q32** | Test rules | Who is the safety driver, what's the speed cap, what's on the pre-drive checklist, who signs it off? |
| **Q33** | Owners | Who owns each package? |
| **Q34** | Secrets | Have the leaked GitHub token, Firebase keys and WiFi password been revoked or changed? Who controls those accounts? |

## Also waiting on the team

From tonight's audits and the Mac work. They're small, but someone has to say yes.

| Item | The choice |
|---|---|
| `ROS_DOMAIN_ID` | one number (0–101) for the car and every laptop |
| GPS driver | keep `ublox_dgnss` (the car only) or switch to `ublox`, which Pixi has (with Q18) |
| `/estop` reliability (N2) | send it repeatedly, or make the mux hear it reliably |
| Respawning device nodes (N3) | restart a sensor driver when it dies? |
| Nav2's lookahead (N7) | its turn command flips sign about once a second in the sim |
| Package renames | the inherited packages' new names, in [Conventions](conventions.md) |
| A `vendor/` folder | keep downloaded source out of git, with a list to fetch it again |
| Stop signs as a twist_mux lock | priority 30: it holds Nav2 and the AI slot, never a person or a test script; 4 s stop, then 10 s to drive past. Built and working on the bench (Proposed) |
| The steering on an e-stop | hold where it is (`spine-core` today), or centre it (the 2025-26 firmware) |
| The brake after boot | `idle_brake` 0 lets it go once the e-stop clears; the old firmware kept it on |
| The RC gear switch's brake position | today it means "speed zero"; a brake field in `RcInput` would bring back the old full brake |
| The remaining renames | `yahboom_imu_cpp`, `ti_ros2_driver`, `battery_monitor`: [Conventions](conventions.md) |
