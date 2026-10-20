# Perception: cameras, RF-DETR and YOLO, stop signs, lanes and radar

What the car sees, and what it does about it. All of it runs on the bench today. On the
car, it waits for the cameras (Q22) and the Orin's move to JetPack 7.2 (Q24).

## The chain

```
camera ─► yolo_detector ─► /perception/detections ─► stop_sign_watcher ─► /perception/stop_sign
                                                                    (a lock on twist_mux)
lane finder (missing) ─► /perception/lane/geometry ─► control_interface ─► /drivers/ai/cmd_vel ─► twist_mux
radar ─► /sensors/radar/points ─► radar_clusters ─► /perception/radar/clusters, /perception/radar/cluster_boxes
```

![What the bench camera shows YOLO, about 5 m from the stop sign](img/bench-stop-sign.png)

| In the picture | What it is |
|---|---|
| The road, the sky and the sign | a drawing, not a photo: the bench's pretend camera (`mock_camera`) draws them from where the model car is. The sign grows as the car gets closer |
| The pink box | the real YOLO model (the stock one) found the sign: "stop sign", 0.90 = 90% sure. (Saved before RF-DETR became the default, 20 Oct; it draws a red box) |
| When | `pixi run -e ml bench-check --perception` saved it the moment the car stopped, about 5 m before the sign |

## The packages

| Package | From | Does | State |
|---|---|---|---|
| `aav_yolo` | 2024-25 `camera_ros2_ws` (`yolo_ros2`) | the detector (RF-DETR or YOLO): camera images in, `vision_msgs` detections out; and the stop-sign watcher | [[works]] on the bench, with either stock model |
| `aav_radar_clusters` | ours (Rust): a rewrite of the 2025-26 `Nav_Radar` C++ node | DBSCAN groups the radar's points into objects, with a box round each | [[works]] on the bench and in Gazebo |
| `aav_lane_geometry` | 2025-26 `Lane_Detection_ROS2` | lane keeping's steering half, as a driver on `/drivers/ai/cmd_vel` | [[works]] on a pretend lane. The line finder is [[missing]] |
| `aav_sensors` `cameras.launch.py` | 2024-25 `cameras` (the calibrations) | `usb_cam` with `left.ini` and `right.ini` | [[untested]] Linux only; the camera models are Q22 |

## Stop signs

The watcher turns the detector's boxes into a lock on twist_mux.

| State | When | The lock |
|---|---|---|
| Clear | no stop sign close enough | off |
| Stopping | a stop sign's box is 72 px tall or more, with a score of 0.5 or more | on, for 4 s: about 1 s to stop, then a 3 s wait |
| Passing | after the 4 s | off, and signs are ignored for 10 s, so the car can drive past this one |

- **The lock** has priority 30. It holds Nav2 (20) and the AI slot (10), and never a
  person (joystick 100, keyboard 90) or a test script (60, 50, 40).
- **It only stops the car.** It can't make it move.
- **It never expires on silence.** If the watcher dies while the lock is on, the car stays
  stopped.
- **On the bench**, Nav2 drove toward the sign at 25 m. The lock came on 4.7 m before it,
  the car stopped, waited, and went on to its goal 40 m away.
- **72 px** suits the bench camera (360 px high): about 3.5 m from the sign. Set
  `min_height_px` again for the real camera.

Last year, a stop sign set off the real e-stop, and the HUD cleared it every half second.
The lock keeps stop signs away from the e-stop.

## Models

### Two detectors, one switch

