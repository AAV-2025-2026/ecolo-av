# Path followers: Regulated Pure Pursuit and MPPI

Nav2's planner draws a path; a **controller** turns it into a speed and a turn, 20 times a
second. We have two, and a script that compares them on the same drives in Gazebo.

> **The short version**
> - **Regulated Pure Pursuit (RPP)** is the default: it chases a point 2-4 m ahead on the path. Simple and steady.
> - **MPPI** tries 2000 possible futures every cycle through a model of the car, and picks the best blend. It can steer around things the planner didn't know about; it costs more computer.
> - **Switch:** `controller:=mppi` on `sim.launch.py` or `navigation.launch.py`.
> - **Compare:** `pixi run controller-compare` (about 25 min, headless, on this computer only).
> - **Results, 22 Oct (Gazebo, one run each):** neither is ready to be the only one. MPPI went round the building where Regulated Pure Pursuit stopped at its corner; Regulated Pure Pursuit was twice as quick to the first goal, where MPPI looped to fix its heading. Both stopped before the box. MPPI used twice the CPU. **Regulated Pure Pursuit stays the default** until MPPI stops looping at goals.

## What each one does

| | Regulated Pure Pursuit | MPPI |
|---|---|---|
| Idea | aim at a point ahead on the path; steer the arc that reaches it | imagine 2000 futures 2.8 s long, score each, blend the best |
| Knows the car's shape | no: only its turning radius, through the planner | yes: the Ackermann turning radius and the outline (footprint) |
| An obstacle on the path | slows, then stops before it | may steer around it, if there's room |
| Settings to tune | a few (lookahead, speeds) | many (noise, temperature, eight scoring rules) |
| Computer | light | heavy: one of the reasons for a second Orin |
| Paper | Macenski et al., 2023 | Williams et al., 2017 |

Both read the same costmap and send the same message to the same velocity smoother,
collision monitor, twist_mux and ego. Everything after the controller is the same.

## Switch between them

```bash
pixi run sim world:=test_lot controller:=mppi      # Gazebo, MPPI following the path
ros2 launch aav_navigation navigation.launch.py controller:=mppi
```

`controller:=` takes `rpp` (the default) or `mppi`. The launch file copies the `MPPI` block
of `nav2.yaml` under the name the behaviour trees ask for, `FollowPath`, and sets its
turning radius, its reverse speed and its top speed from `vehicle.yaml`
(`aav_description/vehicle.py`, `nav2_tuned`).

## Compare them

```bash
pixi run controller-compare                    # both controllers, both tours
pixi run controller-compare --tours obstacle   # only the box in the lane
pixi run controller-compare --controllers mppi --speed 2
```

