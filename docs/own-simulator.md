# Our own simulator

Ben, 7 Nov: "merge in everything from gazebo so its standalone in rust". This page is the
simulator's **core**: the world, the car, the lidar, the radar, the IMU, the GPS, the wheels
and the clock. The cameras are their own part. The plan: [the design](designs/2026-11-05_own-simulator.md).

```sh
pixi run sim simulator:=own world:=test_lot gui:=false rviz:=false
pixi run sim-check --simulator own            # the road world's checks, on ours
```

Gazebo stays the default until ours passes the same checks.

## In one picture

```text
 ego ─> output mux ─> gazebo_adapter ──/gazebo/cmd_vel──> simulator (Rust)
                      (actuator model)                      │ world: Gazebo's .sdf files
                                                            │ car, rays, IMU, GPS, clock
 gazebo_imu, gazebo_gps, gazebo_radar, gazebo_adapter <─────┘ Gazebo's topics, rates, QoS
   └─> /sensors/*, /vehicle/*  ─> localization, Nav2, safety: unchanged
```

It replaces `gz sim` **and** its bridges. Every node above them is the same one Gazebo uses.

## What it gives

| Topic | Rate | Same as Gazebo? |
|---|---|---|
| `/clock` | 1 kHz | yes: one per step |
| `/gazebo/odom`, `/vehicle/sim/truth` | 50 Hz | yes |
| `/gazebo/imu` | 50 Hz, noise 0.02 rad/s, 0.2 m/s² | yes (the xacro's) |
| `/gazebo/navsat` | 5 Hz, noise 4.5e-6° (0.5 m) | yes; exact WGS84 from the world's datum |
| `/joint_states` | 100 Hz | Gazebo sends 1 kHz; the car's wheels 100 Hz |
| `/sensors/lidar/points` | 10 Hz, 1800 x 16, 0.5-100 m, 3 cm | yes: packed as Gazebo's, organised, `inf` misses |
| `/gazebo/radar/points` | 10 Hz, 61 x 3, 0.3-8.4 m, 5 cm | yes |
| cameras, chase camera | none yet | the cameras' crate plugs in |

## The worlds

| World | Read | Triangles |
|---|---|---|
| `empty`, `road`, `test_lot` | `aav_gazebo/worlds/*.sdf`, with `model://stop_sign` | 2 to 118 |
| `campus` | `maps/campus/campus.sdf` and its OBJ meshes (`pixi run campus`) | 595,845, read in 1.2 s |

The rays see what Gazebo's lidar sees: the **visuals**. One roof-lidar scan takes 1.7 ms in the
test lot and 15 ms on the campus (Ben's Mac, 4 threads).

## The car

| Part | How |
|---|---|
| Today | `gazebo_adapter`'s actuator model, then Gazebo's AckermannSteering (±10 m/s², the wheels steer at once), then the bicycle |
| Hitting things | the outline (`vehicle.yaml` `body:`) stops at what it meets, at 0.35, 0.8 and 1.3 m up, as Gazebo's physics does. The log says "the car hit something" |
| The trait | `sim-core` `CarModel`: `step`, `state`, `reset`, `hold`. The shared `car-model` crate goes in behind it at the merge |
| `ActuatorCar` | the actuator model itself, to `car-model`'s rules (exact lags, rate-limited motor, deadband, dead time). Tested; not wired in yet |

## Plug-in points

| For | Where | What it gets |
|---|---|---|
| Cameras, as their own program | `/vehicle/sim/truth` | the car's pose, 50 Hz, on sim time |
| Cameras, in the loop | `sim-core` `SensorPlugin` | the world, the car, `base_link`, the time, at its own period |
| The cameras' world | `World::shapes` | every shape as SDF draws it: box, cylinder, plane, mesh file; pose; colour |
| Placing things | `/vehicle/sim/spawn_entity`, `delete_entity` | `simulation_interfaces`: an SDF model, a pose |

When the cameras come in, `gazebo.launch.py` sets `gazebo_adapter`'s `cameras` to true, so
`/system/source` announces them.

## Results (7 Nov, Ben's Mac, other agents running: load 30-40)

| Check | Ours | Gazebo |
|---|---|---|
| `drop-in`, test lot | odom, status, IMU, GPS, radar, lidar: pass. Cameras: nothing (none yet) | pass (5 Nov) |
| A Nav2 goal, (14, 0) in the test lot | succeeded; the truth 0.4 m short, 0.9 m aside | succeeded (5 Nov) |
| `sim-check`: start-up, contract, lidar, scan, scripted drive, EKF vs truth (0.05-0.20 m), wheels vs IMU | pass | pass |
| `--lidar-obstacle` (the post) | pass: stopped 0.20 m before it | pass |
| `--obstacle` (the box) | stopped **0.33 m** before it; then the goal failed: a TF lookup ran late on the loaded Mac | 0.23 m (3 Nov) |
| `--speed-steps` (-0.5, 1, 2 m/s): overshoot | 15.8, 15.2, 10.1 %; within 5 % after 10.9-13.3 s | 15.9, 15.2, 10.1 %; 11-13 s (TODO 27) |
| `--drive-to-point`, 1 m/s | 7 of 8 pass, B within 0.11-0.34 m; the +150° leg refused (B inside the tightest turn from where the last leg stopped) | pass (0.2) |
| `--drive-to-point`, 3 m/s | 3 of 4 pass, B within 0.05-0.12 m; one leg held by the sensor watchdog (a stale sensor on the loaded Mac) | pass (0.2) |
| Real-time factor | 0.71-1.00 under that load | not run here: its renderer didn't load in this worktree |

## Not there yet

| Missing | Why it matters |
|---|---|
| Cameras | another part (`aav_sim_cameras`); until then `perception`, `lane`, `faults` need Gazebo |
| Ours as the default | after the same checks pass on a quiet computer, and Gazebo's spread is measured |
| Kerbs and slopes | the car stays on flat ground: a 0.3 m kerb neither lifts nor stops it (the outline is felt from 0.35 m up) |
| The car's own body in the lidar | Gazebo's lidar may see the car; ours doesn't |
| The Bevy window drawing ours | the window reads the same topics, so it works as with Gazebo; not run yet |
| `ActuatorCar` driving the node | the Python actuator model stays in front, as with Gazebo |
