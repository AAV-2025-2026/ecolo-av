# Friday 16 October: the to-do list

Written 15 October 2026, for the team. **The goal:** log in to every machine on
the car, and come home with everything we need to finish the hardware layers: what each
machine runs, what starts it at boot, what is plugged in, the files that exist only on
the car, and what goes wrong (such as the cameras freezing).

> **The short version**
> - **Look, copy, write down. Change nothing.** No installs, restarts, reflashing or driving during parts 1-6.
> - **One command surveys every machine:** `pixi run survey ~/aav-audit/hosts.txt`. It's read-only, and saves one file per machine on the Mac.
> - **Copy what exists only on the car** before anything else happens to it: model weights, unpushed code, maps, calibration, boot scripts.
> - **The cameras freezing:** ask the team first, then watch one camera for 10 minutes with the power and temperature logged beside it (part 5).
> - The day's wider plan, and what comes after the audit: [Friday 16 Oct](friday-2026-10-16.md). Every question: [docs/audit-questions.md](../audit-questions.md).

```text
 0 ready  →  1 find  →  2 log in + survey  →  3 read  →  4 copy  →  5 errors  →  6 per layer  →  7 write up
 (home)      net-map    every machine         surveys    only-here   cameras      what's left    no secrets
```

## 0. Before: Thursday evening, at home

| ☐ | Do |
|---|---|
| ☐ | `git pull`, `pixi run build`, `pixi run test` |
| ☐ | Make sure the `git pull` has commit 426e3a0b (15 Oct): before it, `pixi run sim`, `turtle`, `bench` and `keyboard --local` were **not** kept on the Mac, so a pretend car could have met the real one |
| ☐ | The Mac checklist in [Friday 16 Oct](friday-2026-10-16.md) ("Your Mac on the car's network"): Local Network permission, firewall, Lichtblick, an SSH key |
| ☐ | `pixi run car-kit`, onto a USB stick (for after the audit) |
| ☐ | An external drive with an **encrypted** volume, 1 TB or more: the copies hold passwords and keys |
| ☐ | `mkdir -p ~/aav-audit && chmod 700 ~/aav-audit` |
| ☐ | Ask the team for the logins, and **what goes wrong with the car**: which camera freezes, when, how often, what they do to fix it |
| ☐ | Bring: the drive, an Ethernet cable, a USB-C hub, a microSD reader, a tape measure, a multimeter, a magnet, a phone for photos |

## 1. Safe, then find every machine

| ☐ | Do | Gives |
|---|---|---|
| ☐ | Car on stands, wheels off the ground, e-stop in someone's hand, RC off | nothing can move |
| ☐ | Mac on the car's switch with the **USB-C Ethernet dongle**, phone hotspot for the internet: the step-by-step is in [Friday 16 Oct](friday-2026-10-16.md), "Ethernet dongle and phone hotspot" | |
| ☐ | `pixi run net-map --listen 30 --out ~/aav-audit/net-map.md` | every IP, MAC, maker, open ports, ROS domains |
| ☐ | The router's client list: a screenshot (check no password shows) | names for the IPs |
| ☐ | Match each IP to a switch label, and write `~/aav-audit/hosts.txt` (below) | the list for part 2 |

`~/aav-audit/hosts.txt`, one machine per line. **No passwords in it**: ssh asks.

```text
# label    user@ip
JETSON     aavjetson@192.168.1.x
CAM1-PI    pi@192.168.1.x
CAM2-PI    pi@192.168.1.x
RTK-PI     pi@192.168.1.x
DASH-UI    aavui@192.168.1.x
ES-PI      pi@192.168.1.x
MOTOR-PI   pi@192.168.1.193
```

## 2. Log in to every machine, and survey it

```bash
pixi run survey ~/aav-audit/hosts.txt        # one file per machine: ~/aav-audit/<label>.txt
```

It runs [tools/machine_survey.sh](../../tools/machine_survey.sh) on each machine over ssh. Read-only:
no installs, no restarts, never opens a serial port (that can reset an ESP32), never probes
I2C, uses sudo only if it needs no password. It cuts lines that look like passwords or
tokens. About 1-3 minutes a machine.

| Machine | ☐ ssh works | ☐ survey OK | ☐ backed up (part 4) | Notes |
|---|---|---|---|---|
| JETSON (Orin) | | | | the most important: the detector, `camera_decode`, OSRM |
| CAM1-PI | | | | |
| CAM2-PI | | | | |
| RTK-PI | | | | the GPS |
| DASH-UI | | | | the HUD app, `ottawa.db`, tiles |
| ES-PI | | | | in the e-stop path? |
| MOTOR-PI | | | | talks to the ESP32 |
| QNX-PI | | | | QNX, not Linux: run `uname -a; pidin; ls /dev` by hand |