Since 20 Oct the detector runs **RF-DETR** (Ben: "Lets switch to RF-DETR... switch ... to
yolo with a parameter"). YOLO is one argument away. Both publish the same
`/perception/detections`, so the stop-sign watcher and the rest can't tell which ran.

```bash
pixi run detect                        # RF-DETR Nano (the default)
pixi run detect detector:=yolo         # YOLO11 nano
```

In a machine file: `detector: {detector: yolo}` under its `detector:` settings.

| `detector:=` | Model (empty `model:=`) | Licence | Why |
|---|---|---|---|
| `rfdetr` (default) | `models/rf-detr-nano.pth` | Apache-2.0 (Roboflow) | saw Gazebo's stop sign from 20 m, YOLO from 10 m; more people found ([Model comparison](model-comparison.md)) |
| `yolo` | `models/yolo11n.pt`, or its `.mlpackage` / `.engine` | AGPL-3.0 (Ultralytics) | smaller (6 MB), and its TensorRT engine for the Orin is written |

Tested 20 Oct on Ben's Mac (GPU, Metal), on the test stop-sign picture at 10 frames a second:

| | Found | Time per frame | `bench-check --perception` |
|---|---|---|---|
| RF-DETR Nano | stop sign, 0.96 | 32 ms | [[works]] the lock came on at 20.7 m (sign at 25 m); stood still; goal reached |
| YOLO11n | stop sign, 0.97 | 32 ms | [[works]] (earlier runs) |

`pixi run get-models` downloads both into `models/` (RF-DETR's is 366 MB: a training
checkpoint), each checked against its pinned checksum: a model file is a Python pickle,
so a wrong one could run code. Both know COCO's 80 classes, "stop sign" among them, so we
don't need the 2024-25 team's model to start. Another RF-DETR size: name the file after
it, such as `models/rf-detr-small.pth`, and pass `model:=`.

RF-DETR runs on PyTorch: CUDA (the Orin), Metal (a Mac) or the CPU. Its TensorRT engine
for the Orin is [[later]]: until then the Orin runs it through PyTorch on its GPU,
[[untested]].

### YOLO's three formats

One YOLO model, three formats. Each computer with a GPU runs its own (Ben, 10 Oct), and the
detector loads any of them. The machine file names the one to use:

| Format | Runs on | Make it with | Machine file |
|---|---|---|---|
| `.pt` | anything, with PyTorch | `pixi run get-models`, or the training | `all.yaml` |
| `.mlpackage` | Macs, with Core ML | `pixi run -e ml export-coreml`, on a Mac | `laptop.yaml` |
| `.engine` | the Orin, with TensorRT | `python3 tools/build_engine.py`, on the Orin itself | `orin.yaml` |

### Core ML, on a Mac

- `pixi run -e ml export-coreml` makes `models/yolo11n.mlpackage` from
  `models/yolo11n.pt`, and downloads the `.pt` first if it's missing.
- Another model: `pixi run -e ml export-coreml models/best.pt`.
- On an M4 Max the export takes 2 s; the whole command 3 to 10 s.
- [[works]] The result found the test stop sign at 0.97.

### TensorRT, on the Orin

An engine runs only on the GPU and the TensorRT version that built it. So it's built
on the Orin, once it's on JetPack 7.2 (Q24):

1. Install NVIDIA's PyTorch for Jetson (not PyPI's), then `pip install ultralytics onnx`.
   In a venv, make it with `--system-site-packages`, so it sees JetPack's TensorRT.
2. Run `python3 tools/build_engine.py` in the repo, with JetPack's `python3`, not
   Pixi's. It checks first, and says what's missing.
3. It writes `models/yolo11n.engine`: half precision (FP16), 640 px.
   `car.launch.py machine:=orin` loads it.

[[untested]] It needs the Orin: here it only checks, and stops.

The 2024-25 team's own model, `best.pt`, is in no repo: their code loaded it from
`~/Yolo/Capstone/runs/detect/train7/weights/best.pt` on someone's computer. It's
probably on the team's Linux machine with the NVIDIA card (Ben, 10 Oct), which can train
new models too. Ultralytics' models and code are licensed AGPL-3.0.

## Better models to try

The 2024-25 model learned one label from the team's own pictures. Open models trained on
far more pictures may do better:

| Job | Open models |
|---|---|
| Everyday objects, stop signs included | RF-DETR (ours now), YOLO11 and YOLO26 (`detector:=yolo`), RT-DETR |
| Anything named in words, like "traffic cone" | YOLO-World, Grounding DINO, OWLv2 |
| Lane lines and the drivable area | YOLOPv2, TwinLiteNet |
| Distance from one camera | Depth Anything V2 |

