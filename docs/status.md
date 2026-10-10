# Status: what works and what doesn't yet

Where things stand on 10 October 2026. "Works" means it ran under ROS 2 Jazzy on
oirp-spss (through Pixi). "Untested" means the code and its config exist, but it hasn't
run yet.

## Each box in the picture

| Box | Implemented by | Status |
|---|---|---|
| Wheel speed | `aav_legacy` `encoder_udp`; later the spine | [[untested]] needs the car |
| IMU | `yahboom_imu_cpp` + `imu_filter_madgwick` | [[untested]] builds; needs the device |
| GPS | `ublox_dgnss` | [[untested]] on Ubuntu; not packaged for Pixi |
| Car model | `aav_description` | [[works]] numbers are guesses |
| `ekf_local` | robot_localization | [[works]] in the turtle run |
| `ekf_global`, `navsat_transform` | robot_localization | [[untested]] needs GPS, so Gazebo first |
| Joystick | `aav_teleop` | [[untested]] |
| Keyboard | teleop_twist_keyboard | [[works]] |
| Scripted | `aav_scripted` | [[untested]] unit-tested |
| Nav2 | `aav_navigation` | [[untested]] |
| twist_mux | `aav_mux` | [[works]] |
| ego | `aav_ego` | [[works]] |
| turtlesim | `aav_turtlesim` | [[works]] |
| Gazebo | `aav_gazebo` | [[untested]] |
| Real car | `aav_spine` | [[untested]] unit-tested; no spine yet |
| Today's car | `aav_legacy` | [[untested]] on the car |
| Spine firmware logic | `firmware/spine/crates/spine-core` | [[works]] 43 tests |
| Spine board code (ESP32) | | [[missing]] |
| CARLA | `aav_carla` | [[stub]] next year |
| Lidar, cameras, AI | | [[later]] |

## Builds and tests

| Check | Result |
|---|---|
| `colcon build`, all 19 packages, Jazzy | [[works]] 11 s on Linux |
| Our tests: Python and Rust | [[works]] 88 pass |
| Lint tests of 3 inherited packages (IMU, radar, battery) | fail: style, not function |
| Live graph vs `docs/interfaces.yaml`, turtle profile | [[works]] 0 failures |
| Sim, car and replay profiles | [[untested]] |
| The same `pixi.toml` on macOS | resolves; the one known build blocker is fixed; [[untested]] |

## Is it all on Jazzy?

Yes. Everything builds against Jazzy, and the turtle profile runs. The code changes so far
were small: every node now shuts down cleanly on Ctrl-C under Jazzy. The configuration
files are being checked against what the Jazzy nodes really accept.

## Next

1. Run it on a Mac.
2. Run the Gazebo profile headless, then Nav2 in the simulator.
3. Fix whatever the Jazzy config checks find.
4. Measure the car, and replace the guesses in `vehicle.yaml`.
5. Choose the spine's microcontroller (Q10–Q17), then write its board code.
