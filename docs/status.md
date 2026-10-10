# Status: what works and what doesn't yet

Where things stand on 10 October 2026. "Works" means it ran under ROS 2 Jazzy on
oirp-spss (through Pixi). "Untested" means the code and its config exist, but it hasn't
run yet.

## Each box in the picture

| Box | Implemented by | Status |
|---|---|---|
| Wheel speed | `aav_legacy` `encoder_udp`; later the spine | [[untested]] needs the car |
| IMU | `yahboom_imu_cpp` + `imu_filter_madgwick` | [[untested]] builds; needs the device |
| GPS | `ublox_dgnss` | [[needs-you]] not in Pixi: keep it (apt, car only) or switch to `ublox` |
| Car model | `aav_description` | [[works]] numbers are guesses |
| `ekf_local` | robot_localization | [[works]] in the turtle run |
| `ekf_global`, `navsat_transform` | robot_localization | [[works]] in Gazebo: parked, it stays within 0.2 m |
| Joystick | `aav_teleop` | [[untested]] |
| Keyboard | teleop_twist_keyboard | [[works]] |
| Scripted | `aav_scripted` | [[untested]] unit-tested |
| Nav2 | `aav_navigation` | [[works]] in Gazebo: goals of 8 m and 9.5 m reached |
| twist_mux | `aav_mux` | [[works]] |
| ego | `aav_ego` | [[works]] |
| turtlesim | `aav_turtlesim` | [[works]] |
| Gazebo | `aav_gazebo` | [[works]] headless; its window is untested |
| Real car | `aav_spine` | [[untested]] unit-tested; no spine yet |
| Today's car | `aav_legacy` | [[untested]] on the car |
| Spine firmware logic | `firmware/spine/crates/spine-core` | [[works]] 47 tests |
| Spine board code (ESP32) | | [[missing]] |
| CARLA | `aav_carla` | [[stub]] next year |
| Lidar, cameras, AI | | [[later]] |

## Builds and tests

| Check | Result |
|---|---|
| `colcon build`, all 19 packages, Jazzy | [[works]] 11 s on Linux |
| `pixi run test`: build, tests, lint, `colcon test` | [[works]] all pass: Python 47, Rust 47; `colcon test` 77, 0 failures |
| Live graph vs `docs/interfaces.yaml`: turtle, sim and replay | [[works]] 0 failures each |
| Sim, headless: drive commands (the keyboard's topic) and Nav2 goals | [[works]] |
| Replay of a recorded drive | [[works]] the EKFs match the recording within 0.03 m |
| Car, with no hardware attached | comes up; only the missing sensors fail the graph check, as expected |
| The same `pixi.toml` on macOS | resolves; the one known build blocker is fixed; [[untested]] |
| The same `pixi.toml` on the car's ARM computers, on today's Ubuntu 22.04 | resolves; [[untested]] |

## Is it all on Jazzy?

Yes. Everything builds against Jazzy, and the turtle, sim and replay profiles run. Every
configuration key was checked against what the running Jazzy nodes accept. The fixes were
small: clean shutdowns, Nav2 on simulated time, and the simulated GPS noise. The details
are in `docs/history/audit-2026-10-10-*.md`.

## Next

1. Run it on a Mac (`docs/mac.md`), then join the car's network (`pixi run doctor`).
2. Pick the team's `ROS_DOMAIN_ID` and the GPS driver.
3. Drive the turtle with the joystick.
4. Measure the car, and replace the guesses in `vehicle.yaml`.
5. Choose the spine's microcontroller (Q10–Q17), then write its board code.
