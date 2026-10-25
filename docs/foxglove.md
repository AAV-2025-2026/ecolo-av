# Watch from a laptop: Foxglove and Lichtblick

Watch the car, or a simulator, from any laptop. No ROS on the laptop: one app, one
WebSocket. Built in on 24 October (Ben asked on 11 Oct; go-ahead 24 Oct).

```text
  car or simulator                                    your laptop
  ROS topics ──> foxglove_bridge (port 8765) ~~WiFi~~> Lichtblick or Foxglove
                 only the small topics                 + a layout from tools/foxglove/
```

## The two apps

| | Lichtblick | Foxglove |
|---|---|---|
| What | the open-source fork of Foxglove Studio, kept by BMW | the company's own app, newer |
| Licence | MPL-2.0: free, open source | proprietary: a free plan with an account |
| Account | none | needed |
| Get it | github.com/lichtblick-suite/lichtblick, Releases (Mac: `...-mac-universal.dmg`) | foxglove.dev/download |
| Our pick | ✅ the default (our rule: open source first, Ben, 15 Oct) | works the same way |

The bridge itself, `foxglove_bridge`, is MIT and already in our Pixi environment.

## Connect from a Mac: 3 steps

| Step | Do |
|---|---|
| 1 | Start a bridge: `pixi run sim foxglove:=true` (or `bench`, `carla-car`); on the car it runs already (the Orin's `foxglove` part) |
| 2 | In the app: **Open connection → Foxglove WebSocket**, then `ws://localhost:8765` (a simulator here) or `ws://<the Orin's IP>:8765` (the car; `pixi run net-map` finds it) |
| 3 | **Layouts → Import from file**: pick one from `tools/foxglove/` (below) |

Lichtblick's Mac app isn't notarized: the first time, right-click it in Applications →
Open → Open ([Your Mac](mac.md#watch-without-ros-lichtblick)).

## Which layout

| Layout | File | Shows |
|---|---|---|
| **Driving** | `tools/foxglove/driving.json` | 3D view following the car: its model, the lidar's scan, the local costmap, Nav2's plan and goal, the radar and its clusters, the camera's obstacles, the stop zone. The camera preview. Speed and steering, measured against commanded. E-stop, the sensor watchdog, the output gate |
| **Sensors health** | `tools/foxglove/sensors-health.json` | every `/diagnostics` status: the watchdog's per sensor with its **rate (Hz) and longest gap**; EKFs, twist_mux, the camera streams. Whether every sensor comes from the right source. A timeline of stops and e-stops |
| **Map** | `tools/foxglove/map.json` | the car on a street map: the EKF's position (blue) and the raw GPS (orange); fix or no fix; the street route's status |

!!! note "The map needs the internet"
    The map panel loads OpenStreetMap's tiles from the web. At the car with no internet,
    it shows the dots on a blank map.

## Where each bridge listens

| Started by | Listens on | A client may | Topics |
|---|---|---|---|
| `pixi run sim foxglove:=true` | 127.0.0.1 (this computer) | watch, send a goal, drive (`/drivers/keyboard/cmd_vel`), e-stop | WiFi list, plus the camera preview |
| `pixi run bench foxglove:=true` | 127.0.0.1 | the same | the same |
| `pixi run carla-car ... foxglove:=true` | 127.0.0.1: from a Mac, `ssh -L 8765:127.0.0.1:8765 <the CARLA computer>`, then `ws://localhost:8765` | the same | the same |
| the car (`foxglove` part: Orin, `all`) | every network the Orin is on | **watch only**: anyone on the car's WiFi reaches it | WiFi list |

One file does it for all of them: `src/aav_bringup/launch/foxglove.launch.py`, with the
list in `src/aav_bringup/config/foxglove_bridge.yaml`.

## Bandwidth: the WiFi list

The bridge sends only what a panel opens. The danger is one click on a big topic over the
car's WiFi, about 2.5 MB/s for every laptop together ([Bandwidth](bandwidth.md)). So the
list leaves these out:

| Left out | Size | Watch instead |
|---|---|---|
| raw cameras, `.../image_raw`, and their JPEGs | 93 MB/s; 4.5 MB/s | `/perception/camera/front_left/preview/compressed`: 320 px, once a second, a few kB |
| the detector's and lane finder's pictures | raw pictures | the preview (the car's has the boxes drawn on) |
| the lidar's points and packets | ~7 MB/s | `/sensors/lidar/scan`, 3 kB |
| Nav2's costmap layers one by one | 40-640 kB each | `/local_costmap/costmap`, all layers in one |

Measured, 24 Oct, in Gazebo's road world, while Nav2 drove: **all three layouts open at
once: 170 kB/s (1.4 Mbit/s)**. The costmap is the biggest part (64 kB/s), then the odometry
and the scan. On a cable, `ros2 launch aav_bringup foxglove.launch.py foxglove_topics:=all`
lets everything through.

## Check it without the app

```bash
pixi run layout-check                       # the sim here: is every topic served?
pixi run layout-check ws://192.168.1.140:8765 --data   # the car: and how much each sends
```

## Tested

| What | Result |
|---|---|
| `pixi run sim world:=road foxglove:=true`, 24 Oct, own domain | bridge on 127.0.0.1 only; 23 of 26 layout topics served, 3 off as expected (ghost, street route); the camera preview at 1 Hz, 13-16 kB/s |
| A goal sent through the bridge (as Lichtblick's 3D panel does) | Nav2 planned and the car drove 20 m |
| `pixi run bench foxglove:=true` | 22 of 26 served; the bench has no lidar unless `lidar:=true` |
| A watch-only bridge (the car's settings) | publishing refused: "Server does not support clientPublish" |
| The layouts in the Lichtblick app | the setting names were checked against Lichtblick 1.29's own code; not yet opened in the app by a person |
| The car | **untested** |
