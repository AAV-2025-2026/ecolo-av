# tools/foxglove

Our three layouts for Foxglove and Lichtblick: the panels a laptop shows when it
watches the car (or the sim) through `foxglove_bridge`. How to connect:
`docs/foxglove.md`.

## Overview

A person imports a layout in the app: **Layouts → Import from file**. The app then
asks the bridge for each topic the panels show.

## Interface

| File | Layout | Shows |
|---|---|---|
| `driving.json` | Driving | 3D view following the car (model, lidar scan, local costmap, Nav2's plan and goal, radar, stop zone), the camera preview, speed and steering against commanded, e-stop, watchdog, output gate |
| `sensors-health.json` | Sensors health | every `/diagnostics` status: each sensor's rate and longest gap, EKFs, twist_mux, camera streams; the sensor watchdog's lock and state; the sensor mux's state ("every sensor as asked"); a timeline of the watchdog stop, the output gate, "sources ok" and the e-stop |
| `map.json` | Map | the car on a street map: the EKF's position and the raw GPS; fix or no fix; the street route's status |

Each file is the app's own JSON: `configById`, `globalVariables`, `userNodes`, `layout`.

Read by: the Foxglove and Lichtblick apps; `tools/layout_check.py`
(`pixi run layout-check`); `tools/car_day_check.py`.

## Invariants

- Exactly these three layouts (`tools/tests/test_foxglove_layouts.py`).
- Every topic a layout shows is in `docs/interfaces.yaml` (or is Nav2's own).
- Every topic gets through the bridge's WiFi list
  (`ros/bringup/aav_bringup/config/foxglove_bridge.yaml`, `topic_whitelist`).
- Rename a topic in the contract, and rename it here in the same change.

## Side Effects

None from the files. In the app, through a bridge on 127.0.0.1 (sim, bench), a person
may send a goal, drive or e-stop; the car's bridge is watch only (`docs/foxglove.md`).
The Map panel loads OpenStreetMap tiles from the internet.

## Verification

```sh
python3 -m pytest -q tools/tests/test_foxglove_layouts.py   # also in tools/test.sh
pixi run layout-check                       # against a running bridge (default: the sim here)
pixi run layout-check ws://192.168.1.140:8765               # the car's Orin
```
