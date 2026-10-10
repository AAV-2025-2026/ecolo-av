# Running without the car: turtlesim, Gazebo, replay

Every backend consumes the same `/ego/actuator_cmd`, so the drivers, mux, ego and
localization run unchanged whether the "car" is a turtle, Gazebo, or the real thing. Test
in this order, and only move up a rung when the one below works:

| Rung | What runs | Needs | Proves |
|---|---|---|---|
| 1. Unit tests | the maths and protocols, no ROS | Python + pytest, Rust | ego's Twist→Ackermann, the CAN frames, the speed profile, the spine logic |
| 2. turtlesim | mux, ego, scripted driver, ekf_local, a 2D "car" | Jazzy | the command path end to end; keyboard/joystick/scripted driving |
| 3. Gazebo | the whole stack on a simulated car with IMU and GPS | Jazzy + Gazebo Harmonic | localization, Nav2 on the empty map and the test lot |
| 4. Replay | localization (and Nav2) on a recorded drive | Jazzy, a bag | config changes against real sensor data, on a laptop |
| 5. Car on stands | the real backend, wheels off the ground | the car | the firmware link, signs and limits |
| 6. Car | everything | the car, a safety driver | the phase you're on |

Set up Jazzy and build the workspace first: [platforms.md](platforms.md). Every command
below assumes a terminal where you've run `source install/setup.bash` in the workspace.

## 1. Unit tests

```bash
tools/test.sh
```

This runs our packages' Python tests, `cargo test` for the spine firmware, and a check
that `docs/interfaces.md` is up to date. It needs only Python (with pytest and PyYAML)
and Rust, not ROS, so it runs on a Mac or Windows too.

With Jazzy installed, `colcon test` and `colcon test-result --verbose` run the same Python
tests through ROS's build tool.

## 2. turtlesim: drive the turtle like a car

```bash
ros2 launch aav_bringup turtle.launch.py
```

This starts:
- turtlesim and `turtlesim_adapter`. The adapter steers the turtle with the car's
  bicycle model, using the same wheelbase, so it turns like the car.
- `twist_mux`, `ego` and the scripted driver.
- `robot_state_publisher`.
- `ekf_local`, without GPS.

The turtle's world is 11 m x 11 m, and the car can't turn tighter than a circle about
6 m across. Drive slowly and expect to hit walls.

**Keyboard**: in a second terminal, on the same laptop or any computer on the same
network, run:

```bash
tools/keyboard.sh
```

That is short for the full command:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
  -p stamped:=true -r cmd_vel:=/cmd_vel/remote
```

| Key | Does |
|---|---|
| `i` / `,` | forward / reverse |
| `u` / `o` | forward turning left / right |
| `m` / `.` | reverse turning |
| `j` / `l` | nothing: a car can't turn on the spot, so ego holds the wheels until it moves |
| `k` | stop |
| `q` / `z` | all speeds +/- 10% (starts at 0.5 m/s; ego caps it at 1.0 m/s) |

- **Hold the key down.** The keyboard sends one command per key press, and `twist_mux`
  drops an input 0.5 s after its last message. When you let go, the car stops within
  about a second.
- If it stutters when you first hold a key, shorten your OS key-repeat delay.

The keyboard goes in as `remote` (priority 90), so a joystick (100) still wins.

**Joystick:** plug it in and add `teleop:=true`. Hold the deadman button (the trigger)
and steer with the sticks.
- Holding the deadman with the sticks centred outranks every other driver. It's the
  safety driver's "stop".
- Releasing it hands control back to whichever driver is still sending commands. If none
  is, the car stops.

**Scripted drive:** speed up, hold, then slow down, on a gentle left curve:

```bash
ros2 action send_goal /scripted_drive aav_interfaces/action/ScriptedDrive \
  "{target_speed: 1.0, acceleration: 0.5, deceleration: 1.0, hold_time: 3.0, curvature: 0.2}" --feedback