- **The fair test:** record the car's cameras once, then run each model on the same
  recording.
- **Several at once:** any number of nodes can read the same camera topic; each
  publishes its own result.
- **Licences:** check each one before it goes on the car.

## Where it runs

| Machine | How | Speed (YOLO11 nano, 640 px) |
|---|---|---|
| A Mac with Apple silicon | `pixi run -e ml`: PyTorch on the GPU through Metal | 7.7 ms a frame; 26 ms in the node, with the picture drawn and sent |
| The same Mac, Core ML | a `.mlpackage`: Apple's version of TensorRT | 4.3 ms for the model alone, on the GPU |
| A Linux PC | `pixi run -e ml`: PyTorch on the CPU (CUDA builds later) | not measured |
| The Orin, on JetPack 7.2 | JetPack's CUDA 13.2.1 and TensorRT 10.16.2, not Pixi's | not yet |

The detector runs as `python3 -m aav_yolo.detector`, so it uses the `python3` of the
environment that starts it: the `ml` environment's PyTorch on a laptop, JetPack's on the
Orin.

### One GPU setting for every computer

`auto`, the default, picks the GPU the computer has. The other values are PyTorch's own
names, passed on as they are.

| `device:=` | On the Orin, or an NVIDIA card | On a Mac |
|---|---|---|
| `auto` (the default) | CUDA | Metal |
| `cuda`, `cuda:N` | CUDA: the first card, or card N | an error: use `auto` or `mps` |
| `mps` | an error: use `auto` or `cuda` | Metal |
| `cpu` | the CPU | the CPU |

- A name PyTorch doesn't know, such as `gpu` or `metal`, is an error too. It lists the
  names above.
- A `.mlpackage` (Core ML) or an `.engine` (TensorRT) ignores the setting: each picks its
  own hardware.
- MLX, Apple's own machine-learning library, isn't needed for YOLO: Metal, through
  PyTorch or Core ML, is the Mac's fast path. MLX could join the `ml` environment later,
  for training or for other models.

### One detector per computer, and WiFi

| Setting | Does |
|---|---|
| `node_name:=yolo_detector_macbook` | the node's name. Each computer with a GPU runs its own detector, under its own name: `car.launch.py` calls it `yolo_detector_<machine>`. All of them publish on `/perception/detections` |
| `compressed:=true` | reads `/sensors/camera/front_left/image_raw/compressed`, the JPEG pictures `usb_cam` already publishes. Raw pictures are too big for WiFi |

From a Mac on the car's network, by hand:
`pixi run detect node_name:=yolo_detector_macbook compressed:=true`.

### The ml environment

A separate Pixi environment, so nobody downloads PyTorch unless they want it: PyTorch
2.13, Ultralytics 8.4, coremltools 9 (Macs only) and NumPy 2.3.

- Ultralytics' Core ML export needs NumPy 2.3.5 or older, so the environment pins it.
- conda-forge's torchvision has no Metal version of one step (NMS), so
  `PYTORCH_ENABLE_MPS_FALLBACK=1` runs that step on the CPU.
- `YOLO_AUTOINSTALL=false`: Ultralytics must never pip-install into the environment.

## Lane keeping

