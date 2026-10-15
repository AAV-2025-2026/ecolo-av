# Your Mac: run it, and drive the car

Three ways to use a Mac with the car. Use Pixi to run ROS on the Mac itself, and to
drive. Lichtblick only watches, but needs no setup. Ubuntu in a VM is the fallback.

## Three ways

| Way | Gives you | Setup |
|---|---|---|
| 1. ROS on the Mac, with Pixi | everything: keyboard driving, e-stop, RViz, rqt, the turtle, Gazebo | about 30 minutes and 7 GB, once |
| 2. Lichtblick or Foxglove, no ROS on the Mac | watching: 3D view, plots, topics, logs | install an app |
| 3. Ubuntu in a VM (UTM) | the same setup as the car's computers | about an hour; the 3D view is slower |

## Set up the Mac (once)

**1. Apple's command-line tools:** git and the C++ compiler. If they're installed
already, it says so.

```bash
xcode-select --install
```

**2. Pixi**, then open a new terminal:

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

**3. The code.** Clone it from GitHub. You need access to `zander1976/aav` (ask Ben),
and an SSH key on your GitHub account:

```bash
git clone git@github.com:zander1976/aav.git ~/aav
cd ~/aav
```

Later, `git pull` in `~/aav` fetches newer work.

**4. Install ROS and build:**

```bash
pixi install       # ROS 2 Jazzy: about 7 GB, the first time only
pixi run build     # our packages
```

**5. Check it:** `pixi run turtle` in one terminal and `pixi run keyboard` in another.
Hold `i` to drive.

## Join the car's network

!!! warning "The car must run Jazzy too"
  Today's car runs the 2025-26 software on ROS 2 Humble, and Humble and Jazzy don't
  mix. Put this stack on the car first: [Platforms](platforms.md) shows how, with or
  without a reflash.

| # | Do this | Why |
|---|---|---|
| 1 | Join the car's own WiFi router | campus WiFi blocks the traffic ROS uses to find other computers |
| 2 | `export ROS_DOMAIN_ID=42` in each terminal | ROS only talks within one domain. Ours is 42, so it never mixes with the 2025-26 software (`pixi run net-map` shows which domains theirs uses) |
| 3 | Leave the middleware alone | the Mac's Pixi install and Ubuntu both use Fast DDS |
| 4 | When macOS asks whether `python3` or `rviz2` may accept incoming connections, click Allow | otherwise the firewall blocks the car's replies |
| 4b | System Settings → Privacy & Security → **Local Network**: turn on your terminal app (Terminal, iTerm, VS Code) | since macOS 15, apps need this to reach other machines on the network. macOS asks once; if you said no, nothing on the car answers |
| 5 | Run `pixi run doctor` | it checks steps 1–4, and whether it can see the car, and says what to fix |

### See what's on the network: `pixi run net-map`

It lists every machine on the network you've joined: IP, name, MAC, a guess at the maker
(Raspberry Pi, NVIDIA, Espressif = an ESP32), open ports (SSH, web, Foxglove), and the
**ROS domains each machine is talking in**. It needs no ROS and no login, and changes
nothing: it pings, knocks on a few ports, and listens.

```bash
pixi run net-map                       # about 25 s
pixi run net-map --listen 30 --out ~/net-map.md
```

- It hears **Humble and Jazzy alike**: it reads the raw discovery packets, not ROS. So it
  shows which domain the 2025-26 software uses without logging in to anything.
- "No ROS discovery heard" with ROS running means multicast isn't reaching the Mac:
  WiFi routers often drop it. Try Ethernet, or `ROS_STATIC_PEERS` below.
- On a Mac, programs started by Python see an empty ARP table (Local Network privacy),
  so `net-map` reads it from bash. If the MAC column is empty, check step 4b.
- Tried on Ben's home network, 15 Oct: 13 machines in 25 s, and a test talker on domain
  77 heard. **Not yet tried on the car.**

### The car's own topics

`pixi run tools/ros.sh ros2 topic list` should then list the car's topics. If they don't
show up:
- Check that the Mac and the car's computers have addresses on the same network.
- Name the computers directly: add `export ROS_STATIC_PEERS=<the Orin's IP>` on the Mac,
  and the Mac's IP on the Orin. This is Jazzy's way around blocked multicast.
- Turn off the Mac's firewall for a minute, to see whether it's the cause.

