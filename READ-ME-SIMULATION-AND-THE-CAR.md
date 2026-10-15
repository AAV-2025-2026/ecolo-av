# Simulation and the real car: how far we've got

Written 15 October 2026, for Ben. It answers three questions:

1. How far did we get with Gazebo?
2. Does it really produce sensor data?
3. How does any of it relate to the real car?

> **The short version**
> - **Gazebo works**, and it **does produce sensor data**: an IMU, a GPS and wheel speed, on `main`.
> - A camera and a radar in Gazebo are **on a branch**, being finished tonight.
> - **There is no lidar** anywhere yet, not even in simulation.
> - **None of our code has run on the real car yet.** Everything "works" in simulation or on the bench only.
> - The point of simulation: the **same nodes** run in all three places. Only the bottom layer changes.

## 1. The big idea: swap the bottom layer

Most of the software doesn't know whether it's driving a real car or a pretend one.

```text
            ┌──────────────────────────────────────────────┐
  THE SAME  │ drivers → twist_mux → ego                    │
  EVERYWHERE│ EKFs, navsat_transform, Nav2, perception, HUD│
            └──────────────────────┬───────────────────────┘
                     /ego/actuator_cmd  ↓      ↑  /vehicle/odom, /imu, /sensors/gps/fix ...
            ┌──────────────┬────────────────┬────────────────┐
  SWAPPED   │  Gazebo      │  The bench     │  The real car  │
            │ (simulator)  │ (stand-ins)    │ (hardware)     │
            └──────────────┴────────────────┴────────────────┘
```

- Everything **above** the line is the same code, with the same settings.
- Only the **bottom box** changes. We call it the **backend**, and exactly one runs at a time.
- So if Nav2 drives well in Gazebo, the same Nav2 should drive the car. The only differences are the real sensors' noise and the real motors.

## 2. The three bottom boxes

| | Gazebo | The bench | The real car |
|---|---|---|---|
| What it is | a 3D physics simulator | stand-in programs: no physics, no 3D | the car |
| Command | `pixi run sim` | `pixi run bench` | not ready yet |
| Who plays the car | Gazebo's Ackermann car model | `aav_spine_sim`: the spine's own firmware logic, on a model car | the boards and motors |
| Sensors come from | Gazebo's sensor models | small "mock" nodes that pretend | the real devices |
| CAN frames | no | **yes**: the same frames the real spine will send | yes, after the KEFC work |
| Best for | Nav2, localization, driving in a world | the car's own software path, e-stops, CAN | the truth |
| Status | ✅ works on Linux and on the Mac | ✅ works, with its own checks | ❌ never run |

## 3. Does Gazebo produce sensor data? Yes

### On `main` (today)

| Sensor | Gazebo makes it | The car's software sees it as | Rate | Status |
|---|---|---|---|---|
| IMU | `/aav/imu` | `/sensors/imu/data_raw` → filter → `/sensors/imu/data` | 50 Hz | ✅ |
| GPS | `/aav/navsat` | `/sensors/gps/fix` | 5 Hz | ✅ |
| Wheel speed | from the car model's motion | `/vehicle/odom` | 50 Hz | ✅ |
| Car status | from the car model | `/vehicle/status` | 50 Hz | ✅ |

**How it gets there:**

```text
Gazebo sensor → ros_gz_bridge → /gazebo/... → gazebo_adapter → the real drivers' topic names
```

`gazebo_adapter` renames everything to the **same names the real drivers use** (`/sensors/gps/fix`, `/sensors/imu/data_raw`, `/vehicle/odom`). The software above can't tell the difference.

![The simulated car in Gazebo](docs/img/gazebo-car.png)

### On the branch `wt/sim-full` (being finished tonight)

| Added | The car's software sees it as | Status |
|---|---|---|
| A road world: lane lines, a stop sign, a box in the road | | 🔧 written on 11 Oct, checked by `sim-check` then |
| A camera on the car | `/sensors/camera/front_left/image_raw` | 🔧 being finished |
| A radar on the car | `/sensors/radar/points` (via `/gazebo/radar/points`) | 🔧 being finished |
| A lidar on the roof | `/lidar/points` | 🔧 being tried: Gazebo's lidar can crash on a Mac |