Two nodes, from the camera to the wheels. `lane_finder` (ours) finds the lane;
`control_interface` (the 2025-26 team's) steers by it.

```
/sensors/camera/front_left/image_raw ─► lane_finder ─► /perception/lane/geometry ─► control_interface ─► /drivers/ai/cmd_vel
```

![The bench camera, and what lane_finder found in it](img/lane-finder.png)

| In the picture | What it is |
|---|---|
| Left | the bench camera: the car 0.3 m left of the lane's centre |
| Right | the bird's-eye view: the road from above, 4 m ahead (bottom) to 16 m (top) |
| Yellow | the paint it found |
| Boxes | the sliding windows: green found paint |
| Blue, red | the left and right lines it fitted |
| Green line, white line | the lane's centre, and the car's own line |

### The finder

Classic OpenCV, no model. A model can replace it later, on the same topic.

| Step | What it does |
|---|---|
| 1. Bird's-eye view | warps the picture into a map of the road seen from above: 4-16 m ahead, 4 m either side, 5 cm a pixel. From the lens (`/sensors/camera/front_left/camera_info`) and the camera's place and tilt (`vehicle.yaml`). It takes the road to be flat |
| 2. Paint | a pixel is paint when it's brighter than the road on both sides |
| 3. Sliding windows | 12 windows climb each line, from where it starts near the car |
| 4. Fit | a curve per line, `y = a x² + b x + c`, in metres, in `base_link` |
| 5. The answer | the car's offset, the lane's width, each line's radius, and how sure it is |

- **Speed:** 0.8 ms a picture on Ben's MacBook Pro (M4 Max), 1.2 ms in the node.
  [[untested]] on the Orin, whose cores are slower: expect a few ms.
- **The code:** `src/perception/aav_lane_finder`. `birds_eye.py` and `lane_lines.py`
  hold the maths, with no ROS, and 21 tests, most on pictures of known lanes: straight,
  off centre, turned, curved, one line, none. `lane_finder.py` is the node.

### What it sends: /perception/lane/geometry

| Field | Means |
|---|---|
| `vehicle_offset_m` | the car from the lane's centre, 3 m ahead (m). + = the car is left of the centre, so it steers right |
| `left_poly_a`, `_b`, `_c`, and the same for `right_` | each line as `y = a x² + b x + c` (m), in `base_link`: x forward, y left |
| `left_curvature_m`, `right_`, `mean_` | the radius (m). 9999 = straight, or not seen |
| `curve_direction` | +1 bends left, -1 right, 0 straight |
| `lane_width_m` | between the lines (m). With one line, the last width seen |
| `left_confidence`, `left_lane_detected`, and the same for `right_` | 0 to 1; a line counts from 0.3 |
| `steering_hint` | a pure-pursuit wheel angle to the centre (rad, + = left). control_interface doesn't use it |

- **One line:** the centre is half a lane beside it.
- **No lines:** nothing detected, so control_interface slows down and stops.
- **Why 3 m ahead:** an offset at the rear axle says nothing about which way the car
  points. On the bench, measured there, the car weaved 0.3 m either side and ran off the
  lane within 20 s. 3 m ahead, it comes back in about 6 s, 2 cm past the centre at most.

### The steering: control_interface

- It steers with a PID on the offset, through five states (keep, change, committed,
  stopping, resuming).
- It publishes on `/drivers/ai/cmd_vel`, the mux's slot for a learned driver. Every other driver
  outranks it.
- It asks for 2 m/s; ego caps it at the car's 1 m/s.

### On the bench

| Command | Does |
|---|---|
| `pixi run bench lane:=true nav:=false start_y:=0.3` | lane keeping on the pretend camera, from 0.3 m left of the centre |
| `pixi run bench lane:=fake` | control_interface on a pretend lane, without the camera |
| `pixi run bench-check --lane` | the same, measured: [[works]] back within 5 cm of the centre in about 6 s, 2 cm past it at most |
| `pixi run bench lane:=true nav:=false bend_radius:=60` | a 60 m bend to the left, from 30 m on: [[works]] within 8 cm of the centre, 4-5 cm inside it round the bend |

More in [Bench mode](bench.md).

### Next

| Item | Waits on |
|---|---|
| The real camera's place, tilt and lens, in `vehicle.yaml` and its calibration | the cameras (Q22) |
| Tune the paint test on real pictures: shadows, worn paint, glare | a recording from the car |
| Time it on the Orin | the reflash (Q24) |
| Hills and bumps: the warp takes the road to be flat | later, with the IMU's pitch |

## Radar clustering

- `radar_clusters` runs DBSCAN on `/sensors/radar/points`. Points within 0.8 m join a cluster,
  and a cluster needs 15 points (5 on the bench).
- It publishes the clustered points, coloured, and a box round each cluster, for RViz.
- It is Rust (`aav_radar_clusters`), since 15 Oct. It gives the 2025-26 C++ node's
  clusters and boxes, bit for bit (94 recorded clouds), with a few fixes: eps is a real
  distance, noise is left out, old boxes are cleared. Its `PROVENANCE.md` lists them.
- The C++ package's other programs (filters, ICP, an OctoMap) were demos, never launched:
  they went with it.
- [[later]] Next: the radar's points into the local costmap (the ObstacleLayer, written and
  switched off) and `collision_monitor`.

