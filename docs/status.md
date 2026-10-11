# Status: what works and what doesn't yet

Where things stand on the evening of 10 October 2026. "Works" means it ran under ROS 2
Jazzy through Pixi: on oirp-spss (Linux), and since 10 October on Ben's Mac too. "On the
bench" means [Bench mode](bench.md): the car's own software, with stand-ins for the
hardware. "Untested" means the
code and its config exist, but it hasn't run yet. The plan and the work left are in
[Work](work.md).

## Each box in the picture

| Box | Implemented by | Status |
|---|---|---|
| Wheel speed | `aav_legacy` `encoder_udp`; later the spine | [[untested]] needs the car |
| IMU | `yahboom_imu_cpp` + `imu_filter_madgwick` | [[untested]] builds; needs the device |
| GPS | `ublox_dgnss` | [[needs-you]] not in Pixi: keep it (apt, car only) or switch to `ublox` |
| Car model | `aav_description` | [[works]] numbers are guesses |
| `ekf_local` | robot_localization | [[works]] in the turtle run and on the bench |
| `ekf_global`, `navsat_transform` | robot_localization | [[works]] in Gazebo: parked, it stays within 0.2 m. On the bench: 0.03-0.3 m from the truth |
| Joystick | `aav_teleop` | [[untested]] |
| Keyboard | teleop_twist_keyboard | [[works]] |
| Scripted | `aav_scripted` | [[works]] turtle and the bench |
| Nav2 | `aav_navigation` | [[works]] in Gazebo: goals of 8 m and 9.5 m reached; on the bench, 40 m past a stop sign |
| twist_mux | `aav_mux` | [[works]] |
| ego | `aav_ego` | [[works]] |
| turtlesim | `aav_turtlesim` | [[works]] |
| Gazebo | `aav_gazebo` | [[works]] headless on Linux and a Mac; its window on a Mac, with the car driving (10 Oct) |
| Real car | `aav_spine` | [[works]] on the bench, against `spine_sim`: arming, driving, both e-stops |
| Today's car | `aav_legacy` | [[untested]] on the car |
| Spine firmware logic | `firmware/spine/crates/spine-core` | [[works]] 48 tests, and on the bench |
| Spine device drivers and glue | `jrk-g2`, `ad5311`, `pca9555`, `ibus`, `spine-board` | [[works]] 98 tests, against mocks |
| Spine board program | | [[missing]] waits on the chip |
| Bench mode | `aav_spine_sim`, `aav_bench` | [[works]] `pixi run bench-check`: 7 of 7 |
| Camera | `usb_cam` (`cameras.launch.py`) | [[untested]] Linux only; the models are Q22 |
| Stop signs | `aav_yolo` | [[works]] on the bench, with the stock YOLO model |
| Lane keeping | `aav_lane_geometry` | [[works]] on a pretend lane; the lane finder is [[missing]] |
| Radar clustering | `aav_object_detection` | [[works]] on the pretend radar |
| HUD back end | `aav_hud` | [[works]] on the bench; the app needs small changes |
| CARLA | `aav_carla` | [[stub]] parked (Q31) |
| Lidar | | [[later]] |

## Builds and tests

| Check | Result |
|---|---|
| `colcon build`, all 24 packages, Jazzy | [[works]] 11 s on Linux (19 packages); 15 s on the Mac (24) |
| `pixi run test`: build, tests, lint, `colcon test` | [[works]] all pass, 10 Oct: Python 153, Rust 171 and a no_std build for the Pico 2; `colcon test` 192, 0 failures |
| Live graph vs `docs/interfaces.yaml`: turtle, sim, replay and bench | [[works]] 0 failures each |
| `pixi run bench-check` (and `--perception`) | [[works]] 7 of 7 on the Mac, 10 Oct |
| Sim, headless: drive commands (the keyboard's topic) and Nav2 goals | [[works]] |
| Replay of a recorded drive | [[works]] the EKFs match the recording within 0.03 m |
| Car, with no hardware attached | comes up; only the missing sensors fail the graph check, as expected |
| The same `pixi.toml` on macOS | [[works]] on an Apple Silicon Mac (macOS 27), 10 Oct: build 18 s, `pixi run test` all green after one fix (GNU `coreutils`, see [Your Mac](mac.md)) |
| On the Mac: the turtle, Gazebo headless, a Nav2 goal, the Rust listener, the docs, `pixi run doctor`, recording a drive | [[works]] |
| On the Mac: Gazebo's window | [[works]] `pixi run sim` opens it, and the camera follows the car |
| On the Mac: RViz, rqt_graph | [[untested]] they open; nobody has looked at them yet |
| The same `pixi.toml` on the car's ARM computers, on today's Ubuntu 22.04 | resolves; [[untested]] |

## Is it all on Jazzy?

Yes. Everything builds against Jazzy, and the turtle, sim and replay profiles run. Every
configuration key was checked against what the running Jazzy nodes accept. The fixes were
small: clean shutdowns, Nav2 on simulated time, and the simulated GPS noise. The details
are in `docs/history/audit-2026-10-10-*.md`.

## Next

1. Join the car's network from the Mac (`pixi run doctor`), once the car runs Jazzy.
2. Pick the team's `ROS_DOMAIN_ID` and the GPS driver.
3. Drive the turtle with the joystick.
4. Measure the car, and replace the guesses in `vehicle.yaml`.
5. Choose the spine's microcontroller (Q10–Q17), then write its board code.