Machines you can't log in to, by hand:

| Device | ☐ | Do |
|---|---|---|
| Lidar | ☐ | its label (make, model); its IP from net-map; its web page, read only |
| ESP32 board | ☐ | `http://<ip>/status` only (**not** the update page); photograph U3, U7, the jumpers |
| Wheel-encoder Pico 2 | ☐ | its MAC `54:65:6d:70:65:6c` in net-map; photograph the board and sensor |
| Router, switch | ☐ | the client list; the switch's IGMP snooping setting (W4) |
| Radar | ☐ | where it is, and which USB it's on (the survey's USB list shows a TI or CP210x) |

## 3. Read each survey: what to write down

Each file has sections starting `====`. For each machine, pull out:

| Section | Write down | It answers |
|---|---|---|
| os and board | the OS, JetPack or Pi model | what our kit runs on (needs `aarch64`) |
| power | `get_throttled`: anything but `0x0` means brown-outs | the camera freezes? the 5 V converters (P1) |
| network | IPs, CAN interfaces, listening ports and their programs | the network map |
| ROS environment | Humble? the domain; DDS XML files | W2; what our stack must not clash with |
| running now | every ROS node, script and container, with its full command line | what we replace, layer by layer |
| starts at boot | each hand-made service, cron `@reboot`, autostart, `rc.local`; **restarts** count | how to stop theirs and start ours; a high restart count = a crash loop |
| hardware: USB, cameras, I2C | each device: what it is, its stable name (`by-id`), **who holds it open** | which driver we need, and its device path |
| kernel, errors | USB disconnects, camera timeouts, the error log, how often it reboots | part 5 |
| ROS logs | the most common ERROR and WARN lines | part 5 |
| code on this machine | each repo: remote, commit, **changed files, unpushed commits** | part 4: code that's on no GitHub |
| files that may exist only here | weights, maps, recordings, calibration | part 4 |

## 4. Copy what exists only on the car

**Before anyone changes anything.** To the encrypted drive, never to git directly.

