# aav_teleop

Human drivers: the joystick, its e-stop button, and the keyboard. Only stock ROS
packages, set up by our config files: no code of our own. A person is a driver like any
other: they publish a velocity command into twist_mux and never talk to the wheels.

```
joystick -> joy_node -> /drivers/joy/joy -> teleop_twist_joy -> /drivers/joy/cmd_vel -> twist_mux
                                         -> joy_teleop (one button) -> /safety/estop true
keyboard -> teleop_twist_keyboard -> /drivers/keyboard/cmd_vel -> twist_mux
```

## Overview

It replaces the 2025-26 team's `joy_teleop_ackerman`, which drove the wheels directly.
The bringup profiles (`aav_bringup`: turtle, sim, bench, car, carla) start
`teleop.launch.py`. Run it on the computer the joystick's USB receiver is plugged into
(any computer on the same `ROS_DOMAIN_ID`).

## Interface

| Item | What |
|---|---|
| Launch | `ros2 launch aav_teleop teleop.launch.py [estop_button:=true] [use_sim_time:=false]` |
| Keyboard | `pixi run keyboard` (`tools/keyboard.sh`: teleop_twist_keyboard, `stamped:=true`, namespace `/drivers/keyboard`) |

Nodes (all in the namespace `/drivers/joy`, so relative topics land there):

| Node (package) | Reads | Writes |
|---|---|---|
| `joy_node` (joy) | the USB joystick | `/drivers/joy/joy` (`sensor_msgs/Joy`), 20 Hz while held |
| `teleop_twist_joy_node` (teleop_twist_joy) | `/drivers/joy/joy` | `/drivers/joy/cmd_vel` (`geometry_msgs/TwistStamped`, `base_link`) |
| `joy_teleop` (joy_teleop), if `estop_button` | `/drivers/joy/joy` | `/safety/estop` (`std_msgs/Bool`) true, once per press |

Config files (each names its node `/**/<node>`, so it matches in any namespace):

| File | Sets |
|---|---|
| `config/joy.yaml` | device 0, deadzone 0.05, autorepeat 20 Hz |
| `config/teleop_twist_joy.yaml` | deadman button 0 (trigger); axis 1 = speed, 1.0 m/s at full stick; axis 0 = turn rate, 0.35 rad/s at full stick; `inverted_reverse` |
| `config/estop_button.yaml` | button 2 publishes `/safety/estop` true |

twist_mux priorities: joystick 100, keyboard 90 (`aav_command_mux`).

## Invariants

- The joystick sends only while the deadman (button 0) is held, then one zero on release.
- The stick sets a turn **rate**, not a steering angle; ego converts it with the bicycle
  model. Full stick at 1.0 m/s is about full lock (`0.35 = 1.0 x tan(0.5) / 1.57`). The
  car can't steer standing still.
- Stick back = reverse while the trigger is held; ego caps it at `max_reverse_speed`.
- The e-stop button only ever sets true. There is no release button: joy_teleop 2.0.0
  reads an empty Joy message as "all pressed", and a spurious release is unsafe. Clear
  it from a laptop: `ros2 topic pub --once /safety/estop std_msgs/msg/Bool "{data: false}"`.
- Commands are `TwistStamped` (`publish_stamped_twist: true`), never Ackermann.
- TODO: check the button and axis numbers on the team's joystick
  (`ros2 run joy joy_enumerate_devices`, then `ros2 topic echo /drivers/joy/joy`).

## Side Effects

- Reads a USB joystick (`joy_node`).
- Publishes `/drivers/joy/cmd_vel` and `/safety/estop`; the keyboard publishes
  `/drivers/keyboard/cmd_vel`.

## Verification

No tests of its own (only config and a launch file).

```sh
pixi run build && ros2 launch aav_teleop teleop.launch.py
ros2 topic echo /drivers/joy/cmd_vel     # hold the trigger, move the stick
```

`pixi run check <turtle|sim|car>` checks the running graph against `docs/interfaces.yaml`.
`pixi run test` runs every package's tests.
