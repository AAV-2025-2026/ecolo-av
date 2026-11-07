# Hardware debug: one part at a time

**The aim:** see whether the Motor Pi passes its messages to the ESP32 correctly, and take
the car's measurements, one part at a time. The plan and its two reviews:
`docs/designs/2026-11-07_esp32-debug-link_brief.md` ("The plan now" wins).
What makes the ESP32 brake, and what a laptop can and can't do: [ESP32 safety](esp32-safety.md).

**Status:** written 7 Nov. Nothing here has run on the car. The link check is tested on
made-up recordings only.

## The three layers

```text
 Layer 1  PARTS   the calibration page ─► Pi ─► ESP32 ─► steering Jrk      (lock to lock, small steps)
 Layer 2  HAND    joystick ─► ego ─► mux ─► Pi ─► ESP32 ─► Jrks and DAC    (all on the Pi, auto-brake kept)
 Layer 3  EGO     programs ─► ego (Orin) ─► mux ─► Pi ─► ESP32             (what ego asks, what went out)
```

| Layer | For | Proves | Needs |
|---|---|---|---|
| 1 | The steering's ends and centre, by the hardware panel | the steering Jrk moves where it's told, and reports it | Rust, the uplink wire (H9), link version 3 |
| 2 | Driving by hand, on stands | the Pi's frames reach the ESP32: `pixi run link-check` | Rust, link version 2 |
| 3 | Debugging ego's messages | what ego asked is what the Pi wrote | layer 2 passed, the Orin |

The layers are views of the plan's steps, not a strict order. Layer 1 already needs ego and
an open gate (review 2, B3): the firmware reads a calibration request only from a frame with
a new counter.

## Before any layer

