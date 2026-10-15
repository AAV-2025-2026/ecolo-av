# Friday 16 October: the audit, the network, and our stack on the car

Written 15 October 2026, for Ben and the team. The plan for the day, in order, with a
**stop point** after each step.

> **The short version**
> - **Morning: look, don't touch.** Back up, run the read-only checks, and answer the questions in [docs/audit-questions.md](docs/audit-questions.md).
> - **Then the network, together:** the IPs, the ROS domain, and whether multicast passes between the machines (ROS needs it).
> - **Then our stack, one piece at a time,** in our own ROS domain (42), so it never mixes with the 2025-26 software.
> - **The furthest we go on Friday: driving with the wheels off the ground,** at 0.3 m/s, with the e-stop in hand. No driving on the ground.
> - **Everything we add lives in one folder** on each computer. Deleting it undoes it.

## 0. Before Friday (Thursday evening)

| # | Do | Why |
|---|---|---|
| 1 | `pixi run car-kit` on the Mac, onto a USB stick | the car's network may have no internet: the kit has the code, the environment for ARM, and the models |
| 2 | `pixi run test` and `pixi run bench-check` on the Mac | start from a known-good `main` |
| 3 | Print or open [docs/audit-questions.md](docs/audit-questions.md) and [docs/audit-friday.md](docs/audit-friday.md) | |
| 4 | Bring: the USB stick, an Ethernet cable, a USB-C hub, a tape measure, a multimeter, the joystick, a magnet (for C2) | |
| 5 | Ask the team for the logins. **Never write passwords into the repo** | |

## 1. Morning: the audit (read-only)

Follow [docs/audit-friday.md](docs/audit-friday.md): safe and powered, find each
machine, **back up first**, then the read-only checks on every machine.

**Stop point:** every machine backed up, and the results table filled in. If a backup
fails, nothing below happens on that machine.

## 2. The network, together

We look at this side by side. ROS 2 finds its peers by **multicast**, so the network has
to pass it between machines, and over the WiFi to the laptops.

| # | Check | Command | Good answer |
|---|---|---|---|
| 1 | The map: every machine's IP and name | the router's client list; `arp -a` | a table: switch label → IP → hostname |
| 2 | The 2025-26 domain | `printenv \| grep ROS` on each | a number: ours (42) must differ |
| 3 | Multicast, wired | `ros2 multicast receive` on the Orin, `ros2 multicast send` on a Pi | "Received from ..." |
| 4 | Multicast, WiFi | the same between a laptop on the WiFi and the Orin | the same, both ways |
| 5 | The switch | its web page: IGMP snooping | off, or check 3 passes anyway |
| 6 | Clocks | `date` on every machine at once | within a second |
| 7 | Internet | `ping 1.1.1.1` from the Orin | either way is fine: the kit works offline |
| 8 | Our own check | `pixi run doctor` on a laptop | it says what to fix |

**Stop point:** a network map written down, and multicast passing everywhere we need it.
If check 3 or 4 fails, ROS can't work across machines yet: fix it first (W3, W4 in the
questions).

## 3. Install our stack: one folder, no admin

On the **Orin** and the **Motor-Pi** (64-bit only: `uname -m` must say `aarch64`):

```bash
# from the USB stick (bash, because a stick may drop the files' run permission)
bash car-kit/car_install.sh --dry-run    # the checks only: changes nothing
bash car-kit/car_install.sh              # unpacks into ~/aav-jazzy and builds; no sudo
```

- It doesn't touch the Humble install, `~/.bashrc`, or any service.
- **Undo:** `rm -rf ~/aav-jazzy`.
- It needs 13 GB free (the environment is 9 GB unpacked): `--dry-run` checks (W7, W8).
- Step by step, with sizes and times: [docs/car-install.md](docs/car-install.md).

**Stop point:** the build finishes on both.

## 4. Listen first: our stack next to theirs

Everything of ours runs in **domain 42**. On the car's computers `~/aav-jazzy/aav.sh`
sets it; on a laptop, `export ROS_DOMAIN_ID=42` in each terminal. The 2025-26 software in
its own domain doesn't see us, and we don't see it.

