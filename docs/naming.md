# Topic names by area (Proposed, 14 October)

Ben, 14 Oct: "Maybe we need more structure like /localization/<command> and
/drivers/<command> /ego/<command> ... Something that isolates messages into their area."

**Status: Proposed** [[needs-you]]. Nothing is renamed yet.

## The rule

The first part of every name is the **area**: the layer of the picture it comes from. The
same areas as the folders under `src/`.

```text
/<area>/<device or node>/<thing>
```

| Area | Holds | Who publishes |
|---|---|---|
| `/sensors/` | raw sensor data | the drivers on the Pis and the Orins |
| `/vehicle/` | what the car says about itself | the backend (spine, legacy, Gazebo, bench) |
| `/can/` | raw CAN frames | the socketcan bridge |
| `/localization/` | where the car is | the EKFs, navsat_transform |
| `/perception/` | what the car sees | the detectors, the lane finder, radar clusters |
| `/drivers/` | one command per driver | joystick, keyboard, scripted, Nav2, AI, replay |
| `/control/` | the chosen command | twist_mux, the smoother |
| `/ego/` | the command for the wheels | ego |
| `/safety/` | e-stop, collision monitor | the HUD button, collision_monitor |
| `/hud/` | what only the screen needs | the HUD |

Global names stay global, because every ROS tool expects them: `/tf`, `/tf_static`,
`/clock`, `/robot_description`, `/joint_states`, `/diagnostics`, `/rosout`. Nav2 keeps its own
names (`/plan`, `/goal_pose`, its actions) for now.

## Old name → new name

| Now | Proposed |
|---|---|
| `/gps/fix` | `/sensors/gps/fix` |
| `/gps/fix_velocity` | `/sensors/gps/fix_velocity` |
| `/imu/data_raw`, `/imu/mag` | `/sensors/imu/data_raw`, `/sensors/imu/mag` |
| `/imu/data` (after Madgwick) | `/sensors/imu/data` |
| `/camera/image_raw` | `/sensors/camera/front_left/image_raw` |
| `/camera/right/...` | `/sensors/camera/front_right/...` |
| (none yet) | `/sensors/camera/rear/...` |
| (none yet: the lidar) | `/sensors/lidar/points` |
| `/radar/points` | `/sensors/radar/points` |
| `/battery_status` | `/vehicle/battery` |
| `/vehicle/odom`, `/vehicle/status` | unchanged |
| (new: the wheel nodes) | `/vehicle/wheel_speed` |
| `/to_can_bus`, `/from_can_bus` | `/can/tx`, `/can/rx` |
| `/odometry/local` | `/localization/odom/local` |
| `/odometry/global` | `/localization/odom/global` |
| `/odometry/gps` | `/localization/gps/odom` |
| `/gps/filtered` | `/localization/gps/fix` |
| `/radar/clusters` | `/perception/radar/clusters` |
| `/lane_geometry`, `/lane_geometry_status` | `/perception/lane/geometry`, `/perception/lane/status` |
| `/perception/stop` | `/perception/stop_sign` |
| `/joy` | `/drivers/joy/raw` |
| `/cmd_vel/joy`, `/cmd_vel/nav`, ... | `/drivers/joy/cmd_vel`, `/drivers/nav/cmd_vel`, ... |
| `/cmd_vel` (twist_mux out) | `/control/cmd_vel` |
| `/cmd_vel_smoothed` | `/control/cmd_vel_smoothed` |
| `/ego/actuator_cmd` | unchanged |
| `/estop` | `/safety/estop` |
| `/collision_monitor_state` | `/safety/collision_monitor/state` |

## How we would do it

1. Change `docs/interfaces.yaml` first (the contract), and regenerate `interfaces.md`.
2. Rename in the launch files and configs with **remaps**: most stock nodes (robot_localization,
   ublox, twist_mux) take a remap, not a code change.
3. A test that checks every name in `interfaces.yaml` starts with an area from the table.
4. `pixi run check sim` and `bench-check` must still pass.

## Why the two EKFs don't talk

The local EKF doesn't feed the global one, and that is on purpose: robot_localization's
standard setup. Each one fuses the raw sensors itself.

| | `ekf_local` | `ekf_global` |
|---|---|---|
| Uses | wheel speed, IMU | wheel speed, IMU, **GPS** |
| Gives | a smooth position that never jumps | a true position that may jump |
| Publishes | `odom → base_link` | `map → odom` |
| Who uses it | Nav2's controller (steering) | Nav2's planner, the HUD's map |

If the global EKF used the local one's output, the same wheel and IMU data would count
twice, and it would be too sure of itself. Feeding both from the raw sensors avoids that.

They do meet, but in **TF**, not on a topic: `ekf_global` publishes only the correction
`map → odom`, worked out on top of `ekf_local`'s `odom → base_link`. So `rqt_graph` shows
no line between them; `ros2 run rqt_tf_tree rqt_tf_tree` shows the chain. The launch
file's first line said "the local EKF feeds the global EKF"; it now says this (14 Oct).
