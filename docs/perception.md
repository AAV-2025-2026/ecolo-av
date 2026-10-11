# Perception: cameras, YOLO, stop signs, lanes and radar

What the car sees, and what it does about it. All of it runs on the bench today. On the
car, it waits for the cameras (Q22) and the Orin's move to JetPack 7.2 (Q24).

## The chain

```
camera ─► yolo_detector ─► /perception/detections ─► stop_sign_watcher ─► /perception/stop
                                                                    (a lock on twist_mux)
lane finder (missing) ─► /lane_geometry ─► control_interface ─► /cmd_vel/ai ─► twist_mux
radar ─► /radar/points ─► radar_clusters ─► /radar/clusters, /radar/cluster_boxes
```

![What the bench camera shows YOLO, about 5 m from the stop sign](img/bench-stop-sign.png)

| In the picture | What it is |
|---|---|
| The road, the sky and the sign | a drawing, not a photo: the bench's pretend camera (`mock_camera`) draws them from where the model car is. The sign grows as the car gets closer |
| The pink box | the real YOLO model (the stock one) found the sign: "stop sign", 0.90 = 90% sure |
| When | `pixi run -e ml bench-check --perception` saved it the moment the car stopped, about 5 m before the sign |

## The packages

| Package | From | Does | State |
|---|---|---|---|
| `aav_yolo` | 2024-25 `camera_ros2_ws` (`yolo_ros2`) | the detector: camera images in, `vision_msgs` detections out; and the stop-sign watcher | [[works]] on the bench, with the stock model |
| `aav_object_detection` | 2025-26 `Nav_Radar` (`object_detection`) | DBSCAN groups the radar's points into objects, with a box round each | [[works]] on the pretend radar |
| `aav_lane_geometry` | 2025-26 `Lane_Detection_ROS2` | lane keeping's steering half, as a driver on `/cmd_vel/ai` | [[works]] on a pretend lane. The line finder is [[missing]] |
| `aav_sensors` `cameras.launch.py` | 2024-25 `cameras` (the calibrations) | `usb_cam` with `left.ini` and `right.ini` | [[untested]] Linux only; the camera models are Q22 |

## Stop signs

The watcher turns the detector's boxes into a lock on twist_mux.

| State | When | The lock |
|---|---|---|
| Clear | no stop sign close enough | off |
| Stopping | a stop sign's box is 72 px tall or more, with a score of 0.5 or more | on, for 4 s: about 1 s to stop, then a 3 s wait |
| Passing | after the 4 s | off, and signs are ignored for 10 s, so the car can drive past this one |

- **The lock** has priority 30. It holds Nav2 (20) and the AI slot (10), and never a
  person (joystick 100, remote 90) or a test script (50, 40).
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

Model files stay out of git, in `models/`. `pixi run get-models` downloads the stock
YOLO11 nano model (5.6 MB, its checksum pinned). It was trained on the COCO dataset, and
"stop sign" is one of its 80 classes, so we don't need last year's model to start.

| Format | Runs on | Make it with |
|---|---|---|
| `.pt` | anything, with PyTorch | the training |
| `.mlpackage` | Macs, with Core ML | `pixi run -e ml yolo export model=models/yolo11n.pt format=coreml` |
| `.engine` | the Orin, with TensorRT | `yolo export model=models/yolo11n.pt format=engine`, on the Orin itself |

The 2024-25 team's own model, `best.pt`, is in no repo: their code loaded it from
`~/Yolo/Capstone/runs/detect/train7/weights/best.pt` on someone's computer. It's
probably on the team's Linux machine with the NVIDIA card (Ben, 10 Oct), which can train
new models too. Ultralytics' models and code are licensed AGPL-3.0.

## Better models to try

The 2024-25 model learned one label from the team's own pictures. Open models trained on
far more pictures may do better:

| Job | Open models |
|---|---|
| Everyday objects, stop signs included | YOLO11 (ours now), RT-DETR, RF-DETR |
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

| `device:=` | On the Orin, or an NVIDIA card | On a Mac |
|---|---|---|
| `auto` (the default), `gpu`, `cuda`, `metal` or `mps` | CUDA | Metal |
| `cpu` | the CPU | the CPU |
| `cuda:1` | the second NVIDIA card | Metal |

- So `cuda` on a Mac means Metal: the Mac's GPU, through PyTorch.
- A `.mlpackage` (Core ML) or an `.engine` (TensorRT) ignores the setting: each picks its
  own hardware.
- MLX, Apple's own machine-learning library, isn't needed for YOLO: Metal, through
  PyTorch or Core ML, is the Mac's fast path. MLX could join the `ml` environment later,
  for training or for other models.

### The ml environment

A separate Pixi environment, so nobody downloads PyTorch unless they want it: PyTorch
2.13, Ultralytics 8.4, coremltools 9 (Macs only) and NumPy 2.3.

- Ultralytics' Core ML export needs NumPy 2.3.5 or older, so the environment pins it.
- conda-forge's torchvision has no Metal version of one step (NMS), so
  `PYTORCH_ENABLE_MPS_FALLBACK=1` runs that step on the CPU.
- `YOLO_AUTOINSTALL=false`: Ultralytics must never pip-install into the environment.

## Lane keeping

- `control_interface` reads `/lane_geometry` (the lane lines as polynomials, the car's
  offset and the curvature) and steers with a PID through five states (keep, change,
  committed, stopping, resuming).
- It publishes on `/cmd_vel/ai`, the mux's slot for a learned driver. Every other driver
  outranks it.
- Its base speed is 2 m/s; ego caps it at the car's 1 m/s.
- [[missing]] **The line finder**: whatever turns the camera's picture into
  `/lane_geometry`. It isn't in any repo. Until then, `fake_lane_geometry_pub` stands in
  (`bench.launch.py lane:=true`).

## Radar clustering

- `radar_clusters` runs DBSCAN on `/radar/points`. Points within 0.8 m join a cluster,
  and a cluster needs 15 points (5 on the bench).
- It publishes the clustered points, coloured, and a box round each cluster, for RViz.
- The package's other programs (filters, ICP, an OctoMap) are the 2025-26 team's demos,
  built but not launched.
- [[later]] Next: the radar's points into the local costmap (the ObstacleLayer, written and
  switched off) and `collision_monitor`.

## On the car

`aav_bringup perception.launch.py` starts the camera, the detector, the watcher and the
radar clustering, next to `car.launch.py`, on the Orin. When `car.launch.py` next changes,
they become parts in its machine files.

- **From a Mac:** a Mac on the car's network can run the detector on the car's cameras.
  Raw images are too big for WiFi, so the cameras should also publish compressed ones.
- **Into the costmap:** a camera detection needs a distance first (a stereo pair, a depth
  model, or the camera's height above a flat road). Then it's a point on the ground, and
  Nav2's costmap marks it like a radar or lidar point. Stop signs never go in the
  costmap: they lock the mux.

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