```

Grab the keyboard or joystick mid-run: it outranks the script at once. When you let go,
the script carries on.

**E-stop:**
- Stop: `ros2 topic pub --once /estop std_msgs/msg/Bool "{data: true}"`. This blocks
  every driver.
- Clear: publish `data: false`.

## 3. Gazebo

```bash
ros2 launch aav_bringup sim.launch.py                 # empty world, Nav2 on the empty map
ros2 launch aav_bringup sim.launch.py world:=test_lot # the walled lot, with its map
```

Arguments:

| Argument | Default | Meaning |
|---|---|---|
| `world` | `empty` | `empty` or `test_lot` |
| `nav` | `true` | start Nav2 |
| `teleop` | `false` | `true` if a joystick is plugged in |
| `gui` | `true` | show the Gazebo window |
| `rviz` | `true` | open RViz |

How the simulated car connects:
- Gazebo plays the car with its Ackermann steering system, an IMU and a GPS.
- `gazebo_adapter` turns those into the same `/vehicle/odom`, `/imu/data_raw` and
  `/gps/fix` the real drivers publish.
- The IMU filter, both EKFs and `navsat_transform` then run with the car's own configs.
- The world's origin is the GPS datum, so map (0, 0) is where the car starts, facing east.
- Everything runs on simulated time (`/clock`).

How to drive it:
- **Keyboard:** `tools/keyboard.sh --sim`. It's the same as for turtlesim, but on
  simulation time.
- **Nav2 goal:** in RViz, click **2D Goal Pose**, then click and drag on the map. Nav2
  plans with the car's turning radius, and its command goes into the mux as `nav`
  (priority 20). Any human input overrides it.
- **From a terminal:**

  ```bash
  ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 20.0, y: 5.0}}}}"
  ```

- **GPS goals** (phase 2) use `/follow_gps_waypoints` with latitude/longitude points near
  the datum.

Gazebo Harmonic wants a real GPU. In a virtual machine, run `gui:=false` and watch
in RViz or Foxglove instead.

## 4. Replay a recorded drive

On the car, record what the sensors saw and what the stack decided:

```bash
tools/record.sh parking_lot_test        # -> bags/<date>_parking_lot_test/
```

**Re-run localization** (and optionally Nav2) on any laptop, against that drive:

```bash
ros2 launch aav_bringup replay.launch.py [nav:=false] [rviz:=true]
ros2 bag play bags/<the bag> --clock --topics /vehicle/odom /imu/data_raw /gps/fix /tf_static
```

Change an EKF setting, replay, and compare the path. That is how to tune localization
without the car.

**Drive the same commands again**, on the car or in Gazebo:

```bash
tools/replay_commands.sh bags/<the bag>
```

This plays the recorded `/cmd_vel` back into the mux as `replay` (priority 40). It is
open loop, so the car drifts from the original path. The joystick and `/estop` still win.

## CARLA: next year

CARLA is a full self-driving simulator, with towns, traffic and photoreal cameras. It is
the right tool for perception, which is next year's work. As of October 2026 it doesn't
fit Jazzy:
- No released CARLA or `carla_ros_bridge` supports Jazzy or Ubuntu 24.04.
- CARLA 0.9.16 supports Ubuntu 20.04 and 22.04 and wants an NVIDIA GPU with 8 GB or more
  of video memory.
- The bridge was last updated in 2022, for ROS 2 Foxy.
- Jazzy support in CARLA's native ROS 2 interface exists only on unreleased branches.

`src/backends/aav_carla` is a stub written to the topic names the 2024-25 team used, and
it has never been run. Revisit it when CARLA ships a release with Jazzy support. Use
Gazebo this year.

## When nothing moves

Work down the chain:

1. Is a driver publishing? Run `ros2 topic hz /cmd_vel/remote` (or `/joy`,
   `/cmd_vel/scripted`, `/cmd_vel/nav`).
2. Did the mux pick it? Run `ros2 topic echo /cmd_vel`. If it's silent, check for a
   latched e-stop with `ros2 topic echo /estop`, and clear it by publishing `false`.
3. Is ego converting it? Run `ros2 topic echo /ego/actuator_cmd`. ego publishes at 50 Hz
   all the time, so look for speed 0.
4. Is a backend listening? Run `ros2 topic info /ego/actuator_cmd -v`.
5. In Gazebo or replay, is `use_sim_time` true for everything? A node on wall time
   ignores sim-time messages as stale.
6. Compare the whole graph against the contract: `tools/check_graph.py --profile turtle`
   (or `sim`, `car`).

More tools for looking inside a running system are in [guide.md](guide.md).