| # | Do | Where | Done |
|---|---|---|---|
| 1 | The car on stands, all four wheels off the ground; the Kar-Tech stop in a hand | [car day, A1](car-day.md#session-1-safety-first) | ☐ |
| 2 | **A USB cable** to the ESP32 and to each Jrk. Check the connector types first | the hardware lead | ☐ |
| 3 | **Each Jrk's current limit, set over USB** in Pololu's Jrk G2 utility (Motor tab), before any sweep or step. Both Jrks: steering and brake | [Way A, A4](actuator-tests.md#way-a-pololus-utility-over-usb-car-day) | ☐ |
| 4 | The Motor Pi's UART ready: console off, theirs off at boot, ours on | [car day, A7b](car-day.md#a7b-the-motor-pis-uart-ready) | ☐ |
| 5 | The Rust ESP32 flashed and its checks passed, link version 2 | [car day, A8](car-day.md#session-6-the-esp32) | ☐ |
| 6 | Recording on: `~/aav-jazzy/aav.sh tools/record.sh <name>` | it keeps `/control/car/link_frame` | ☐ |

| Current limit (hardware lead) | Steering Jrk | Brake Jrk |
|---|---|---|
| Old value | ______ | ______ |
| Set for today | ______ | ______ |

!!! warning "Throttle tests need a wheel speed"
    The actuator tests refuse a throttle test on the real car while `/vehicle/odom` can't
    see the driven wheels. Don't work round it. Known bug, not fixed: the hardware panel's
    "is the car moving?" check passes on NaN (review 2, M5). Today's board says NaN, so
    the panel can't be trusted on that point.

## Layer 1: the parts

**The steering, lock to lock, or small steps.** The hardware panel's STEERING CAL page:
[Way B](actuator-tests.md#way-b-the-hardware-panel-rust-firmware). Limp and mark by hand,
or HOLD and step 25 counts a press, then the LOCK-TO-LOCK CHECK.

| Needs | Setting |
|---|---|
| The Rust with the uplink, H9 confirmed | `uplink: true` |
| Link version 3 | `frame_version: 3` |
| The hardware lead's say-so, this session only | `steering_calibration: stands`, back to `none` after |
| The Jrk's feedback analog | Pololu's utility, Feedback tab |

**The brake: no page yet.** Use Pololu's utility over USB, and the sheet below. The
hardware lead rules on hands near the wheels.

### The brake sheet

| Point | How to find it | Counts | Note |
|---|---|---|---|
| Released | the brake actuator fully back | ______ | |
| First drag | a rear wheel turned by hand starts to drag | ______ | hand on the wheel: the hardware lead's call |
| Holds | the wheel won't turn by hand | ______ | |
| Hardware stop | the actuator's end; stop before it strains | ______ | |
| Current limit used | | ______ A | |
| Firmware today | released 400, full 3500 | | the numbers go in `calibration.rs`, not `vehicle.yaml` |

`Measured by: ________ · Hardware lead: ________ · Date: ________`

## Layer 2: by hand, through the Pi

**The joystick on the Motor Pi, through ego, all on the Pi** (`machine:=motor_pi_alone`).
The auto-brake stays: the ESP32 brakes 100 ms after the heartbeat stops, ego caps the speed
at 0.3 m/s. No stand-in without these (review 2, B2). The steps: [car day,
A9b](car-day.md#a9b-the-joystick-on-stands).

| # | Do | You should see |
|---|---|---|
| 1 | Start recording on the Motor Pi: `~/aav-jazzy/aav.sh tools/record.sh link` | a folder in `bags/` |
| 2 | At the same time, on the laptop with the ESP32's USB cable: `vendor/cargo-tools/bin/espflash monitor \| tee esp32.log` | `LINK t=... frames=...` lines |
| 3 | A9b steps 3-5: **move the stick**, steer, stop, a few times, for a minute | the wheels follow |
| 4 | Stop both recordings | |
| 5 | `pixi run link-check bags/<folder> --esp32 esp32.log` | PASS, FAIL or NOT TESTED |

**Move the stick.** A parked car changes nothing, so the check says NOT TESTED, never PASS.

### What the link check says

| Says | Means | Do |
|---|---|---|
| **PASS** | every frame counted: the Pi wrote them, the ESP32 took them, `bad` and `skipped` flat | write down the line "a loss of up to N frames would not show" |
| **FAIL**: lost | the ESP32 took fewer frames than the Pi wrote | the wire, the speed (115200), the console (A7b) |
| **FAIL**: second writer | the ESP32 took more frames than the Pi wrote | theirs still running? A7b step 4 |
| **FAIL**: bad or skipped rose | frames turned down | `frame_version` on both ends; noise on the wire |
| **FAIL**: values differ | a good frame with other values | a reporting bug, not the wire: tell Ben |
| **NOT TESTED** | no data on one side, nothing changing, or no frame both saw | record again, both at once, moving the stick |

How it knows a frame: by its counter **and** its check byte, never the counter alone. It
samples about one frame in five (`link_frame_rate_hz: 10`); the counts are the proof.

**Today's firmware writes text only** (`LINK` lines), with no frame to match. Then the check
shows the ESP32's counts, but the ESP32 hop stays NOT TESTED until the Rust writes its JSON
status lines (`firmware/status/README.md`). Not built yet.

## Layer 3: ego's messages

The Orin runs ego and the mux; the Motor Pi runs only the bridge.

| # | Do | You should see |
|---|---|---|
| 1 | Layer 2 passed | |
| 2 | The Orin: `~/aav-jazzy/aav.sh ros2 launch aav_bringup car.launch.py machine:=orin max_speed:=0.3 gps:=false lidar:=false stands:=true` (as A8 step 4); the Motor Pi: `~/aav-jazzy/aav.sh car motor_pi` | the gate OPEN |
| 3 | Record on the Orin: `~/aav-jazzy/aav.sh tools/record.sh ego` | |
| 4 | Drive from the keyboard, or an actuator test on stands | the wheels follow |
| 5 | `pixi run link-check bags/<folder> --esp32 esp32.log` | as layer 2 |
| 6 | Compare `/ego/actuator_cmd` (what ego asked) with `/control/car/link_frame` (what went out) in Foxglove or Lichtblick | the same moves; the frame's values are -1..1 |

`/control/car/actuator_cmd` is the mux's output: silent while the gate is shut. Ego's own
is `/ego/actuator_cmd` (review 2, M3).

## The rollout sheet (the wheel's size)

For `wheel_diameter` in `vehicle.yaml` (0.36 today, tape-measured). On the ground, power off,
pushed by hand. How to release the brake unpowered: the hardware lead's call.

| # | Do |
|---|---|
| 1 | Chalk a line on the tyre and the ground, at the bottom of a rear wheel |
| 2 | Push the car straight until the mark is at the bottom again, **5 turns** |
| 3 | Mark the ground, measure the distance |
| 4 | Do it three times |

| Run | Turns | Distance (m) | Diameter = distance ÷ (turns × 3.1416) |
|---|---|---|---|
| 1 | 5 | ______ | ______ |
| 2 | 5 | ______ | ______ |
| 3 | 5 | ______ | ______ |
| Mean | | | ______ |

`Measured by: ________ · Date: ________ · Tyre pressure: ________`

## Open

| Question | For |
|---|---|
| Which computer and network runs `hw_panel` on the day | Ben (recommended: a wired laptop) |
| The return wire, GPIO17 to the Pi's RX (H9) | the hardware lead |
| How to keep the counter moving while layer 1 stands still | untested |
| The JSON status lines in the Rust firmware, the Pi link's verdict, `/health` | built, not flashed: `firmware/status`, `pixi run esp first-check` ([first flash](esp32-bench.md#2a-the-first-check-the-gate)) |