A helper is finishing this branch tonight. It merges into `main` only if all its checks pass.

### Not simulated at all

| Thing | Why not |
|---|---|
| Lidar (on `main`) | no lidar in our code yet. Its model is unknown (Q22) |
| The magnetometer | the EKFs don't use it |
| The battery | nothing to simulate yet |
| The real CAN boards | that's the bench's job, not Gazebo's |

## 4. "Works" means: in simulation or on the bench

| Part | Gazebo | Bench | Real car |
|---|---|---|---|
| twist_mux, ego (the command path) | ✅ | ✅ | ❌ never run |
| Both EKFs + navsat_transform | ✅ within 0.2 m parked | ✅ 0.03-0.3 m from the truth | ❌ |
| Nav2 drives to a goal | ✅ 8 m and 9.5 m goals | ✅ 40 m past a stop sign | ❌ |
| Stop sign → the car stops | 🔧 on the branch | ✅ | ❌ |
| Obstacle stop (collision_monitor) | | ✅ | ❌ |
| The spine and CAN frames | | ✅ against the spine simulator | ❌ the board was never flashed |
| GPS driver (`ublox_gps`) | | | ❌ never run with the receiver |
| IMU driver | | | ❌ needs the device |
| The raylib HUD | ✅ as a ROS node, with test topics | ✅ next to bench mode | ❌ not on the car's screen yet |

## 5. Why none of it has run on the car yet

| Blocker | What it means | Who or when |
|---|---|---|
| **The car runs ROS 2 Humble; we use Jazzy** | the two can't talk on one network (Q24) | reflash the Orin, or run our Jazzy through Pixi on its Ubuntu 22.04 |
| **We've never logged in** | we don't know what runs on each Pi | **Friday's audit** |
| **The drive path is still the 2025-26 one** | Motor-Pi + ESP32 over UART/UDP. Our `aav_legacy` backend speaks it, but has never been tried | after the audit |
| **CAN isn't wired yet** | the KEFC parts are still to buy | after the order |

## 6. Today vs after the KEFC changes

| Layer | Today on the car | Our code today | After KEFC |
|---|---|---|---|
| Computer | Orin #1 (Humble) | runs on Jazzy | Orin #1 (control, EKF) + Orin #2 (perception, Nav2) |
| Drive path | Motor-Pi → ESP32 (UART/UDP) | `aav_legacy` backend, untested | Orin → CAN → ESP32 control board (`aav_spine`) |
| Wheel speed | optical encoder (fouled) on a Pico 2 | `aav_legacy` reads it | 2 Hall sensors → 2 ESP32 wheel nodes → CAN |
| Steering feedback | none (open loop) | `measured_steering_angle` waits for it | KTC-100 pot → the Jrk G2 |
| GPS | ZED-F9R on a taped u.FL lead | `ublox_gps` driver, untested | new ZED-F9R board, screw-on antenna |
| Lidar | on the roof, unknown model | **nothing** | read on Orin #2 |
| Cameras | 2 front Pi 5s | `usb_cam` launch, untested | + a rear Pi 5 |

## 7. The plan, in order

1. **Tonight:** finish the Gazebo camera and radar (and maybe a lidar), and merge them if green.
2. **Friday:** the audit (`docs/car-photos.md` has the checklist). Find out what really runs.
3. **Then:** get our stack onto the car, either Jazzy on the Orin or Pixi, and listen first: `ros2 topic hz /sensors/gps/fix`.
4. **Then:** drive on stands through `aav_legacy`, before any CAN work.
5. **Then:** the KEFC parts, the CAN bench with a CANable, one board at a time.

## 8. Try it yourself

| You want to | Run |
|---|---|
| See Gazebo with the car | `pixi run sim` |
| See its sensor data | in another terminal: `pixi run tools/ros.sh ros2 topic hz /sensors/gps/fix` |
| Look at one GPS message | `pixi run tools/ros.sh ros2 topic echo --once /sensors/gps/fix` |
| Drive it | `pixi run keyboard --sim` |
| Check the whole graph | `pixi run check sim` |
| The bench instead | `pixi run bench`, then `pixi run bench-check` |
| The HUD on top of it | `pixi run hud` |

More detail: [Simulation](docs/simulation.md), [Bench mode](docs/bench.md), [Status](docs/status.md).