## On the car

`car.launch.py` starts perception as parts, like the rest of the car. Each machine file
turns them on where they run ([Platforms](platforms.md#on-the-car-what-runs-where)):

| Part | Starts | Where |
|---|---|---|
| `camera` | `usb_cam` → `/sensors/camera/front_left/image_raw` (Linux only) | off everywhere until the cameras are known (Q22) |
| `detector` | YOLO, as `yolo_detector_<machine>` → `/perception/detections` | the Orin. The laptop's is off until it reads compressed images |
| `stop_signs` | `stop_sign_watcher` → `/perception/stop_sign` | one per car, next to the mux: the Orin |
| `radar_clusters` | DBSCAN on `/sensors/radar/points` | off until the radar is on the car |
| `camera_obstacles` | the boxes as points on the road → `/perception/camera_obstacles`, for Nav2's costmap | off until the cameras are calibrated (Q22); then next to `navigation`: the Orin |
| `lane` | to do: the lane finder, then lane keeping | the lane finder is being written |

- Every detector publishes on `/perception/detections`, so the watcher hears them all.
- A detector needs PyTorch: JetPack's on the Orin, the `ml` environment on a laptop
  (`pixi run -e ml car laptop`). Without it, or without its model file, the part is
  skipped with a warning, and the rest of the car starts.

- **From a Mac:** a Mac on the car's network can run the detector on the car's cameras.
  Raw images are too big for WiFi, so the cameras should also publish compressed ones.
- **Into the costmap:** `camera_obstacles` (in `aav_yolo`) puts each box where it meets
  the road: its bottom edge, seen through the camera's lens from its height and tilt
  (`vehicle.yaml`, through TF). The local costmap's camera layer marks those points. Off
  until the cameras are calibrated (Q22); then turn the `camera_obstacles` part on in the
  machine file that runs `navigation`, the Orin's. [Costmaps](costmaps.md) has the details.

  | Counts | Never counts |
  |---|---|
  | people, bicycles, cars, motorcycles, buses, trucks, cats, dogs, horses (`config/camera_obstacles.yaml`) | stop signs, even if listed: they lock the mux |

  Each message's camera is its `header.frame_id`, so every detector, on any camera, is
  read the same way.

### Isaac ROS (NVIDIA)

- **Not needed for the detector:** it already uses TensorRT on the Orin, through
  Ultralytics.
- **Jazzy:** Isaac ROS 4.6 (18 Aug 2026) is the last release for Jazzy, and supports the
  Orin on JetPack 7.2. Isaac ROS 5.0 (21 Sept 2026) moved to ROS 2 Lyrical.
- **Later, maybe:** nvblox (a costmap from cameras), visual SLAM and stereo depth. It runs
  in NVIDIA's Docker containers, not in Pixi, and has no Mac version: it needs CUDA.
  [Releases](https://nvidia-isaac-ros.github.io/releases/index.html)

## Still to do

| Item | Waits on |
|---|---|
| Find `best.pt` and the training pictures: probably on the team's NVIDIA Linux machine | SSH to it: later (Ben, 10 Oct) |
| Back up the Orin: the 2025-26 detector lives only there | before any reflash |
| The line finder | someone: classic OpenCV, or a model |
| The cameras' models and udev names | Q22 |
| `min_height_px` for the real camera | the cameras |
| TensorRT on the Orin | the reflash (Q24) |
| The radar into the costmap | the ObstacleLayer settings |
