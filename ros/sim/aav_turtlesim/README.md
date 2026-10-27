# aav_turtlesim

turtlesim as the car: the quickest whole-loop test, on any laptop. `turtlesim_adapter`
drives the turtle like a car (the bicycle model, with the car's wheelbase) and reports
its speed as `/vehicle/odom`.

## Overview

```
/control/turtle/actuator_cmd ─> turtlesim_adapter ─> /turtle1/cmd_vel ─> turtlesim
/turtle1/pose ─> turtlesim_adapter ─> /vehicle/odom, /vehicle/status, /vehicle/steering
```

- It tests the joystick, the mux, ego, the scripted driver and `ekf_local` together.
- One turtlesim unit counts as one metre. The world is 11 x 11 m and the car's
  turning circle is almost 6 m across, so drive slowly.
- `pixi run turtle` starts it through `aav_bringup`'s `turtle.launch.py`, on this
  computer only (`tools/ros.sh --local`).

## Interface

### Launch: `launch/turtlesim.launch.py`

Starts the stock `turtlesim_node` (named `turtlesim`) and `turtlesim_adapter`, with
`wheelbase` from `vehicle.yaml`. Argument: `use_sim_time` (false).

### Node: `turtlesim_adapter` (`aav_turtlesim/turtlesim_adapter.py`)

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/control/turtle/actuator_cmd` | `ackermann_msgs/AckermannDriveStamped`: ego's command, from `aav_io_mux` (target turtle) |
| Subscribes | `/turtle1/pose` | `turtlesim/Pose` |
| Publishes | `/turtle1/cmd_vel` | `geometry_msgs/Twist`: v, and w = v tan(δ) / L |
| Publishes | `/vehicle/odom` | `nav_msgs/Odometry`, twist only, `odom` to `base_link` |
| Publishes | `/vehicle/status` | `aav_interfaces/VehicleStatus` (mode COMPUTER, armed) |
| Publishes | `/vehicle/steering` | `aav_interfaces/ActuatorState`: command = measured |
| Publishes | `/system/source` | `aav_interfaces/DataSource`, latched: vehicle and odometry are SIM |

Parameters: `wheelbase` (m; default 1.57, the launch file passes `vehicle.yaml`'s);
`cmd_timeout` (0.2 s).

`/turtle1/*` is turtlesim's own side and not in `docs/interfaces.yaml`
(`docs/naming.md`).

## Invariants

- Positive steering turns left (REP-103). Speed in m/s, angle in rad.
- The turtle steers at once: `measured` always equals `command`.
- Odometry carries the twist only. The pose covariance is huge (1e3), so `ekf_local`
  ignores the pose.
- No command for `cmd_timeout` (0.2 s, steady clock): one zero `Twist`, and the turtle
  stops, as the other stand-ins do.
- It runs only in the `turtle` profile. Exactly one backend runs at a time.

## Side Effects

- Publishes the topics above, and moves the turtle.
- No files, no hardware.

## Verification

```sh
pixi run build && colcon test --packages-select aav_turtlesim && colcon test-result --verbose
```

The package has no tests of its own yet. `pixi run test` runs everything. To try the
loop: `pixi run turtle`, then `pixi run check turtle`.
