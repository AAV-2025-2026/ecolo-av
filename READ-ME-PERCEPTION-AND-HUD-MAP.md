# Perception models, the lidar, and a map on the HUD

Written 15 October 2026, for Ben. It answers:

1. YOLO, OpenCV, or the previous teams' trained models?
2. What do we do with the lidar? Can we just download a model?
3. Can the HUD show a map?

> **The short version**
> - **Use stock YOLO for objects** (already wired in): one model, run as TensorRT on the Orin and Core ML on a Mac. **Keep OpenCV for lane lines** (already done: under 1 ms a frame).
> - **The previous teams' trained model is lost** (`best.pt` was on someone's laptop) and knew one label. Start from stock, and train our own later only if the stock one fails on our recordings.
> - **Lidar: no model to start.** Put its points straight into Nav2's costmap and collision_monitor. Clustering next. A downloaded 3D detector last, and only if needed.
> - **A map on the HUD: yes.** The raylib HUD can draw offline map tiles with the car's GPS dot on top. Not built yet.

## 1. Camera perception: which tool for which job

| Job | Tool | Why | Status |
|---|---|---|---|
| Stop signs, people, cars, bikes, traffic lights | **YOLO11 nano**, stock, trained on COCO (80 classes) | one model for many objects; fast; runs on TensorRT and Core ML | ✅ bench, Gazebo road world; ❌ car |
| Lane lines | **OpenCV**, classic (`aav_lane_finder`) | no training; 0.78 ms a frame; easy to debug | ✅ bench |
| How far away is it? | the lidar or radar (see 3), not the camera | a camera alone guesses distance badly | - |

### What the previous teams trained

| Team | Model | Where it is now |
|---|---|---|
| 2024-25 | their own YOLO, `best.pt`, one label, from their own photos | **lost**: their code loaded it from `~/Yolo/Capstone/runs/...` on someone's computer. The training scripts came across; the pictures and weights didn't |
| 2022-23 | Colab notebooks for vision models (`Carleton-AAV/AI-Development-Scripts`) | notebooks only |

We don't know what they started from or how good it was. Stock YOLO11 already knows "stop
sign", so we start there.

### One model, three formats

| Computer | Format | Made by |
|---|---|---|
| Orin | `yolo11n.engine` (TensorRT, half precision) | `python3 tools/build_engine.py`, on the Orin itself |
| Mac | `yolo11n.mlpackage` (Core ML) | `pixi run -e ml export-coreml` |
| Anything | `yolo11n.pt` (PyTorch) | `pixi run get-models` |

Measured on a Mac: 7.7 ms a frame through PyTorch and Metal, 4.3 ms through Core ML.

### When to train our own

1. Record the car's cameras on a real drive (`tools/record.sh`).
2. Run stock YOLO on the recording. Count what it misses.
3. Only if it misses too much: label a few hundred of our frames and fine-tune YOLO11 from the stock weights. It's the same code, the same three formats.

Other open models worth a fair test on the same recording: RT-DETR and RF-DETR (objects),
YOLO-World (anything named in words, such as "traffic cone"), YOLOPv2 (lanes and drivable
area), Depth Anything V2 (distance from one camera). Check each licence first: Ultralytics'
YOLO is AGPL-3.0.

## 2. The cameras on the car: one thing to fix first

The photos show **ribbon (CSI) cameras** on the Pi 5s. Our camera driver, `usb_cam`, only
reads **USB** cameras. The camera Pis need a libcamera driver instead, such as `camera_ros`.
Friday's audit will show what the 2025-26 team ran there.

## 3. The lidar: three steps

| Step | What | Model? | Gives | Effort |
|---|---|---|---|---|
| **1. Points into Nav2** | the lidar's point cloud → the local costmap's obstacle layer, and collision_monitor's stop zone | no | "something is there, don't drive into it" | small: configuration, like the radar's |
| **2. Clusters** | group nearby points into objects (DBSCAN, as we already do for the radar) | no | boxes with a position and size | small: reuse `aav_radar_clusters` |
| **3. A 3D detector** | a downloaded model labels the points: car, person, cyclist | yes | labelled 3D boxes | big |

Step 1 is what keeps the car from hitting things, and it needs no model at all. Most
student and research cars stop there.

### "Can we download a random model?"

Yes, but it's step 3, and it comes with catches:

| Model family | Trained on | The catch |
|---|---|---|
| PointPillars | KITTI, nuScenes (car datasets) | trained on a different lidar, mounted differently: expect worse results on ours |
| CenterPoint | nuScenes, Waymo | heavier; wants a big GPU |
| NVIDIA TAO PointPillars | NVIDIA's data | built for TensorRT on Jetson: the best fit for the Orin |

### Camera + lidar together

The usual way: YOLO finds a box in the picture; the lidar points that fall inside that box
give its distance. That needs the camera and lidar **calibrated** to each other (where each
one sits on the car, and the camera's lens). It's a later step, after both run on the car.

### In Gazebo today

`pixi run sim world:=road lidar:=true` simulates a generic 16-beam lidar on the roof, on
`/sensors/lidar/points`. It's off by default: on a Mac, with YOLO running as well, the
simulation stalled. Step 1 can be built and tested there before the real lidar's model is
known.

## 4. A map on the HUD

### What exists

| Piece | Status |
|---|---|
| The 2025-26 Flutter app's map page (`flutter_map`) | written; it needs a tile server on the dash Pi, which isn't in git |
| `ottawa.db`: 606,628 places for the search box | `pixi run get-hud-map` |
| OSRM road routes | Docker on the dash Pi; data not in git |
| The raylib HUD (ours) | speed, e-stop, GPS panel, camera, topic health. **No map yet** |

### How the raylib HUD would draw one

```text
 map tiles (256 px squares, offline) ─► raylib textures ─► the map panel
 /localization/gps/fix ─► a dot and an arrow for the car
 the route (lat/lon points) ─► a line over the tiles
```

| Step | Does |
|---|---|
| 1 | Make offline **tiles** of the test area once: a folder of PNGs (zoom 15-19 covers a campus) |
| 2 | The HUD loads the tiles around the car as textures |
| 3 | lat/lon → tile pixel is a standard formula (Web Mercator) |
| 4 | Draw the car's dot, its heading, and the route on top |

- **Offline**, so it works without internet in the car.
- **The rules:** OpenStreetMap's own tile servers forbid bulk downloads. Render our own tiles from OSM data, or use a provider that allows offline use. Show "© OpenStreetMap contributors" on the screen, as the Flutter app does.
- **About a day's work** for a map panel with the car's position. Search and routing come after.

## 5. What to do, in order

| # | Task | Needs |
|---|---|---|
| 1 | Friday: what cameras, lidar and radar are really on the car, and what drives them | the audit |
| 2 | `camera_ros` instead of `usb_cam` on the camera Pis | step 1 |
| 3 | The lidar's points into Nav2 (step 1), first in Gazebo | nothing: can start now |
| 4 | Record a real drive; run stock YOLO on it; decide whether to train | the cameras on the car |
| 5 | The HUD's map panel with offline tiles | the test area chosen |
| 6 | Lidar clusters; then camera + lidar calibration | the lidar on the car |