```bash
~/aav-jazzy/aav.sh tools/car_listen.sh    # which devices exist, which our drivers could open
```

A device (the GPS, the IMU, a camera) can only be opened by **one program**. So for each
sensor, one at a time:

| # | Do | See it |
|---|---|---|
| 1 | Stop the 2025-26 program that owns the device (found in step 1) | |
| 2 | Start ours: `~/aav-jazzy/aav.sh car orin` with only that part (or its driver alone) | `ros2 topic hz /sensors/gps/fix` |
| 3 | Look at it: `pixi run hud` on a laptop, domain 42 | the GPS panel: NO FIX / 3D / RTK |
| 4 | Stop ours; start theirs again | their software works as before |

Order: **GPS** first (it answers "is there GPS data?"), then the IMU, then a camera (with
`camera_ros`, if the cameras are ribbon ones), then the radar and the lidar if their
drivers are known.

**Stop point:** each sensor shows on our HUD, and theirs works again afterwards.

## 5. Drive with the wheels off the ground

Only if steps 1-4 went well, and the team agrees.

| # | Check before | |
|---|---|---|
| 1 | The car on stands: **all four wheels off the ground** | ☐ |
| 2 | Someone holds the **Kar-Tech e-stop**, and knows what it cuts (S1) | ☐ |
| 3 | The 2025-26 Motor-Pi software is **stopped**. Never two drive paths at once | ☐ |
| 4 | Everyone knows: today's ESP32 firmware has **no command timeout** (S3) | ☐ |

Then:

```bash
# Motor-Pi (domain 42): our legacy backend, to today's ESP32 over its UART
~/aav-jazzy/aav.sh car motor_pi
# Orin (domain 42): mux and ego, speed capped
~/aav-jazzy/aav.sh car orin -- max_speed:=0.3 gps:=false
# Laptop, on the car's WiFi: in every terminal first
export ROS_DOMAIN_ID=42
pixi run keyboard
pixi run hud
```

| # | Test | Expect |
|---|---|---|
| 1 | Nothing pressed | wheels still; the HUD shows speed 0 |
| 2 | Forward, gently | the drive wheels turn **forward**, slowly |
| 3 | Left | the front wheels turn **left** (positive steering = left) |
| 4 | Let go of the key | ego slows to 0 within 0.3 s; the bridge sends brake frames |
| 5 | The HUD's e-stop button | brake at once; nothing moves until `pixi run estop-clear` |
| 6 | Stop the keyboard program | the bridge brakes (its commands go stale) |
| 7 | Stop the Motor-Pi bridge with Ctrl-C | it sends a last stop frame |
| 8 | The Kar-Tech e-stop | everything stops |

**Stop point:** all eight pass. Write down anything that turned the wrong way: it's a
sign to fix in `legacy_protocol.py` or `vehicle.yaml`, not on the car.

**Not on Friday:** driving on the ground, Nav2, the scripted drive at speed, flashing any
board, the Rust ESP32 firmware, or the reflash to JetPack 7.2.

## 6. Put it back

| # | Do |
|---|---|
| 1 | Stop all our programs (Ctrl-C) |
| 2 | Start the 2025-26 software again, the way step 1 found it starts |
| 3 | Check it drives as before (their usual test) |
| 4 | Leave `~/aav-jazzy` in place for next time, or `rm -rf` it |
| 5 | Save the results: `docs/history/audit-2026-10-16-car.md` (no secrets) |

## Links

| Page | For |
|---|---|
| [docs/audit-questions.md](docs/audit-questions.md) | every question, how to answer it, what it unblocks |
| [docs/audit-friday.md](docs/audit-friday.md) | the read-only audit, machine by machine |
| [docs/car-install.md](docs/car-install.md) | the USB kit: install offline, no sudo, and undo |
| [docs/platforms.md](docs/platforms.md) | Jazzy on the car before the reflash |
| [READ-ME-HOW-IT-ALL-FITS.md](READ-ME-HOW-IT-ALL-FITS.md) | what starts where, and why |