| ☐ | What | Where it probably is | How |
|---|---|---|---|
| ☐ | Every home folder | each machine | `rsync -a --exclude .cache <user>@<ip>:~/ /Volumes/<drive>/aav-backup/<label>/home/` |
| ☐ | `/etc` (services, udev, network) | each machine | `ssh <user>@<ip> 'sudo -n tar czf - /etc' > /Volumes/<drive>/aav-backup/<label>/etc.tgz`. If sudo wants a password: the three commands in [docs/audit-friday.md](../audit-friday.md), step 3 |
| ☐ | **Model weights**: the stop-sign detector, any `best.pt`, `.engine`, `.onnx` | the Orin (survey: "files that may exist only here") | in the home copy. Write each one's path, size and `sha256sum` |
| ☐ | **Code not on GitHub**: repos with changed files or unpushed commits; workspaces that aren't git repos | survey: "code on this machine" | in the home copy. List each one in the write-up |
| ☐ | **`~/Desktop/aav/Camera` on the Jetson**: `camera_decode`, `best.pt` / `best.onnx` / `best.engine` (the stop-sign model), `cameras.yaml` (the Pis' IPs). **In no git repo** | the Jetson | in the home copy; check it's there |
| ☐ | MediaMTX's config, `/usr/local/etc/mediamtx.yml`, and its service | each camera Pi | in the `/etc` copy, plus that file |
| ☐ | Camera calibration (`~/.ros/camera_info/*.yaml`) | the camera Pis, the Orin | in the home copy |
| ☐ | OSRM route data, map tiles, `ottawa.db` | DASH-UI, the Orin; Docker volumes | the home copy; `docker inspect` shows the volume paths |
| ☐ | Recordings (`.db3`, `.mcap`, `.bag`) | anywhere | in the home copy: useful test data |
| ☐ | The boot scripts: hand-made `.service` files, crontabs, autostart files | `/etc/systemd/system`, home folders | in the `/etc` and home copies |
| ☐ | SD-card images of the Pis | only if the team agrees to shut each one down | [docs/audit-friday.md](../audit-friday.md), step 3 |

What then comes into **git** (later, on a branch): source code only, each with a
`PROVENANCE.md`. Weights go in `models/` (not in git), with their checksum written down.

## 5. Errors to chase

### The cameras freezing

**How their cameras work** (found 15 Oct, in the 2025-26 `AAV_dashboard` repo:
[docs/reference/2025-26-camera-system](../reference/2025-26-camera-system/README.md)):

```text
 camera (ribbon) → camera Pi 5: MediaMTX video server, RTSP port 8554 → network
   → Jetson: camera_decode (NVDEC decoder) → /camera/cam1/image_raw, cam2 → YOLOv8 (TensorRT) → stop sign
```

So a freeze can start in **four** places: the Pi (power, the ribbon), MediaMTX, the network,
or the Jetson's decoder. Check each: `systemctl status mediamtx` on each camera Pi; port 8554
open in net-map; `ros2 topic hz /camera/cam1/image_raw` on the Jetson (domain 10).

**First, ask the team** (write the answers down):

| ☐ | Question |
|---|---|
| ☐ | Which camera(s)? The picture stops, or goes black, or the program crashes? |
| ☐ | After how long? Only when driving, or on the bench too? Hot days? |
| ☐ | Does it come back by itself? What do they do: restart a program, reboot, replug? |
| ☐ | Where do they see it: on the HUD, in RViz, on the Orin's detector? |

**Then look** (the survey already has most of this):

| Possible cause | How to tell | Section |
|---|---|---|
| **Power: the Pi browns out** | `get_throttled` not `0x0`; "under-voltage" in the kernel log. The dash converter showed 3.48 A; a Pi 5 wants 5 A | power |
| **Heat** | over 80 °C; throttling bits set | disk, memory, temperature |
| **The camera link (ribbon)** | `unicam`, `rp1-cfe`, `csi` or "timeout" lines in the kernel log | hardware: cameras |
| **The streaming program crashes and restarts** | its service's **restarts** count; its ROS log errors | starts at boot; ROS logs |
| **The network: raw pictures over WiFi** | the stream's size: `ros2 topic bw` on the picture topic, on the car's Humble side | on the camera Pi |
| **The receiving end** (the Orin or the HUD), not the camera | the camera Pi's rate stays steady while the HUD's picture stops | the watch below |

**The 10-minute watch** on one camera Pi. Read-only, and everything is saved on the Mac:

```bash
# Mac terminal 1: the Pi's power and heat every 5 s
ssh <user>@<camera pi> 'while true; do echo "$(date +%T) $(vcgencmd get_throttled) $(vcgencmd measure_temp)"; sleep 5; done' \
  | tee ~/aav-audit/watch-<label>.txt
# Mac terminal 2: the picture rate on the Pi, with their ROS (their domain and topic name)
ssh <user>@<camera pi>
source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=<theirs>
ros2 topic hz <their camera topic>
```

When the picture freezes: note the time, look at both terminals, then run `dmesg | tail -20`
on the Pi (with `sudo` if it asks).

### Other errors to note

| ☐ | Error | Where |
|---|---|---|
| ☐ | Reboots without anyone asking (many boots in `journalctl --list-boots`) | every survey |
| ☐ | USB devices dropping and coming back | the kernel section |
| ☐ | Failed services | starts at boot |
| ☐ | The most common ROS errors | ROS logs |
| ☐ | Clocks more than a second apart | `date` on each, side by side (W6) |
| ☐ | Anything else the team mentions | ask |

## 6. Each hardware layer: what we still need from the car

What our code has today, and what Friday must answer to finish each layer.

| Layer | Our code today | Still need from the car | Questions |
|---|---|---|---|
| **Throttle** | `aav_legacy` (the ESP32's UART); spine CAN later | the Motor-Pi's serial port and baud; what writes to it now; the motor controller's model and limits | D1-D3, D8 |
| **Steering** | ego → Ackermann; no position feedback | the Jrk G2 settings; actuator wire count (feedback built in?); the centre reading; the full-lock angles | D6, D7, N9, M5 |
| **Brake** | through the ESP32 (Jrk G2) | what the brake does when power is cut; the Jrk settings | S2, D6 |
| **E-stop** | the spine's watchdog; `/safety/estop` | what the Kar-Tech and the mushroom cut; whether ES-PI is in the path | S1, S3, W9 |
| **Wheel speed** | `aav_legacy` reads the Pico over UDP 10111 | is the Pico alive, and do its packets arrive at the Motor-Pi? | D4 |
| **IMU** | `aav_imu_yahboom` (Rust) | which computer, which USB, its stable name; its mounting angle | N3, M6 |
| **GPS / RTK** | stock `ublox_gps`; `navsat_transform` | the ZED-F9R's port; who reads it now; where corrections come from; is there a fix | N1, N2 |
| **Cameras** | `usb_cam` (needs `camera_ros` for ribbon cameras); YOLO | the camera models; what streams them; calibration files; **the freeze** | N4, N5, part 5 |
| **Radar** | `ti_ros2_driver`; `aav_radar_clusters` (Rust) | is it on the car; where; which USB; its config file | N7 |
| **Lidar** | **none yet**; Gazebo only | make, model, IP; which computer reads it; any driver on the car | N6 |
| **Power, battery** | none | each converter's rating and load; the KM110F's data port | P1, P2, N8 |
| **Network, time** | domain 42; `doctor`, `net-map` | the IP map; multicast; IGMP; clocks | W1-W6 |
| **HUD screen** | the raylib HUD and map; boot units ready (`car_install.sh --screens`) | which computer drives which screen, the outputs' names and resolutions; how the app starts at boot (below) | W10 |
| **CAN (the KEFC plan)** | the DBC; the spine firmware | is U7 fitted and wired to the ESP32; rotor holes; room at each wheel | C1-C3 |

### The dash's two screens (W10)

Our HUD and map are ready to start at boot, one per screen ([docs/car-screens.md](../car-screens.md)):
they only need these answers. Read-only, on the computer the screens plug into, in its
desktop's terminal (or over ssh with `DISPLAY=:0`).

| ☐ | Note | How |
|---|---|---|
| ☐ | Which computer drives each screen (follow the cables: the small touchscreen, the Innoview) | photo of both ends of each cable |
| ☐ | The outputs' names and resolutions | `xrandr --listmonitors` (X11); `wlr-randr` (Wayland: Pi OS); `kmsprint` (no desktop) |
| ☐ | Which name is the small screen, which the big one | the sizes in the line above: ~800x480 is the touchscreen |
| ☐ | X11 or Wayland | `echo $XDG_SESSION_TYPE`, and `loginctl show-session $XDG_SESSION_ID -p Type` |
| ☐ | Does it log in to the desktop by itself at power-on? As which user? | watch a boot; `grep -i autologin /etc/gdm3/custom.conf` |
| ☐ | What starts the 2025-26 app now | `systemctl list-unit-files --state=enabled`; `systemctl --user list-unit-files`; `ls ~/.config/autostart` |
| ☐ | Is the touchscreen's touch a mouse to X? | `xinput list` |
| ☐ | The GPU and OpenGL version (two full-screen windows) | `glxinfo -B` if installed; `uname -m` must say `aarch64` for our kit |
| ☐ | Its 5 V (the dash converter showed 3.48 A) | `vcgencmd get_throttled` (E1) |

## 7. Photos and measurements

| ☐ | Do |
|---|---|
| ☐ | Photograph every label: each computer, the GPS, IMU, lidar, radar, cameras, motor controller, both Jrk G2s, the converters, the switch. Name files by label: `RTK-PI-1.jpg` |
| ☐ | The tape-measure sheet, M1-M7 and every sensor: [Measure the car](../measure-the-car.md). Print it; fill it in; photograph it |

## 8. Write it up (no secrets)

| ☐ | Do |
|---|---|
| ☐ | `docs/history/audit-2026-10-16-car.md`: the table in [docs/audit-friday.md](../audit-friday.md) step 7, plus part 3's notes, part 4's list of what exists only on the car, and part 5's findings |
| ☐ | Answer each question in [docs/audit-questions.md](../audit-questions.md) by its number |
| ☐ | `grep -n -i -E "pass|psk|token|secret|key|ntrip" docs/history/audit-2026-10-16-car.md`: write only where a secret is and what kind |
| ☐ | The raw survey files and backups stay in `~/aav-audit/` and on the encrypted drive: **never in git** |
| ☐ | Update [Team tasks](../team-todo.md), the team's work list: fill its "Audit says" column, fix the sizes, add what the audit found |

## Don't (all day, until part 8 is done)

| Don't | Why |
|---|---|
| Install, upgrade, restart services, reboot | something may depend on it; we're recording how it is |
| Open the ESP32's update page, or flash anything | no password, and no way back |
| Configure the GPS, the radar or the lidar | their settings are part of what we record |
| Run `i2cdetect`, or open a serial port | it can move an actuator, or reset a board |
| Copy a password, token or key into notes, chat, photos or git | they must be changed, not spread (Q34) |
| Run a simulator with `AAV_DISCOVERY=SUBNET` | it would share the pretend car with the real car's network |
