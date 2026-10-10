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

**3. The code.** Copy the file `aav.bundle` to the Mac (from `/home/ben/aav/` on
oirp-spss), then:

```bash
git clone aav.bundle aav
cd aav
```

**4. Install ROS and build:**

```bash
pixi install       # ROS 2 Jazzy: about 7 GB, the first time only
pixi run build     # our packages
```

**5. Check it:** `pixi run turtle` in one terminal and `pixi run keyboard` in another.
Hold `i` to drive.

## Join the car's network

| # | Do this | Why |
|---|---|---|
| 1 | Join the car's own WiFi router | campus WiFi blocks the traffic ROS uses to find other computers |
| 2 | Add `export ROS_DOMAIN_ID=<n>` to `~/.zshrc`, with the car's number | ROS only talks within one domain. The team hasn't picked its number yet [[needs-you]] |
| 3 | Leave the middleware alone | the Mac's Pixi install and Ubuntu both use Fast DDS |
| 4 | When macOS asks whether `python3` or `rviz2` may accept incoming connections, click Allow | otherwise the firewall blocks the car's replies |
| 5 | Run `pixi run doctor` | it checks steps 1–4, and whether it can see the car, and says what to fix |

`pixi run tools/ros.sh ros2 topic list` should then list the car's topics. If they don't
show up:
- Check that the Mac and the car's computers have addresses on the same network.
- Name the computers directly: add `export ROS_STATIC_PEERS=<the Orin's IP>` on the Mac,
  and the Mac's IP on the Orin. This is Jazzy's way around blocked multicast.
- Turn off the Mac's firewall for a minute, to see whether it's the cause.

## Drive and watch from the Mac

| Want | Run this on the Mac |
|---|---|
| Drive with the keyboard | `pixi run keyboard` |
| Stop everything | `pixi run estop`, then `pixi run estop-clear` when it's safe |
| The 3D view: map, costmaps, path, the car | `pixi run rviz` |
| Nodes and topics, live | `pixi run graph` |
| Be the safety driver's joystick laptop | `pixi run tools/ros.sh ros2 launch aav_bringup car.launch.py machine:=laptop` |

!!! warning "Driving the real car"
  The keyboard has priority 90. The safety driver's joystick (100) and the hardware
  e-stop always win. Keep both in someone's hands whenever the Mac drives.

## Watch without ROS: Lichtblick

The car runs `foxglove_bridge`, so any Foxglove-compatible viewer can watch it over one
WiFi connection, with no ROS on the Mac.
- **Lichtblick:** free, open source, no account. Download the Mac app from
  github.com/lichtblick-suite/lichtblick (releases).
- **Foxglove:** the same idea; its free plan needs an account.

In either app: Open connection → Foxglove WebSocket → `ws://<the Orin's IP>:8765`.

## Gazebo on a Mac

On macOS, Gazebo's window has to run as a separate program:

```bash
pixi run sim gui:=false    # terminal 1: the simulator, with no window
pixi run gz-window         # terminal 2: Gazebo's window
```

Cameras and lidars inside Gazebo can crash it on a Mac. Our simulated car has neither yet.

## If the native way fails: Ubuntu in UTM

1. Install UTM (free) from mac.getutm.app.
2. Make a VM from the Ubuntu 24.04 **arm64** image, from cdimage.ubuntu.com.
3. Network: **Bridged**, so the VM gets its own address on the car's network.
4. Display: UTM's GPU-accelerated option (experimental) for RViz. Inside the VM,
   `glxinfo -B` should not say `llvmpipe`.
5. Inside the VM, install Jazzy as on [Platforms](platforms.md), or use Pixi as above.

## What's been tested

| Part | Status |
|---|---|
| The Pixi environment resolves for Macs (Apple Silicon and Intel, macOS 14+) | [[works]] |
| Building on a Mac | [[untested]] The one known blocker, a Linux-only serial speed in the IMU driver, is fixed. |
| Turtle, keyboard, e-stop | [[works]] on Linux; [[untested]] on a Mac |
| RViz and rqt on a Mac | [[untested]] |
| Joystick on a Mac | [[untested]] An old macOS joystick bug is fixed in the version we use. |
| The Mac on the car's network | [[untested]] |
| `pixi run doctor` | [[works]] on Linux; [[untested]] on a Mac |