!!! note "The stand-ins stay on your Mac"
  `pixi run turtle`, `sim`, `bench` and `view` only talk to this computer, whatever your
  domain and peers say. So a pretend car never meets the real one. The keyboard, `estop`
  and RViz do reach the car: that's their job. `pixi run keyboard --local` keeps the
  keyboard on your Mac too.

If RViz shows the car but drops data ("extrapolation" errors), or the doctor says the
clock is off: the car's computers keep the time (the Orin serves it, see
[Platforms](platforms.md)). Set the Mac from the Orin once with
`sudo sntp -sS <the Orin's IP>`.

## Drive and watch from the Mac

| Want | Run this on the Mac |
|---|---|
| Drive with the keyboard | `pixi run keyboard` |
| Stop everything | `pixi run estop`, then `pixi run estop-clear` when it's safe |
| The 3D view: map, costmaps, path, the car | `pixi run rviz` |
| Nodes and topics, live | `pixi run graph` |
| Be the safety driver's joystick laptop | `pixi run car laptop` |

!!! warning "Driving the real car"
  The keyboard has priority 90. The safety driver's joystick (100) and the hardware
  e-stop always win. Keep both in someone's hands whenever the Mac drives.

## ML on your Mac, against the bench

On the car, the laptop runs its own detector (`yolo_detector_laptop`, Core ML) on the
camera's JPEG pictures, which suit WiFi. At home, the bench plays the car:

| Terminal | Run | What it is |
|---|---|---|
| 1 | `pixi run bench` | the car's software, with stand-ins for the hardware |
| 2, once | `pixi run -e ml export-coreml` | makes `models/yolo11n.mlpackage`, the Core ML model (12 s) |
| 2 | `pixi run -e ml laptop-bench` | your laptop's parts, as on the car: the joystick, and its own detector |

- **See it:** `pixi run graph` shows `yolo_detector_laptop` reading
  `/sensors/camera/front_left/image_raw/compressed`, and publishing `/perception/detections`.
- **Stop at the sign too:** start the bench with `pixi run -e ml bench perception:=true`. It
  runs its own detector and the stop-sign watcher, as the Orin would; the watcher then hears
  both detectors, as on the car.
- **Tried on Ben's Mac, 11 Oct:** Core ML took 21 ms a picture and kept up with all 10
  pictures a second. It saw the bench's stop sign from 20 m (score 0.52), and at 0.95 from
  5 m.

## Watch without ROS: Lichtblick

The car runs `foxglove_bridge`, so any Foxglove-compatible viewer can watch it over one
WiFi connection, with no ROS on the Mac.
- **Lichtblick:** free, open source, no account. Download the Mac app from
  github.com/lichtblick-suite/lichtblick (releases).
- **Foxglove:** the same idea; its free plan needs an account.

In either app: Open connection → Foxglove WebSocket → `ws://<the Orin's IP>:8765`.

## Gazebo on a Mac

On macOS, Gazebo's window has to run as a separate program from the simulator.
`pixi run sim` starts both, and points the window's camera at the car:

```bash
pixi run sim               # the simulator, its window, and RViz
pixi run gz-window         # opens the window again, if you closed it
pixi run sim follow:=false # a free camera instead of one that follows the car
```

