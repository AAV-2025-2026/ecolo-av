# Sources and targets: the sensor mux and the output mux

Simulated data must never drive the real car (PLAN.md S-4, T1.5, decision D3). Two
nodes at the edges of the stack make sure: the **sensor mux** checks where the data comes
from, and the **output mux** sends ego's commands to one target, the real car only while
everything is real. Package `aav_io_mux`, built 23 Oct.

!!! note "The short version"
    - **Source:** where the sensor data comes from: `real`, `sim`, `bench` or `replay`.
    - **Target:** who plays the car: `car`, `gazebo`, `bench`, `turtle` or `carla`.
    - Every backend reads only its own target's topic, `/control/<target>/actuator_cmd`.
      Nothing reads `/ego/actuator_cmd` directly any more.
    - The real car's topic carries commands only while **every** source is REAL. One SIM
      or BENCH anywhere on the network, and it goes silent, **latched**: the car brakes.
    - Reopen it, once the cause is gone: `pixi run gate-clear` (the service
      `/safety/output_mux/clear`).
    - The HUD shows it (24 Oct): a red **STOP** with the reason, such as "GPS is SIM";
      amber **WAIT**; green **GO** ([HUD](hud.md#may-the-car-move-the-go-stop-panel)).

## The picture

```text
 sources                       checked by                    targets
 ───────                       ──────────                    ───────
 real drivers ─┐                                       ┌─► /control/car/... ──► spine_bridge
 Gazebo        ├─► /sensors/... ──► sensor_mux         │                        legacy_uart_bridge
 bench mocks   │   /vehicle/...      │ /system/sensor_mux/state
 a bag (replay)┘   /system/source ───┤ (ok? which source?)
                                     ▼                 ├─► /control/gazebo/.. ──► gazebo_adapter
 drivers ─► twist_mux ─► ego ─► output_mux ────────────┤   /control/bench/... ──► spine_bridge (bench)
                    /ego/actuator_cmd  (target:=car)   └─► /control/turtle/.. ──► turtlesim_adapter
```

## What each one checks

| Node | Reads | Says no when |
|---|---|---|
| `sensor_mux` (`source:=`) | `/system/source`; who publishes each sensor topic (the ROS graph) | any announcement isn't `source`; a sensor topic has **two** publishers; in a simulator, a sensor nobody announces (a real driver?) |
| `output_mux` (`target:=`) | ego's command; the sensor mux's verdict; `/system/source` | the sensor mux says no, checks for another source, or goes quiet for 3 s; any announcement isn't the target's source |

Both forget an announcement once the node that made it has gone. The real car's stock
drivers (u-blox, Velodyne, usb_cam) can't announce, so an unannounced sensor counts as
REAL. Every stand-in announces (Gazebo, the bench's mocks, `spine_bridge` off the car, a
replay), so it can't pass for real.

## Open, wait, stop

| State on `/safety/output_mux/state` | Means | Commands |
|---|---|---|
| `WAIT` | **doubt**: the sensor mux not heard yet, or quiet for 3 s; or it's unsure; or 2 s of all clear not over | none, then by itself again |
| `OPEN` | every source is the target's | ego's, unchanged |
| `STOP` | **evidence**: an announcement of another source, or the sensor mux's problem. Latched, with the reason | none, until `/safety/output_mux/clear` |

Evidence and doubt:

| Finding | Kind | Why |
|---|---|---|
| `/system/source` says SIM, BENCH or REPLAY (on the car) | evidence, at once | a stand-in says so itself |
| Two publishers on one sensor topic | doubt; evidence once it lasts 5 s | discovery can show a node before its name |
| In a simulator, a sensor nobody announces | doubt; evidence once it lasts 5 s | a node can publish before its announcement arrives |
| The sensor mux quiet for 3 s | doubt | a busy computer can delay it; it never latches |

!!! warning "Arm the spine only once it says OPEN"
    Until then `spine_bridge` gets no commands, so the spine's 100 ms watchdog latches it
    again at once. `bench_check.py` and `sim_check.py` wait for OPEN before they arm.

When it sends nothing, each backend's own timeout brakes, as when ego stops: `spine_bridge`
after 0.1 s (then the spine's 100 ms watchdog), `legacy_uart_bridge` after 0.3 s, Gazebo
after 0.2 s. The clear service refuses while anything is still wrong, and says what.

## One launch, `target:=`

```text
ros2 launch aav_bringup stack.launch.py target:=gazebo world:=road
```

| `target:=` | Starts | Source |
|---|---|---|
| `turtle` | `turtle.launch.py` | sim |
| `gazebo` | `sim.launch.py` | sim |
| `bench` | `bench.launch.py` | bench |
| `car` | `car.launch.py` (with `machine:=`) | real |
| `carla` | `carla.launch.py` | sim |

`source:=` may only say the target's own: `target:=car source:=sim` stops before anything
starts. The `pixi run` tasks start the same files directly, each with its two muxes. On
the car the muxes run next to ego (its `ego` part).

## Why check, not copy

The proposal's sensor mux picks one source per sensor and republishes it. We check
instead, and let each launch start only the chosen source:

| | Copy (republish) | Check (ours) |
|---|---|---|
| Cameras and point clouds | twice the bandwidth, and a hop of delay | nothing extra: the data isn't touched |
| A stray publisher on `/sensors/...` | still gets through, beside the copy | caught: two publishers |
| If the mux dies | the sensors stop (the watchdog stops Nav2) | the output mux stops the car within 3 s |
| Picks a source while running | yes | no: the launch picks it (`target:=`, `source:=`) |

The output mux itself is one more hop for ego's commands. Measured on the bench (23 Oct,
a Mac at load 30-45): the gaps between commands were the same before and after it
(median 19-21 ms); the long gaps at start-up were ego's own, before the hop.

## The heartbeat to the ESP32 (24 Oct)

TODO 50 (Ben, 24 Oct). With each command it passes on, the output mux also sends a
counter, +1 each time, on `/control/<target>/heartbeat`. So the counter moves **only
while the gate is OPEN**.

```text
 output_mux ── /control/car/actuator_cmd ──► legacy_uart_bridge ── UART, v2 frames ──► ESP32
  (OPEN)    └─ /control/car/heartbeat ─────►   (Motor Pi: copies     counter frozen
               counter 1, 2 ... 255, 0          the counter)          100 ms ─► brake
```

| The gate | The counter | The ESP32 |
|---|---|---|
| OPEN, ego at 50 Hz | moves | drives |
| WAIT or STOP | stops | brakes 100 ms later, latched |
| the Orin, its network or ego gone | stops (the Pi keeps sending, with the old counter) | brakes 100 ms later, latched |

The Pi only copies it, so a Pi cut off from the Orin can't keep the car going. Only the
real car's `legacy_uart_bridge` reads it; `spine_bridge`'s DRIVE_CMD has a counter of its
own. The frame: [the heartbeat](rust-firmware.md#the-heartbeat-version-2-of-the-serial-frame-24-oct).

## What it can't catch

- A stand-in that announces nothing and runs **instead of** the real driver (one
  publisher, unannounced): it looks real. Every stand-in of ours announces.
- Ghost obstacles: they only add an obstacle to Nav2's view, never a sensor, so they're
  allowed on the car ([ghost obstacles](ghost-obstacles.md)).
- The first 4 s after start: the sensor mux stays quiet 2 s while discovery settles, and
  the output mux waits 2 s more. Nothing drives in that time.

## Tests

| Test | Checks |
|---|---|
| `aav_io_mux/test/test_provenance.py` | the rules, no ROS: 30 cases |
| `aav_io_mux/test/test_real_backend_guard.py` | the real nodes with `spine_bridge` (source real): all REAL, its DRIVE_CMD frames flow; Gazebo announcing SIM, **none**; and `spine_bridge` never listens to `/ego/actuator_cmd`. With `role:=sensors` (today's wiring: the Orin's CAN bus has only sensors), the mux still opens, not one frame reaches `/can/tx`, and it announces only the wheels |
| `aav_bringup/test/test_stack_launch.py` | `target:=` picks the profile; a wrong `source:=` is refused; every profile runs the two muxes with its own target |
| `pixi run sim-check`, `pixi run bench-check` | the whole graph with both muxes: contract, drive, e-stops. Passed 23 Oct |
| the turtle (`pixi run turtle`) | OPEN; a scripted drive moved the turtle at 0.86 m/s |
| `aav_io_mux/test/test_heartbeat.py`, `aav_legacy/test/test_heartbeat_chain.py` | the counter: +1 a command, wraps in a byte; the muxes and `legacy_uart_bridge` on a pseudo-terminal: the frames carry the mux's counter, frozen when ego stops; a shut gate sends **no** heartbeat |
