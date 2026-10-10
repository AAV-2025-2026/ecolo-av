# Maps and costmaps

A **costmap** is a grid laid on the ground. Every cell holds a cost:
- free (0);
- near something (inflated, 1–252);
- inside something (lethal, 253–254);
- unknown (255).

Nav2's planner searches the grid for a path the car can drive. Its controller follows that
path and slows down near high-cost cells. `nav2_costmap_2d` builds the grids from layers.
The settings are in `src/drivers/aav_navigation/config/nav2.yaml`.

## The two costmaps

| | Local costmap | Global costmap |
|---|---|---|
| Used by | the controller (Regulated Pure Pursuit), each step | the planner (SmacPlannerHybrid), once per path |
| Frame | `odom`: smooth, moves with the car | `map`: fixed to the ground by GPS |
| Size | 20 m x 20 m rolling window, centred on the car | the size of the map that `map_server` loads |
| Cell size | 0.10 m (200 x 200 cells) | 0.25 m |
| Updates | 5 Hz | 1 Hz |
| Layers now | static (the map), inflation | static (the map), inflation |
| Layers later | + obstacle layer (radar/lidar), already written but not enabled | + obstacle layer if needed |

A 20 m window means 10 m ahead and behind, about 5 s of driving at 2 m/s, the most this
car is meant to do this year. Make it larger only if the car gets faster.

- **Footprint:** the car's outline, made from `body` in `vehicle.yaml` by the launch
  file. Nav2 checks that it doesn't enter lethal cells.
- **Inflation:** 2.0 m with cost scaling 3.0: at least the car's circumscribed radius,
  1.93 m. This keeps paths away from walls rather
  than scraping them.

## What each phase uses

| Phase | Map | What it tests |
|---|---|---|
| 0, 1 (joystick, scripted) | none | Nav2 isn't running |
| 2: Nav2 on an empty costmap | `maps/empty.yaml`: 200 m x 200 m, all free, 0.25 m cells, centred on the datum | planning and following within the turning limits, GPS goals |
| 3: Nav2 on a pre-rendered costmap | your test site, drawn as a map, e.g. `maps/example_lot.yaml` (an 80 m x 60 m made-up lot) | planning around known walls and buildings |
| perception (next year) | as phase 3, plus live obstacles | the obstacle layer and `collision_monitor` |

## Map files

A Nav2 map is an image (PGM or PNG) plus a YAML file that says how to read it.
`src/drivers/aav_navigation/maps/README.md` covers the format line by line. In short:
- one pixel is one cell;
- white is free, black is blocked, grey is unknown;
- `resolution` is metres per pixel;
- `origin` is the map-frame position of the bottom-left pixel.

Don't paint maps by hand. Write a short spec and generate them:

```bash
tools/make_map.py src/drivers/aav_navigation/maps/example_lot.spec.yaml
```

A spec lists:
- the size in metres east and north;
- the origin;
- blocked rectangles and free rectangles.

`tools/make_map.py --help` (or the top of the file) shows the format. It needs only
Python and PyYAML, not ROS.

## Your first map, in ten minutes

1. Open `src/drivers/aav_navigation/maps/example_lot.spec.yaml`, and add a box under
   `blocked:`:

    ```yaml
      - [15, -3, 18, 3]       # a box across the drive, to plan around
    ```

2. Make the map again:

    ```bash
    pixi run python tools/make_map.py src/drivers/aav_navigation/maps/example_lot.spec.yaml
    pixi run build
    ```

   It says `wrote example_lot.pgm/.yaml: 320 x 240 px, 80 x 60 m`.
3. Start Gazebo with the test lot: `pixi run sim world:=test_lot`. On a Mac, add
   `gui:=false`, then run `pixi run gz-window` and `pixi run rviz` in two more terminals.
4. In RViz, send a **2D Goal Pose** at about (30, 0): 30 m straight ahead, past the box.

**You should see** the planned path bend around your box. In the test on 10 October it
passed at y = 4.4 m, beside a box that ends at y = 3 m.

5. Put the map back: `git checkout src/drivers/aav_navigation/maps/`.

!!! note "Two things this teaches"
  - The box is only in the map, not in Gazebo's world. Nav2 avoids it because the map
    says so: that's how phase 3 works.
  - Leave room in front of an obstacle. The car turns no tighter than 2.86 m, and the
    costmap keeps 2 m of clearance, so a box 5 m ahead can't be swerved around. (The
    test tried it: Nav2 reported "collision ahead".)

!!! warning "Known problem, 10 October: the car doesn't finish this drive"
  In Gazebo the car follows the curve around the box, but overshoots the goal and ends
  about 6 m off. Nav2 then can't plan a way back, because the car only drives forward,
  so the goal fails. It's open work for the navigation team (N7, the lookahead). A
  straight 8 m goal on the empty map succeeds.

## Where the map sits on the Earth

The map frame is pinned to the ground by the **datum** in
`src/localization/aav_localization/config/navsat.yaml`:
- map (0, 0) is the datum's latitude and longitude;
- x points east and y points north.

So a point 20 m east and 5 m north of the datum is (20, 5) on the map, in Nav2 goals and
in RViz. The datum in the file now is a placeholder near Carleton.

To draw the real test site:
1. Pick the datum: a corner of the lot, or the start spot. Survey it with the GPS
   (average a few minutes of fixes) and put its latitude and longitude in `navsat.yaml`.
2. Measure the drivable area in metres east and north of it, with a tape, or by measuring
   on satellite imagery from the datum.
3. Write the spec: the size, then the blocked rectangles (buildings, curbs, parked cars).
4. Build the map and drive phase 3 in Gazebo first (`world:=test_lot` pairs with
   `example_lot`).

## A costmap is not a road map

The global costmap only says which cells may be driven on. Roads, junctions and routing
across a city are a separate kind of map: a road graph. Two tools handle that:
- **OSRM**, which the HUD already uses. It turns a destination into a route of
  latitude/longitude points. Those points can become a `follow_gps_waypoints` goal for
  Nav2 (see [hud.md](hud.md)).
- **Nav2's Route Server** (`nav2_route`). It's released for Jazzy, in Nav2 1.3.13 as of
  October 2026, and follows a hand-made graph of lanes or paths. Consider it if the test site becomes a set of fixed lanes.

For this year's goals (an empty costmap, then a pre-rendered test site) a grid map plus
GPS waypoints is enough.
