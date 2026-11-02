# Know the car: tests that learn it

Written 1 November 2026. Ben, 1 Nov: "drive 10m straight then measure how far it actually
went. Speed up and slow down and see the time and distance covered. If we do enough tests
we should be able to figure out the driving characteristics of the car and get more
accurate with every pass ... We can map the area while there."

> **The short version**
> - Six tests. Each **measures** one thing, **fits** one number in `vehicle.yaml` (or `legacy.yaml`), and is **run again** until the error is small.
> - Most already exist as [actuator tests](actuator-tests.md): this page puts them in order and says when to stop.
> - **Record the lidar the whole time**: the same drives give the lot's map.
> - First in Gazebo (`--sim`), then on stands, then the empty lot. A safety driver and the e-stop, always.

## The loop

```text
  run the test ──► measure (tape, stopwatch, the log) ──► fit one number
       ▲                                                       │
       └──── error still big? ◄── run again ◄── vehicle.yaml ◄─┘
```

Stop when **two runs in a row** are inside the "Good enough" column below.
Write each pass in the table at the bottom: the number before, the measured, the number after.

## The six tests

| # | Test | Run | Measure | Fits | Good enough |
|---|---|---|---|---|---|
| 1 | **10 m straight**, by tape | `pixi run actuator-test straight` ([4.7](tests.md#4b-steering-on-the-ground)); or by hand on the joystick | the tape's distance against the wheels' (`/vehicle/odom`, in the log) | `vehicle.yaml` `wheel_diameter` (test [4.20](tests.md#4e-record-the-lot-the-maps-and-the-scores)) | within 1 % (10 cm in 10 m) |
| 2 | **Speed step**, 0 to 1 m/s | `pixi run actuator-test speed-up` ([4.1](tests.md#4a-speed-up-coast-brake)) | the time to 1 m/s; the speed it settles at | `throttle_lag`, `max_accel`; on today's ESP32 also `legacy.yaml` `full_throttle_speed` | settles within 10 % of the speed asked |
| 3 | **Brake from 1 m/s** | `pixi run actuator-test brake` ([4.3](tests.md#4a-speed-up-coast-brake)) | the stopping distance (tape), g (IMU) | `max_brake`, `brake_lag` | the distance within 10 % of v² ÷ (2 × `max_brake`) |
| 4 | **Coast-down** from 2 m/s | `pixi run actuator-test coast` ([4.2](tests.md#4a-speed-up-coast-brake)) | how fast it slows | `drag` | two runs within 10 %. ❌ not on today's ESP32: a low command still pushes ([why](actuator-tests.md#what-the-car-can-measure-today)) |
| 5 | **Fixed-steering circle**, both ways | `pixi run actuator-test circles` ([4.5](tests.md#4b-steering-on-the-ground)) | the circle's diameter (tape across, or GPS); yaw rate ÷ speed | the real wheel angle per command: `max_steering_angle`, `steer_offset` (the centre) | the radius within 5 %; left and right within 5 % of each other |
| 6 | **Lock to lock**, on stands | test [3.0](tests.md#3b-steering-on-stands), then `pixi run actuator-test steer-sweep --stands` (3.10) | the steering actuator's ends and centre (counts), the angle at each end (protractor) | `max_steering_angle`; `steering_limits` | equal limits each side; the hardware lead reviews them |

How each number moves, test by test:

| # | New number |
|---|---|
| 1 | `wheel_diameter` × (tape ÷ wheels' distance) |
| 2 | `full_throttle_speed` × (speed reached ÷ speed asked); `throttle_lag` from the fit |
| 3 | `max_brake` from the fit; check it against the tape: v² ÷ (2 × distance) |
| 5 | wheel angle = atan(`wheelbase` ÷ radius), one per command; the centre where left and right match |

The fits themselves (the dead time, the lag, the refusals): [Trusting the fits](actuator-tests.md#trusting-the-fits).

## In what order

1. **6, then 5** first: steering is the one we can measure on stands, and every other test drives straight with it.
2. **1** next: every speed and distance after it reads the wheels.
3. **2, 3, 4**: the speed, the brake, the drag. They settle the "5 times" throttle disagreement ([the car's model](vehicle-model.md)).
4. Then test 1 again: a new `full_throttle_speed` can change the speed it drove at.

After each change: `pixi run python3 tools/vehicle_model.py --set <key>=<value>` shows what
it does to the car's model; at home, `pixi run test`.

## How good is it now?

A scripted 10 m stop scores the whole car at once, each pass:
`pixi run measure atob bags/<run> --taped <along> <across>` ([A to B](a-to-b.md)). The tape
splits the GPS's error from the control's. Tests 5.1 and 5.2 in [Every test](tests.md#stage-5-the-whole-drive).

## Map the lot at the same time

| ☐ | Do |
|---|---|
| ☐ | The lot's corner in `navsat.yaml`'s `datum`, **the same every time** ([4e](tests.md#4e-record-the-lot-the-maps-and-the-scores)) |
| ☐ | On the Orin, before the first test: `~/aav-jazzy/aav.sh tools/record.sh --lidar learn` (about 5 GB per 10 min: 20 GB free) |
| ☐ | Drive between the tests too: 2 laps, a figure 8 (4.19) |
| ☐ | Before leaving: `pixi run ndt-map build bags/<it> --poses /localization/odom/global` (4.21). Blurred? Record again while the car is there |

## The record of each pass

Print it. One line a pass.

| Pass | Test | Number | Before | Measured | After | Inside "good enough"? |
|---|---|---|---|---|---|---|
| 1 | 1 | `wheel_diameter` | 0.36 | | | ☐ |
| | | | | | | ☐ |
| | | | | | | ☐ |
| | | | | | | ☐ |
