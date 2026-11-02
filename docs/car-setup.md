# Car setup: every computer, one by one

Written 1 November 2026, for a student on their own. Ben, 1 Nov: "we are going to login
to each node, upgrade the os, and install our code. Make sure we setup the boot process
... ubuntu 24 whatever on all of them and updated." This page is that day, in order.

> **The short version**
> - **Back up each computer first.** Then upgrade it, install our code, start it at boot.
> - **One script does each computer:** `bash car_setup.sh <role>`. With no `--apply` it only prints what it would do.
> - **Order:** the Pis, then the Orin (a reflash), then the ESP32, then the first moves with the joystick, then the lab desktop.
> - **Wheels off the ground** until [car day](car-day.md)'s session 9 passes.
> - **Logins** are in the Keychain of Ben's Mac. Type them; never paste them into a file, a chat or the repo.
> - Changes to the hardware (the ESP32, the Orin's reflash) wait for **the hardware lead's OK**.

## The order

```text
 1 back up ──► 2 Ubuntu Pis: upgrade ──► 4 install ──► 5 start at boot ──┐
   (all)       3 Pi OS Pis: keep, or                                     │
                 a new SD card                                           ▼
 6 the Orin: JetPack 7.2 (reflash) ──► 4, 5 again on it ──► 7 the ESP32 ──► 8 first moves
 9 the lab desktop: upgrade, CARLA (any time)
```

The internet is there all day: `apt` and GitHub work. Only the ESP32's flash (step 7)
goes over a USB cable from the laptop.

## The computers and their roles

From the [21 Oct audit](history/audit-2026-10-21-car.md). Addresses are `192.168.1.x`.
Usernames: `~/aav-audit/hosts.txt` on Ben's Mac.

| Role (for the script) | Computer | Address | Today | Should be | How |
|---|---|---|---|---|---|
| `orin` | JETSON, AGX Orin | .140 | Ubuntu 22.04, JetPack 6 (R36.4.7) | JetPack 7.2 (Ubuntu 24.04) | a reflash (step 6) |
| `motor_pi` | CORTEX, Pi 4 (the Motor Pi? H1) | .120 | Ubuntu 22.04 | Ubuntu 24.04 | `do-release-upgrade` (step 2) |
| `localization` | LOCALIZATION, Pi 4 | .113 | Ubuntu 22.04 | Ubuntu 24.04 | `do-release-upgrade` |
| `dash` | aav-desktop, Pi 4, the two screens | .196 | Ubuntu 22.04 Desktop | Ubuntu 24.04 Desktop | `do-release-upgrade`; 4 GB of memory or more |
| `camera_pi` | CAM1-PI, CAM2-PI, Pi 5 | .108 (or .102), .118 | Pi OS (Debian 13) | **Pi OS, updated** | `apt full-upgrade` only (step 3) |
| `lab_desktop` | the lab's x86 desktop, NVIDIA | ☐ | Ubuntu, CARLA | updated | step 9 |
| none | `.211`, a Pi | .211 | Ubuntu 22.04 | ask the team first | its job is unknown |

## Running the script

Copy it to the computer, log in, and run it there. `tmux` keeps it running if the ssh drops.

```bash
scp tools/car_setup.sh <user>@192.168.1.120:        # from the laptop, in the repo
ssh -t <user>@192.168.1.120
tmux new -s setup                                  # back in after a drop: tmux attach -t setup
bash car_setup.sh motor_pi                         # a dry run: prints every step, changes nothing
bash car_setup.sh motor_pi backup --apply          # really: it asks you to type "motor_pi"
```

| Step | Does | Needs sudo |
|---|---|---|
| `backup` | `~/aav-backup/<host>-<date>/`: the package lists, services, crontab, addresses, `/etc` | yes (`/etc`) |
| `upgrade` | `apt full-upgrade`; prints `do-release-upgrade` (runs it with `--release-upgrade`) | yes |
| `install` | our code from the car kit (`car_install.sh`); the dash adds `--screens` | no |
| `services` | chrony, udev, groups, Cyclone's card, a fixed address (`--address`), our stack at boot | yes |
| `check` | read-only: OK, NOTE or STOP per line. Runs in a dry run too | no |

With no step named, it does all five, in that order. The units it installs:
[tools/systemd](../tools/systemd/README.md).

## Step 1: back up

Before anything changes. The backups hold passwords (WiFi, keys): only on the
**encrypted** backup drive, never in git.

### A Pi's SD card, from a Mac

The whole card, so undo is a card swap. Shut the Pi down (`sudo poweroff`), take its card
out, put it in the Mac's reader.

```bash
diskutil list                                   # find the card: "external, physical", its size
diskutil unmountDisk /dev/disk4                 # disk4: the number diskutil showed
sudo dd if=/dev/rdisk4 of=$HOME/aav-backup/cortex-$(date +%F).img bs=1m   # Ctrl-T: progress
gzip $HOME/aav-backup/cortex-$(date +%F).img
diskutil eject /dev/disk4
```

- Check the disk number twice: `dd` reads the card here, so a wrong number only wastes time.
- To put it back: Raspberry Pi Imager → Choose OS → **Use custom** → the `.img.gz`.

### An Ubuntu computer, while it runs

| # | Where | Do |
|---|---|---|
| 1 | the computer | `bash car_setup.sh <role> backup --apply` |
| 2 | the laptop | the `rsync` line it prints: the home folder, to `~/aav-backup/` |

### The Orin

Its home and `/etc`: car day's [session 4a](car-day.md#4a-look-then-back-up). Its full
disk image, before the reflash: [session 11b](car-day.md#11b-in-the-lab-the-orins-full-image),
on the lab desktop.

## Step 2: the Ubuntu 22.04 Pis, to 24.04

`motor_pi`, `localization`, `dash`. An upgrade in place: no new card.

| # | Do | You should see | If not |
|---|---|---|---|
| 1 | `bash car_setup.sh <role> upgrade --apply` | the updates install | an apt error: write it down, ask the team |
| 2 | `sudo reboot`, log in again, `tmux new -s setup` | | |
| 3 | `bash car_setup.sh <role> upgrade --apply --release-upgrade` | it asks questions: keep the **installed** version of each config file | it refuses: fewer than 5 GB free, or a reboot is pending |
| 4 | Over ssh it says it opens a **spare ssh on port 1022**: say yes | | the ssh drops: `ssh -p 1022 <user>@<address>` |
| 5 | At the end, reboot | `lsb_release -d`: Ubuntu 24.04 | the SD card backup (step 1) |
| 6 | `bash car_setup.sh <role> check` | `Ubuntu 24.04` | |

!!! warning "This ends the 2025-26 software on that Pi"
    Humble (`/opt/ros/humble`) is built for 22.04: after the upgrade it stops working.
    The backup is the way back. Our code doesn't need it.

## Step 3: the Pis on Raspberry Pi OS

Pi OS can't become Ubuntu in place: that is a **new SD card** with Ubuntu Server 24.04
(Raspberry Pi Imager → Other general-purpose OS → Ubuntu).

The camera Pis **stay on Pi OS** ([What's new](whats-new.md#the-computers-which-ubuntu)):
they run no ROS, and the Pi camera works best on Pi OS. So for them:
`bash car_setup.sh camera_pi upgrade --apply`, then `services --apply` (MediaMTX at boot,
the Orin's time).

A new card instead, for any Pi: keep the old card, labelled. Undo is a card swap.

## Step 4: install our code

`orin`, `motor_pi`, `localization`, `dash`: from the car kit, made on the laptop.

| # | Where | Do |
|---|---|---|
| 1 | the laptop | `pixi run car-kit` (once), then `scp -r car-kit <user>@<address>:~/` |
| 2 | the computer | `bash ~/car-kit/car_setup.sh <role> install --apply` |
| 3 | the computer | `~/aav-jazzy/aav.sh tools/car_listen.sh`: the devices (read-only) |

The kit's details: [From a USB stick](car-install.md). The camera Pis get only our
`mediamtx.yml` ([session 5](car-day.md#session-5-the-camera-pi)).

## Step 5: start at boot

`bash ~/car-kit/car_setup.sh <role> services --apply`, then `sudo reboot`.

| What | Which roles | How |
|---|---|---|
| Our stack, `car.launch.py machine:=<role>` | `orin`, `motor_pi` | `aav-car.service`, a user unit; linger starts it at boot |
| Its settings | the same | `~/.config/aav/car.env`: the machine file, `max_speed:=0.3` |
| The two screens | `dash` | `aav-hud`, `aav-map` ([The two screens](car-screens.md)); turn on automatic login, by hand |
| The camera stream | `camera_pi` | MediaMTX, enabled |
| Time | all but the lab desktop | chrony: the Orin keeps the car's time, the others ask it |
| Device names | `orin`, `motor_pi`, `localization` | `tools/udev/99-aav.rules`: `/dev/aav/...` |
| Groups | the same, and `dash` | `dialout` (serial), `plugdev`, `input` (the joystick), `video` |
| ROS | the same | domain 42 (`aav.sh`); Cyclone on the 192.168.1.x card |
| A fixed address | any | `--address 192.168.1.120/24`: beside DHCP's, through `netplan try` (undoes itself after 120 s unless you press Enter). The router's reservation is better |

| Look | Command |
|---|---|
| Is it running? | `systemctl --user status aav-car` |
| Its log | `journalctl --user -u aav-car -f` |
| Stop it until the next boot | `systemctl --user stop aav-car` |

!!! warning "Never two drive paths"
    On the Motor Pi the script won't enable ours while the 2025-26 `aav_serial_bridge`
    starts at boot. Turn theirs off only when the team agrees:
    `sudo systemctl disable --now aav_serial_bridge`.

The `localization` Pi gets no ROS service yet: no machine file has its IMU and GPS
(`orin.yaml` assumes they're on the Orin: a TODO for the hardware lead's answer).

## Step 6: the Orin, to JetPack 7.2

A **reflash**, not an upgrade: `do-release-upgrade` must never run on a Jetson (the
script refuses). Everything on the Orin is wiped. **After the hardware lead's OK.**

| ☐ | Check first |
|---|---|
| ☐ | NVIDIA's JetPack 7.2 release notes list **Jetson AGX Orin**, and its memory size (W7: 32 or 64 GB). Write what they say here: ________ |
| ☐ | SDK Manager's page: which Ubuntu the **host** needs for 7.2. The lab desktop has it? |
| ☐ | The module's part number ([Platforms](platforms.md#moving-the-orin-to-jetpack-72): -502 has a reported flashing problem) |
| ☐ | Home and `/etc` copied (session 4a); the full image taken (session 11b) |

| # | Do | You should see |
|---|---|---|
| 1 | The Orin beside the lab desktop, a USB-C data cable to its flashing port, the Orin in **recovery mode** | `lsusb` on the desktop: NVIDIA (`0955:`) |
| 2 | SDK Manager on the desktop: Jetson AGX Orin, JetPack 7.2; flash and install the SDK components | 30-90 min; the Orin boots its first-start setup |
| 3 | Make the user (as in `hosts.txt`), on the car's network | `ssh` works |
| 4 | `bash car_setup.sh orin upgrade --apply`, then `install --apply`, `services --apply` | as steps 4-5 |
| 5 | The TensorRT engine again: [session 4d](car-day.md#4d-rf-detrs-tensorrt-engine) | an engine is tied to its TensorRT version |

## Step 7: the ESP32

**After the hardware lead's OK, with Ben on a call.** Car day's
[session 6](car-day.md#session-6-the-esp32): back up the board, flash the Rust
(`spine-esp32-umod-v2.elf`), set `frame_version: 2`, then the checks on stands. The
bench page: [First flash on the bench](esp32-bench.md).

## Step 8: the first moves, the joystick

Ben, 1 Nov: "We do still need a way to move the vehicle to get to our first test. Should
we allow the joystick to have direct control like before? ... if the connection drops we
stop?"

**Yes, but through our stack, all on the Motor Pi** (`machine:=motor_pi_alone`). The
heartbeat is then made on the same Pi as the bridge, so the ESP32 stops the car when the
Pi, the bridge or the wire stops. No Orin is needed.

```text
joystick (USB, on the Pi) ─► teleop ─► twist_mux ─► ego ─► output mux ─► legacy bridge ─► ESP32
   hold-to-drive              0.5 s     0.3 s       the heartbeat         0.3 s          brakes 100 ms
                              timeout   timeout     counter               stale→brake    after it stops
```

| # | Do |
|---|---|
| 1 | Stands, the e-stop in a hand ([session 1](car-day.md#session-1-safety-first)). The Rust on the ESP32 (step 7), `frame_version: 2` |
| 2 | Theirs off: `aav_serial_bridge` inactive. The Orin **not** running `car orin` (two muxes would both drive) |
| 3 | On the Motor Pi: `~/aav-jazzy/aav.sh ros2 launch aav_bringup car.launch.py machine:=motor_pi_alone max_speed:=0.3`. Or at boot: `AAV_MACHINE=motor_pi_alone` in `~/.config/aav/car.env` |
| 4 | Check the buttons and sticks first: `~/aav-jazzy/aav.sh ros2 topic echo /drivers/joy/joy` (deadman: button 0; e-stop: button 2) |
| 5 | Session 9's tests 3.1-3.9 with the joystick. Then **turn the joystick off while holding the trigger** (the gap below) |
| 6 | Only then on the ground, at walking pace, with a safety driver |

### What keeps it safe

| Rule | With the Rust ESP32 | With the 2025-26 C++ |
|---|---|---|
| Hold-to-drive: let go of the trigger, it stops | ✅ teleop_twist_joy, one zero on release | ✅ |
| The joystick's USB receiver unplugged | ✅ no commands: twist_mux 0.5 s, ego 0.3 s, the bridge brakes | ✅ |
| **The joystick turned off or out of range, its receiver still in** | ❓ `joy_node` repeats the last state 20 times a second. If the receiver keeps its last report, the car keeps going. **Untested** (TODO 74) | ❓ |
| The Pi, the bridge or the serial wire stops | ✅ brakes 100 ms after the heartbeat stops (QEMU: 111-120 ms) | ❌ the last throttle stays: only the e-stop |
| The network drops | ✅ nothing on the network: all on the Pi | ✅ |
| A speed cap | ✅ ego's `max_speed:=0.3`, on the Pi | ✅ the same |
| A cap in the firmware | ⚠️ only the throttle's top (DAC 700 of 1023): no speed cap, the ESP32 has no wheel speed (TODO 74) | ⚠️ the same |
| The joystick's e-stop button | ✅ `/safety/estop`: the bridge brakes | ✅ |
| The RC transmitter turned off | ✅ brakes within 0.1 s | ❌ no RC timeout |
| The red button, the Kar-Tech e-stop | ✅ hardware: what it cuts is S1 | ✅ |

The 2025-26 path ("like before": `joy_to_ackermann` → `aav_serial_bridge` → the C++) has
the deadman but **no timeout anywhere**: we don't use it.

## Step 9: the lab desktop

| # | Do | You should see |
|---|---|---|
| 1 | `bash car_setup.sh lab_desktop backup upgrade --apply` | updated. A release upgrade only if CARLA's version supports 24.04 ([CARLA](carla.md)) |
| 2 | `bash car_setup.sh lab_desktop install --apply` | `~/ecolo-av` cloned and built (Pixi first, if missing) |
| 3 | CARLA running, and the rehearsal: car day's [session 11a](car-day.md#11a-in-the-lab-the-week-before) | the car drives in CARLA |

## The checklist

Tick each box as it passes. `check` is `bash car_setup.sh <role> check`.

| Step | orin | motor_pi | localization | dash | CAM1 | CAM2 | lab desktop |
|---|---|---|---|---|---|---|---|
| 1 backed up (card image or home + `/etc`) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 1 the Orin's full image (11b) | ☐ | | | | | | |
| 2 `apt full-upgrade`, rebooted | | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 Ubuntu 24.04 (`do-release-upgrade`) | | ☐ | ☐ | ☐ | | | |
| 6 JetPack 7.2 (after the hardware lead's OK) | ☐ | | | | | | |
| 4 our code installed | ☐ | ☐ | ☐ | ☐ | | | ☐ |
| 5 services; rebooted; `check` all OK | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 5 time from the Orin (`chronyc sources`) | serves | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 7 the ESP32 flashed, session 6 passed | | ☐ | | | | | |
| 8 the first moves, on stands | | ☐ | | | | | |
| 9 CARLA rehearsal | | | | | | | ☐ |

## What's untested

| Part | Status |
|---|---|
| `car_setup.sh`'s dry run, every role, and its refusals | [[works]] on a Mac and in CI (`tools/tests/test_car_setup.py`) |
| `car_setup.sh --apply` on a car computer | [[untested]]: this day is its first run |
| `aav-car.service` at boot | [[untested]] |
| `machine:=motor_pi_alone` | [[untested]] on the car; its launch is checked like every machine file |
| `do-release-upgrade` on these Pis | [[untested]] |
| Which computer is the Motor Pi (H1), CAM1-PI's address (C1), `.211`'s job | [[needs-you]]: the hardware lead |