For each tour and controller the script starts Gazebo's test lot with no windows, on a ROS
domain of its own (this computer only), sends the same goals, and records where the car
really was (Gazebo's ground truth). Forward only, as on the car. The results go to
`log/controller-compare/<time>/`:

| File | What |
|---|---|
| `results.md` | a table per goal: one column per controller |
| `lot.svg`, `obstacle.svg` | where each controller took the car, on the map |
| `results.json` | the numbers, and each drive's track |
| `sim-<tour>-<controller>.log` | everything the simulator said |

| Tour | Goals |
|---|---|
| `lot` | a left turn; round the building; a turn back in the 14 m lane; home |
| `obstacle` | 30 m east, with a 1 m box in the lane at 15.5 m. The planner's map has no box in it, so only the controller and the collision monitor can deal with it |

What the numbers mean (`tools/drive_metrics.py`):

| Number | Means |
|---|---|
| Time | from the goal sent to Nav2's answer |
| Controller asked to move after | the controller's first speed command over 0.05 m/s |
| Car moving after | the car 0.1 m from where it started |
| Off the path | from the planner's newest path (it replans every second) |
| Off the first route | from the first path: shows a car that wanders off |
| End: off the goal | where the car stopped, against the goal |
| Steering work | how fast the steering command changes (RMS): lower is smoother |
| Stops, reversals | stand-stills of 1 s or more; changes of direction |
| Closest to the box | the car's outline to the box's |
| Controller CPU | `controller_server`'s share of one core |

## Results, 22 October

Gazebo's test lot on Ben's Mac (M4 Max), headless, 1 m/s, forward only, with MPPI's
settings from "Making MPPI drive" below. One run each: read small differences as noise.

![Where each controller took the car in the test lot](img/controllers-lot.svg)

| Goal | Regulated Pure Pursuit | MPPI |
|---|---|---|
| A left turn (15, 15), 21 m | ✅ 28 s, drove 21.5 m, 0.32 m from the goal | ✅ 58 s, drove **47.5 m**: it reached the point, then drove a full circle to face north |
| Round the building (35, 42) | ❌ stopped at the building's north-west corner: the collision monitor saw the wall in its 1 m stop box | ✅ 45 s, 0.57 m from the goal: it kept further from the corner |
| Turn back in the 14 m lane (20, 42, facing west) | ❌ still stuck at the corner (forward only, no way out) | ❌ drove 16 m east and round; stopped by the collision monitor near the building |
| Home (0, 0) | ❌ still stuck | ❌ the sensor watchdog stopped Nav2: the IMU and wheel speed silent for 0.5-0.8 s (see "Found on the way") |

![The box in the lane](img/controllers-box.svg)

| The box in the lane | Regulated Pure Pursuit | MPPI |
|---|---|---|
| What happened | drove at it; stopped 0.36 m before it | drove at it; stopped 0.25 m before it |
| Who stopped it | the collision monitor | the collision monitor |
| Steered round? | no: it follows the path | no: its path goes through the box, and its path rules outweigh its cost rule |

| On average | Regulated Pure Pursuit | MPPI |
|---|---|---|
| Off the path (mean) | 0.12-0.18 m | 0.13-0.16 m |
| Steering work (lower is smoother) | 0.39-0.54 rad/s | 0.14-0.41 rad/s: smoother |
| `controller_server` CPU | 10-11% of a core | 21-32% of a core: twice to three times |

What it means:

| | |
|---|---|
| **Default** | Regulated Pure Pursuit stays the default: quicker, cheaper, and no loops at goals |
| **MPPI next** | stop the loops: drop or soften `GoalAngleCritic`, or widen its angle threshold, so it accepts the heading it arrives with (the goal checker allows 0.5 rad anyway) |
| **Both** | the corner problem: the planner's paths pass walls closer than the collision monitor allows (PLAN.md M8) |
| **Both** | steering round the box needs the obstacle in the planner's map (PLAN.md M5) |

## Making MPPI drive

With the settings first written for it (Nav2's examples for a small robot), MPPI in Gazebo
sat still for 13 s, then crept at 0.2 m/s and drifted metres off a straight path. Found on
22 October, one cause at a time, by printing each layer's command twice a second:

| What we saw | Why | Change |
|---|---|---|
| Its speed flipped between forward and back for 12 s | the simulator let Nav2 reverse (`reversing:=true` by default), and MPPI dithered around zero | the comparison runs forward only, as the car does |
| Nav2 warned "Inconsistent configuration in collision checking" | MPPI checked a circle; the costmaps use the car's 2 x 1 m outline | `CostCritic.consider_footprint: true` |
| Fast samples all swerved | it tried turn rates of ±0.4 rad/s, but the car turns at most 0.35 rad/s at 1 m/s (full lock): fast samples left the path, slow ones won | `wz_std` 0.4 → 0.1 |
| Speed built up by only 0.015 m/s each second | its samples' speed changes were clipped by the 1 m/s² limit (0.05 m/s per step up, but 0.1 down), so its futures drifted slower | `ax_max` 1.0 → 3.0 for its planning only (ego and the smoother still hold the car to 1 m/s²); `ax_min` stays at ego's -2.0 |
| Still slow to commit | small speed samples, a soft blend | `vx_std` 0.2 → 0.4, `temperature` 0.3 → 0.15 |

After the changes: moving within 0.5 s, about 0.95 m/s, within about 0.5 m of a straight
path. The settings and their reasons are in `nav2.yaml`, above the `MPPI` block.

## Found on the way

- **The global EKF's heading jumps at walking pace.** GPS gives only a position; the
  filter reads each fix's error (0.5 m in Gazebo) partly as a heading error, and the slower
  the car the bigger it reads it: ±20° at 0.2 m/s. Nav2 places its path with that pose, so
  the path swings round the car. Regulated Pure Pursuit, aiming 2-4 m ahead, barely
  notices; a slow MPPI did. It is probably also why a "straight" 10 m drive turned 38° on
  21 October. Lowering the filter's heading noise helped but didn't cure it: a heading
  source (two GPS antennas, or the F9R's own fused heading) is the real fix. Open, for
  localization (proposal T6.3).
- **Late data, twice, on an otherwise punctual Mac.** Once `map → odom` was 1.4 s old
  just after start-up, and Nav2 refused the goal ("Transform data too old"). Once, six
  minutes into a run, the IMU and wheel speed went silent for 0.5-0.8 s, and the sensor
  watchdog stopped Nav2. Measured for a minute, parked and driving with MPPI, the same
  simulator kept real time (0.99) with every topic under 80 ms late, using 3 of the Mac's
  16 cores. So it isn't the Mac's size: Gazebo's main loop is 89% of one core, and our
  Python `gazebo_adapter` relays the IMU and wheel speed from one thread. Either can hiccup.

## Limits of this comparison

| | |
|---|---|
| One run each | the numbers vary from run to run: read differences under about 20% as noise |
| Gazebo on a Mac | CPU numbers are the Mac's, not the Orin's |
| The car's numbers are guesses | the same guesses for both controllers (`vehicle.yaml`) |
| 1 m/s | the car's limit this year; `--speed` goes up to 5 in the simulator |