Cameras and lidars inside Gazebo can crash it on some Macs. Ours don't: in the road world
(`pixi run sim world:=road lidar:=true`), the camera, the radar stand-in and the roof
lidar render with no window, on Metal, at their full rates (Ben's Mac, 15 Oct). The lidar
is off by default all the same: its big clouds made the whole graph flaky once YOLO ran too
([Simulation](simulation.md#the-lidar-gazebo-only)). If Gazebo crashes, use the empty
world, which renders nothing.

If the window stays empty, or the car never appears, run `export GZ_IP=127.0.0.1` in both
terminals and start again: Gazebo's two programs then find each other on the Mac itself.
On Ben's Mac the simulator ran without it (10 Oct); it fixed the same symptom on Linux.

## macOS hides one setting from ROS

| What happens | Why it matters | What we do |
|---|---|---|
| macOS's System Integrity Protection (SIP) deletes `DYLD_LIBRARY_PATH` whenever one of Apple's own programs starts, such as `/bin/sh`, `/bin/bash` or `/usr/bin/env` | ROS finds our own message libraries (`aav_interfaces`) through that setting. Without it: "Could not load library" | for `colcon test`: the Mac environment adds GNU `coreutils`, whose `env` isn't Apple's |
| A script that starts with `#!/usr/bin/env bash` loses the setting too | `ros2 bag record` couldn't record `/vehicle/status` | scripts run `ros2` through `tools/ros.sh`, which sets it last: `tools/record.sh` does |

Two rules follow, for anyone writing scripts:
- On a Mac, a script that runs `ros2` with our messages must run it through `tools/ros.sh`.
- Inside Pixi on a Mac, `ls`, `date`, `stat` and friends are the GNU versions, the same as
  on Linux and the car. Outside Pixi, the Mac's own versions are unchanged.

## Three more things the bench found on a Mac

| What happens | Why | What we do |
|---|---|---|
| A best-effort subscriber gets no camera images at all | an image is too big for one UDP packet, and best effort drops the whole image when one piece is lost | subscribe to images reliably, keeping only the newest frame |
| `ros2 topic hz` on a camera or lidar shows nothing | Jazzy's `hz` always subscribes best effort, with no option to change it | count them reliably: `ros2 topic echo --qos-reliability reliable --field header.stamp <topic>` |
| A Python node with `MultiThreadedExecutor` uses a whole CPU core | rclpy 7.1.12's multi-threaded executor spins whenever any subscription gets messages | use the default single-threaded executor; `scripted_driver` now does |
| A script started through `#!/usr/bin/env python3` can't load our messages | macOS drops `DYLD_LIBRARY_PATH` when `/usr/bin/env` starts | launch such scripts with `prefix='python3'`, as `aav_lane_geometry` does |

## If the native way fails: Ubuntu in UTM

1. Install UTM (free) from mac.getutm.app.
2. Make a VM from the Ubuntu 24.04 **arm64** image, from cdimage.ubuntu.com.
3. Network: **Bridged**, so the VM gets its own address on the car's network.
4. Display: UTM's GPU-accelerated option (experimental) for RViz. Inside the VM,
   `glxinfo -B` should not say `llvmpipe`.
5. Inside the VM, install Jazzy as on [Platforms](platforms.md), or use Pixi as above.

## If something breaks

Paste these into Claude (or a team chat), and it can usually say what to fix:

| What | How |
|---|---|
| The command, and the last 20 lines it printed | copy them from Terminal |
| What the doctor says | `pixi run doctor` |
| Which Mac | `sw_vers; uname -m; pixi --version` |

## What's been tested

| Part | Status |
|---|---|
| The Pixi environment resolves for Macs (Apple Silicon and Intel, macOS 14+) | [[works]] |
| Steps 3 to 5 from a fresh copy of the bundle: clone, install, build, `pixi run test`, the turtle | [[works]] on Linux, and on an Apple Silicon Mac (macOS 27), 10 Oct |
| Building on a Mac | [[works]] 19 packages in 18 s; 24 packages in 15 s on 10 Oct evening |
| Bench mode, `pixi run bench-check` | [[works]] 7 of 7, with perception (`-e ml`) |
| YOLO on the Mac's GPU (Metal) | [[works]] 7.7 ms a frame; Core ML 4.3 ms |
| The laptop's own detector against the bench (`laptop-bench`) | [[works]] 11 Oct: Core ML on the compressed pictures, 21 ms each; it saw the stop sign from 20 m |
| `pixi run test` on a Mac | [[works]] all green, after the `coreutils` fix above |
| The turtle, driving it the keyboard's way, the scripted drive, the e-stop | [[works]] on Linux and the Mac. The real keyboard keys are [[untested]] on a Mac |
| Gazebo without its window, and a Nav2 goal | [[works]] on the Mac, without `GZ_IP` |
| Gazebo's window on a Mac | [[works]] 10 Oct: `pixi run sim` opens it; the car drives in it (pictures in [Your first day](first-day.md)) |
| Gazebo's camera and lidars on a Mac | [[works]] 15 Oct: headless, 10 Hz each; `pixi run sim-check` passes. The lidar with YOLO too is flaky, so it's off by default |
| RViz and rqt_graph on a Mac | [[untested]] they open without errors (RViz logs one shader warning); nobody has looked at them yet |
| Recording a drive (`tools/record.sh`) | [[works]] on the Mac, after the `tools/ros.sh` fix above |
| The Rust listener | [[works]] on the Mac: builds in 15 s |
| Joystick on a Mac | [[untested]] An old macOS joystick bug is fixed in the version we use. |
| The Mac on the car's network | [[untested]] the car still runs Humble |
| `pixi run doctor` | [[works]] on Linux and the Mac |
