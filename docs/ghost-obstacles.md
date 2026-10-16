# Ghost obstacles: a pretend person for Nav2

A ghost is a person (or a post) that only Nav2 can see. Use it to test stopping on the
real car, with nothing real to hit. PLAN.md item S4, built 16 Oct.

!!! note "The short version"
    - Start with `ghost:=true`: `pixi run sim ghost:=true`, or `pixi run car <machine>
      ghost:=true` on the computer that runs Nav2. Off by default.
    - Place it: `pixi run ghost ahead 10` (10 m past the front bumper). Take it away:
      `pixi run ghost off`. In Gazebo, add `--local`: `pixi run ghost --local ahead 10`.
    - It **only adds**. It never clears or hides what the radar or the lidar sees.
    - It only stops **Nav2**. The joystick, the keyboard and the tests drive through it.

## How it fits

```text
 pixi run ghost ahead 10
        │ (parameters)
        ▼
 ghost_obstacle ──/safety/ghost/scan──┬──► local costmap: its own ghost_layer
   (aav_ghost)     (LaserScan, 10 Hz) └──► collision_monitor: its own ghost source
        │                                      │ stop zone
        └──/safety/ghost/marker──► RViz        ▼
                                          /drivers/nav/cmd_vel = 0
```

The scan is what a perfect 2D lidar at `base_link` would see of the ghost: its near side,
and `inf` everywhere else. With no ghost, the scan is all `inf`.

## Why it can't hide a real obstacle

| Part | The ghost's own | So |
|---|---|---|
| Local costmap | `ghost_layer`, a layer of its own | its clearing wipes only old ghosts, never the radar's or the lidar's marks |
| collision_monitor | `ghost`, a source of its own | it adds points to the stop zone; the radar's and the lidar's still count |
| Global costmap | nothing | the planner plans as before; the controller and the stop zone react |

## The commands

| Command | Does |
|---|---|
| `pixi run ghost ahead 10` | a ghost 10 m past the front bumper, on the car's heading, where the car is **now**. Then it stays put |
| `pixi run ghost at 20 0` | a ghost at map x 20, y 0 (m) |
| `pixi run ghost size 0.3 1.2` | a post instead of a person (width, height in m) |
| `pixi run ghost on` | the last ghost again (`ahead`: in front of the car again) |
| `pixi run ghost off` | take it away |
| `pixi run ghost --local ...` | the same, for Gazebo or the bench on this computer |

The same with ROS's own tools: `ros2 param set /ghost_obstacle enabled true`. Use
`10.0`, not `10`, for a number: ROS refuses an integer for a decimal parameter.

## Its settings

`src/safety/aav_ghost/config/ghost_obstacle.yaml`:

| Parameter | Default | Means |
|---|---|---|
| `enabled` | `false` | no ghost until someone asks |
| `ahead` | `10.0` m | from the front bumper to the ghost's near edge. Negative: use `x`, `y` |
| `x`, `y` | `0.0` m | where, in `frame`, when `ahead` is negative |
| `frame` | `map` | the ghost stands still in this frame |
| `width`, `height` | `0.5`, `1.7` m | a person |
| `rate_hz` | `10.0` | the scan's rate |

## On the real car

1. Start the car with `ghost:=true` on the machine that runs Nav2.
2. Clear lot, wheels on the ground, the safety driver holding the joystick.
3. `pixi run ghost ahead 15`, then send Nav2 a goal past it.
4. The car must stop 0-2 m before the ghost. `pixi run ghost off`: it drives on.

!!! warning "A ghost is not a safety test of the sensors"
    It tests Nav2's reaction: the costmap, the controller, collision_monitor, ego, the
    brakes. It doesn't test whether the radar or the lidar would have **seen** a person.

!!! note "A silent ghost stops Nav2"
    With `ghost:=true`, collision_monitor expects the scan. If `ghost_obstacle` dies, Nav2
    stops after 1 s, like a silent radar. That's on purpose: fail-safe.

## The test in Gazebo

`pixi run sim-check --ghost` (`READ-ME-TESTS.md` 1.13): a second Gazebo
run with `ghost:=true`. A ghost 15 m ahead; Nav2 drives 30 m.

| Must | How it's measured |
|---|---|
| stop 0-2 m before the ghost | the bumper to the ghost, in the ghost's own scan: what Nav2 sees |
| who stopped it | the stop zone (`/safety/collision_monitor/state`), or the controller's own collision check on the costmap, which can stop it first. Either counts |
| the local costmap marks it | 99 or more of 100 there |
| drive on once it's off | Nav2's goal reached, past where the ghost stood |
