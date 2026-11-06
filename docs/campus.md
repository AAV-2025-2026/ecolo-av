# The campus

Carleton in Gazebo, on one Nav2 costmap, with a guessed NDT map. It's for practice while the
hardware catches up (Ben, 5 Nov). Nothing here has met the real campus yet.

```sh
pixi run campus                                       # builds maps/campus/ (about 10 s)
pixi run sim world:=campus reversing:=false screen_cubes:=true ndt:=true gui:=false rviz:=false
pixi run dev-window --live --ndt-map maps/ndt/campus.pcd   # in a second terminal
```

Click a road or lot on the map, then confirm, as in any world. The car starts in lot P4,
because the datum itself is on a station shelter.

## What's real and what's guessed

| From OpenStreetMap | Guessed by `tools/campus_world.py` |
|---|---|
| where roads, lots, buildings and trees are | how tall most buildings are (529 of 574) |
| their shapes | where kerbs run (9.8 km: 0.30 m round the lots) |
| many road widths | other road widths, tree sizes, trees inside woods |
| | all the looks: pavement, grass, brick, stone |

The data is (c) OpenStreetMap contributors, under the ODbL, so anything showing it must say so.
`maps/` isn't in git: `pixi run campus` makes it again.

**Google:** being students doesn't change Google's terms, which limit copying their maps into
another map. So the world is built from OpenStreetMap. Your own tape measurements and points
you read by hand are for checking it.

## What it makes

| File | What it is |
|---|---|
| `maps/campus/campus.sdf`, `meshes/`, `textures/` | the world: 355,000 triangles, bump-mapped |
| `maps/campus/campus.pgm`, `.yaml` | one Nav2 map: 1.6 x 1.6 km at 0.25 m (6400 x 6400 cells) |
| `maps/campus/place.yaml` | where the car starts, what went in, the credit |
| `maps/ndt/campus.pcd` | NDT's map, **a guess**: points on the same shapes |

**One costmap, no segments.** It works on a Mac: only roads and lots are free. Gazebo held
real time (0.98-1.01) and the window about 100 fps. Nav2's planner loop runs at about 8 Hz, not
the 20 Hz it wants, and warns about it in the console. Paths and grass are blocked: the car
stays on roads and lots.

## What was measured (Gazebo, 5 Nov)

| Check | Result |
|---|---|
| Nav2 goal from P4, 40 m | reached |
| EKF against the truth | within 0.36 m |
| NDT against the truth, on the guess | within 0.12 m (near buildings, 60 s) |
| NDT on a map recorded on that road | within 0.11 m |

**This doesn't show the real campus will work.** The guess is made from the same shapes as the
world, so of course it fits here.

## NDT's score floor

`ndt.yaml`'s 2.3 is the test lot's, with walls close by. On the campus, fits at the true place
score 1.73-1.94 on the guess, and 2.00-2.31 on a recorded map. So this world uses 1.5.

**Not measured:** how high a *wrong* pose scores here. Until it is, leave `ndt_ekf` off on the
campus: NDT is watched, and doesn't steer the estimate.

## Found along the way

| Finding | What to do |
|---|---|
| With `reversing` on, the car backs a long way to a goal behind it, at 0.5 m/s | use `reversing:=false` here; a decision for later |
| Kerbs sit at the cubes' 0.3 m floor | TODO 119: test it now this world exists |
| A lot's middle is far from anything | the lidar sees little there: NDT may lose the fit |
| Lidar cubes reach 30 m, NDT's points 45 m | so the top right can look empty in open space |

## Next: the real lidar drive

A drive suggests and a person accepts (Ben, 5 Nov). The tools to record and build a map exist,
and were rehearsed here:

```sh
tools/record.sh --lidar
pixi run ndt-map --out maps/ndt/<place> build <bag> --poses /localization/odom/global
```

Not built yet: fitting a drive onto the outlines, the GPS offset, and approving changes in the
window.
