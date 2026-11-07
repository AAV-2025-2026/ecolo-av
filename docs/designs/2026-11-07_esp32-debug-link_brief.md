# ESP32 debug link

* **Author:** Ben
* **Date:** 2026-11-07

## The plan now

Ben chose this order on 7 Nov: the second review's steps, with the graphs in `hw_panel`. This section
wins over everything below it. Review: `docs/designs/2026-11-07_esp32-debug-link_review-2.md`.
Nothing is built.

**The aim:** see whether the Pi passes its messages to the ESP32 correctly, and take the car's
measurements, one part at a time.

| # | Step | Needs |
|---|---|---|
| 0 | Read today's C++ log over WiFi, filtered | The network only |
| 1 | USB cable. In Pololu's tools: feedback mode, both current limits, steering ends | A cable (check the connector types), the hardware lead |
| 2 | Fix the panel's NaN speed check and the duplicate keys in `vehicle.yaml`. Paper sheets for the brake and wheel size | Ben's OK for the fixes; the hardware lead for the brake marks |
| 3 | The Pi: kernel console off the UART, the inherited service off for good, our bridge on | The hardware lead there, a written way back |
| 4 | Rust with no radio, link version 2, car-day checks | Steps 1 and 3 |
| 5 | Record the normal joystick path. PASS or FAIL: frames written against `frames`, `bad`, `skipped` | Added bag topics, a small script |
| 6 | The return wire, then graphs in `hw_panel`, read from ROS | The wire confirmed; `docs/interfaces.yaml` first |
| 7 | The steering page on the car, then a brake method if still needed | Step 6 |
| 8 | Timing test, then the WiFi pages: `/status.json`, `/scan`, the page, the WebSocket | Step 4 |

Only if a written fault remains that these can't separate: a stand-in for ego, WiFi commands.

| Decided by Ben | |
|---|---|
| Firmware | Rust. The C++ gets no new work |
| Normal driving | Everything goes through ego |
| WiFi | The Rust does the C++'s WiFi jobs, with JSON instead of streaming text; a way to pause |
| Graphs | In `hw_panel`, with the actuators and the sensors |
| If ego is ever taken out | The car still brakes by itself |

| Still open | For | Recommendation |
|---|---|---|
| Rotate the WiFi password, close the C++'s `/update` | Ben, hardware lead | Yes, at step 1's reflash at the latest |
| Which computer and network runs `hw_panel` on the day | Ben | A wired laptop; reach the car from it first |
| Hops with a verdict, and two lines a graph, instead of five | Ben | Yes |
| Tab names PARTS, HAND, EGO, instead of "layer" | Ben | Yes |
| If the return wire can't be confirmed | Hardware lead, then Ben | Graph data comes over WiFi at step 8 |

| Retired | Why |
|---|---|
| "Plain" stand-in with no limits | It loses a stop and the speed cap (review, B2) |
| "Each layer adds one part" | Layer 1 needs what layer 2 "adds" (review, B3). The layers stay as views of the steps |
| Five lines paired by counter, and the fault table | The counter doesn't identify a frame; the proof is counts (review, M1, M2) |
| Signed update page, no cable | A cable settles it (review, B1) |
| Lichtblick first for graphs | Ben chose `hw_panel` |

Everything below is the history of how this was reached.

## Overview

**The idea.** One laptop joins the WiFi the ESP32 is on. It reads structured status (JSONL) and
tests one actuator at a time, without the Pi or ROS in the path. The aim is to rule out the Pi and
ROS when something fails. It is never for driving, and it should be temporary and simple.

**What six reviewers found.** The concept is really three tools under one name, with different risks:

| Tool | Risk | Verdict |
|---|---|---|
| Status lines (JSONL) | Low | Build it |
| Reading them over WiFi | Medium: the radio shares the chip with the control loop | Build it if a timing test passes |
| Commands over WiFi | High: a second way to move the car | Not ready as written |

**Status of this brief.** Nothing was built, flashed or run. Everything comes from reading the repo.
The recommendations below wait for Ben or the hardware lead, except where "Ben's direction" says so.

## Ben's direction, 7 Nov (after the review)

Word for word: `docs/history/messages-2026-11-07.md`. Where this differs from the reviewers' text
below, this section wins.

| Topic | Ben's direction | What it changes |
|---|---|---|
| Which firmware | Rust. The C++ is being replaced | Settles B-2 |
| What the Rust must do | Everything the C++ does, including HTTP and talking to the Pi | WiFi is part of the replacement, not a bench extra |
| The log | A structured format instead of streaming text | JSONL, as planned |
| Normal commands | All 3 actuators, from ROS 2 through the Pi | The normal path doesn't change |
| Direct commands | Only to work around the Pi when we don't know if it's working | A fallback, not a second normal path |

### What's still missing for the C++'s jobs

| The C++ does | Rust today | To do |
|---|---|---|
| Pi's UART frames, RC, Jrks, DAC, direction | ✅ Written, never flashed | Prove it (stage 0) |
| Log on the USB cable | ✅ Text lines | Add JSONL beside them |
| Joins the WiFi | ❌ | Add it |
| Status page, `/` and `/status` | ❌ | Add it |
| I2C scan, `/scan` | ❌ | Add it |
| WebSocket log, port 81 | ❌ | Add it, carrying JSONL |
| Firmware update, `/update`, no password | ❌ | **Recommend not porting.** Awaiting Ben |

### What follows from it

- **The radio is now on while the car drives.** This reverses 6 Nov's "real car has no WiFi" for
  reading, and settles most of B-4. The non-goal below on WiFi in the driving image no longer holds.
- **The timing test now gates the whole replacement.** If WiFi fails it (stage 2), the Rust can't
  do the C++'s jobs on this chip as designed. Nobody has a fallback for that yet. So stage 2 can no
  longer simply stop there. Not measured.
- **Reading may answer most of the question.** The `LINK` line's frame counts and the heartbeat
  counter show if the Pi is sending, and if its commands are fresh. Then "is the Pi working?" needs
  no commands.
- **A hole in the fallback.** A Pi that's sending wrong or stuck frames isn't silent, so the board
  refuses direct commands. That's the case where the Pi is most in doubt. A person must then stop
  the bridge or pull the wire.
- **Throttle has no direct path.** Normal throttle still comes through the Pi. With the Pi in doubt,
  test the DAC by RC (B9).

### Three ways to command (Ben, 7 Nov)

| Way | Path | Used for |
|---|---|---|
| Normal | Joystick and programs → ego → output mux → Pi's bridge → UART → ESP32 | All driving. No direct drive |
| Hardware screen, first choice | Screen → Pi's bridge node → UART → ESP32, skipping ego | Testing hardware |
| Hardware screen, last resort | Screen → WiFi → ESP32 | Only if the Pi's route doesn't work |

### What this needs that doesn't exist

| Gap | Today | Proposal (not decided) |
|---|---|---|
| Two-way UART | Built: 40 bytes at 50 Hz. Off: `uplink` feature, `uplink: false`, GPIO17 wire unconfirmed | Turn it on once the wire is confirmed |
| Test commands through the Pi | Only steering limp and jog (frame version 3). Nothing sends `TestRequest` to the spine (`fsm.rs`) | A new frame field carrying `TestRequest`; the same request type over WiFi |
| Freshness without the Orin | The bridge only relays the Orin's counter, so a dead Orin stops the frames being commands | A separate counter for test commands, from the screen |
| Logs through the Pi | No log on the UART. The uplink has a `kind` byte | New kinds for events and log lines; the bridge publishes them |
| Asked, received, did | Only an echo of the counter | Add received values and the target; the bridge publishes what it wrote |
| Telling firmware apart | Not in the uplink | Add build ID, boot ID, reset reason, link counts |
| Test mode reported | Shown as `Stopped` (`link.rs`) | Report it |
| Our node on the car's Pi | CORTEX ran the inherited `aav_serial_bridge` on 6 Nov | Deploy `legacy_uart_bridge`, and take the kernel console off the UART |

UART room: 115200 baud is about 11,500 bytes a second each way. ESP32 to Pi, the uplink uses 2,000.
Pi to ESP32, the frames at 50 Hz use up to 1,000. A calculation, not a measurement.

### No USB cable (Ben, 7 Nov)

| Effect | Note |
|---|---|
| Without a cable, the only way onto the board is the C++'s `/update` | Whether a Rust image loads that way is untested |
| A bad Rust image would leave the board stuck until someone brings a cable | This is the main risk of the first flash |
| Without a cable, the Rust needs its own update page, checking a signature | Replaces the earlier "leave `/update` out". This reverses the non-goal below on over-the-air updates, if Ben agrees |

### Three debug layers in `hw_panel` (Ben, 7 Nov: the latest direction)

Each layer adds one more part of the car. If a layer fails, the fault is in what it just added.

| Layer | Purpose | Path |
|---|---|---|
| 1 | Move the hardware to get measurements: lock to lock, or small steps | Panel → Pi → ESP32 |
| 2 | Joystick or remote commands | Joystick → Pi → ESP32, no ego |
| 3 | Debug ego's messages | Joystick and programs → ego → Pi → ESP32 |

| Layer | Already built | Missing |
|---|---|---|
| 1 | Steering: limp, steps, marks, lock-to-lock check that stops on resistance, save to a file | Brake: no such page and no way in. Throttle: no measure of what it does |
| 2 | RC direct (skips the Pi). `motor_pi_alone`, joystick-alive check: **these go through ego** (car-day A9b) | A path that skips ego |
| 3 | The whole path, its timeouts | The graph of ego, Pi and ESP32 lines |

**Layer 1 needs more than it looks** (steering, `docs/actuator-tests.md` Way B):

| Needs | State |
|---|---|
| Rust on the ESP32, built with `uplink` | Never flashed |
| GPIO17 wire to the Pi's RX | Unconfirmed (H9) |
| The Jrk's feedback mode set to Analog | Unconfirmed |
| The steering actuator's current limit set low, before any sweep | **Set in Pololu's utility over USB** |
| A heartbeat from an output mux | `motor_pi_alone` makes it on the Pi, so no Orin; but mux and ego do run |

So the safety steps need a USB cable, whatever route the commands take.

**Layer 2: the car still brakes by itself (Ben, 7 Nov).** Bridges only read the output mux's command,
and the mux makes the heartbeat. Skipping the mux too would lose the heartbeat stop, the gate and the
e-stop handling. So: a plain stand-in for ego, with no smoothing or limits of its own, and the output
mux stays. Fits "everything is a drop-in". The joystick's hold-to-drive and alive check stay, and it
starts on stands.

**Throttle** first appears at layer 2, by a person's hand on stands. Layer 1 can't test it safely
without a driven-wheel speed (B9). Wheel sensors are on the front, so they read 0 on stands.

### The watch screen: what Ben is really missing (latest direction, 7 Nov)

A way to watch, over WiFi, how hard each direction is being pushed, where it really is, and that the
Pi passes its messages to the ESP32 correctly. It lives in `hw_panel`, with the layers below. New WiFi
commands wait (proposed). The watching itself doesn't need the two-way UART; layer 1 does, today.

| Endpoint | Does | From the C++? |
|---|---|---|
| `/` and `/status` | The page: live values, the log, pause, filter by value | Yes, better |
| `/status.json` | One snapshot of every value | New |
| `/scan` | The I2C devices found | Yes |
| WebSocket, port 81 | JSONL: status and events | Yes, as JSONL |
| `/update` | Firmware update | Depends on the cable |

| Value | Asked (from the Pi's frame) | Sent to the device | Where it really is |
|---|---|---|---|
| Throttle | Speed value in the frame | DAC code. `ad5311` has a `read()`; use not checked | **Unknown**: no sensor |
| Brake | Accel value in the frame | Jrk target | Jrk position, if feedback is Analog |
| Steering | Steering value in the frame | Jrk target | Jrk position, if feedback is Analog |
| Direction | Sign of the speed | Expander pin | **Unknown**: no sensor |
| Link | Counter | Frames, bad, skipped, repeats (`LinkStats`, exists) | |
| RC | Raw channels | Which source drives | |

The last frame's raw values aren't kept for reporting today: that's new.

**Proposed: one set of JSON, three readers.** The firmware builds one status object.

| Reader | How | Why |
|---|---|---|
| The page | WebSocket | Values update in place. Events list. Raw lines hidden unless asked for |
| `hw_panel` | The same WebSocket | One open connection; events arrive at once |
| `curl`, scripts | `/status.json` | One snapshot, no JavaScript |

Polling alone would miss events between polls and open a new connection for each request. Unverified:
which Rust crate serves this (look at `picoserve` first, and its licence), memory use, and how many
readers the board can hold. A slow reader loses lines and never slows the board.

**Proposed: graphs (Ben, 7 Nov).** One graph each for steering, brake and throttle, over the last
60 s, with numbers beside each.

| Part | Proposal | Why |
|---|---|---|
| History | Kept by the reader, not the board | The board stays simple, and needs no memory for it |
| Each status line | Last, lowest and highest value since the last line | At 5 a second, a short spike between lines would never show |
| Lines on a graph | Asked, sent and really-at, on one scale | The gap between them is the fault you're looking for |
| Scale | Jrk counts for steering and brake; DAC code for throttle | "Asked" converts with the same maths the firmware uses |
| Time | The board's `up_ms`, not the laptop's clock | The clocks may differ |
| Lost lines | A gap in the graph, found from `seq` | A straight line across a gap would look like real data |
| Numbers | Now, average, lowest and highest over the last few seconds | An average alone hides a spike |
| Drawing | Plain canvas in the page, no library from the internet | The car's network may have no internet. Size to be checked |

`hw_panel` draws its own graphs in raylib, from the same lines.

**Proposed: the Pi and the ESP32 on one graph (Ben, 7 Nov).** This one lives in `hw_panel`: it's the
only screen that can read both ROS and WiFi. The browser page stays ESP32 only.

| Line | Comes from | Exists today? |
|---|---|---|
| What ego asked | `/control/car/actuator_cmd` | Yes, in m/s and radians |
| What the Pi wrote to the UART | A new topic from `legacy_uart_bridge` | No. `docs/interfaces.yaml` changes first |
| What the ESP32 received | WiFi status | No: the last frame's values aren't kept |
| What the ESP32 sent to the device | WiFi status | Internally, not reported yet |
| Where it really is | WiFi status | Jrk positions only, if feedback is Analog |

| Lines that differ | Points to |
|---|---|
| Ego and Pi wrote | The bridge's conversion, or a stale stop |
| Pi wrote and ESP32 received | The UART: wire, noise or a wrong frame version |
| ESP32 received and sent | The firmware's rules, such as a latch or stop |
| Sent and really at | The actuator, its power or the linkage |

- Compare Pi and ESP32 in the frame's own values (-1 to 1): they should be identical, so no conversion
  can hide a fault.
- Line up by the frame counter, not by time: the two clocks differ. Version 2 frames only. The counter
  is 8 bits, so at 50 frames a second it wraps about every 5 s. Pair within that window.
- The ESP32's status is slower than the frames, so only some frames get compared. Together with
  `bad` and `repeats`, that's enough to show a broken link. A single bad value could still slip through
  unless the low and high are compared too.
- Needs our bridge on the Pi and the Rust on the ESP32. Neither is on the car today.

| Sensor | Comes from | Reaches the screen by |
|---|---|---|
| IMU, GPS, lidar, radar, camera, battery | Other computers, not the ESP32 | ROS: `hw_panel` reads these already |
| Wheel speed | CAN to the Orin | ROS: `/vehicle/wheels` |
| Steering, brake, throttle, RC | ESP32 | WiFi, as above |

So the ESP32's own page can't show the IMU or GPS: it has no ROS. Only `hw_panel` can show
everything, so it reads two sources, each showing its age. The browser page is the fallback with
no ROS.

Found: `legacy_uart_bridge` doesn't publish `/vehicle/throttle` (`docs/interfaces.yaml:328-331`), so
`hw_panel`'s throttle row would stay empty on today's route.

Calculated, not measured: `/scan` at 100 kHz takes about 14 ms for 126 addresses, longer than the
10 ms tick. So the Rust must probe a few addresses each tick, not all at once as the C++ does.

### Still open

| # | Question | Recommendation |
|---|---|---|
| New | Can someone bring a micro-USB cable for the first Rust flash? | Yes, as the way back if it fails |
| B-3 | Is the WiFi command path in the image that drives, or only in a named bench build? | Depends on the cable answer |
| B-7 | Rotate the WiFi password, and close `/update` on the C++, now? | Yes |
| New | Must the Pi's test route and the WiFi route be one design? | Yes: one `TestRequest`, two ways to carry it |

## Analysis

### How to read the evidence

- **Checked:** reread in the source while writing this brief.
- **Reviewer:** one reviewer read it. Not reread.
- **Unverified:** nobody confirmed it.

| Short name | File |
|---|---|
| `spine.rs`, `fsm.rs` | `firmware/spine/crates/spine-core/src/` |
| `main.rs` | `firmware/spine/boards/esp32-umod/src/main.rs` |
| `link.rs`, `actuators.rs`, `wheel.rs`, `spine_board.rs` | `firmware/spine/crates/spine-board/src/` |
| `ros2_handler.cpp`, `rc_handler.cpp` | `firmware/legacy/aav_umod_esp32/src/modules/<name>/` |
| `main.cpp` | `firmware/legacy/aav_umod_esp32/src/main.cpp` |
| `bridge` | `ros/can_bridge/aav_legacy/aav_legacy/legacy_uart_bridge.py` |
| `bench-link` | `docs/designs/2026-11-06_bench-link.md` |

### 🔴 Blockers

**B1. A silent UART does not mean the car is stopped (Q2).**

A dead Pi, a cut wire and an idle bench all look the same. Silence is also exactly when WiFi would open.

| Firmware | What happens | Evidence |
|---|---|---|
| C++ | No bytes: it returns, and the last throttle stays on | Checked: `ros2_handler.cpp:9-10` |
| Rust | Entering test mode does not need the latch clear, only "standstill" | Checked: `spine.rs:470-481` |
| Rust, this board | Speed always reads 0, so "standstill" always passes | Checked: `main.rs:155-157`, `spine_board.rs:126-127`, `wheel.rs:72-73` |

Result: on Rust, a car still rolling after the Pi dies can enter test mode. `Brake(0)` would then
let the brake go (Checked: `spine.rs:693`), and steering would move.

*Recommendation:* silence is needed, but never enough. See B3 for the person check.

**B2. A Pi restart during a test does not end the test (Q2).**

- Test mode outranks the computer, so returning frames do not interrupt it. Checked: `spine.rs:488-496`.
- The test mode's exit list has no UART term. Checked: `spine.rs:458-462`.
- Our bridge sends stale-stop frames when the stack goes quiet, so a healthy Pi is never silent.
  Checked: `bridge:64-66`.
- A kernel console was on this UART on 6 Nov, so a Pi reboot may put text on the wire.
  Checked: `docs/history/audit-2026-11-06-car.md:49`. Whether it writes at boot is unverified.

*Recommendation:* put the rule in `spine-core`, with tests.

| Moment | Rule |
|---|---|
| To enter | No bytes at all for a set time (number to be decided), then `Exit`, `Enter` from a person |
| During a test | Any UART byte ends the test and latches |
| After that | The actuator holds. The screen says why, and a person must start again |

Noise on a floating RX would then refuse tests. That fails safe, but test it with the Pi powered off.
Unverified: whether GPIO16 floats.

**B3. Being on the network proves nothing about a person at the car (Q3, Q4).**

- The old WiFi password is public (Q34), and there is no longer a physical enable.
- A boot number only stops replay across reboots. Within one boot, a captured command can be sent
  again, so each command also needs a rising counter (`bench-link:89` had one).
- A shared key cannot tell laptops apart.
- It also loses a property of the old design: firmware that is safe to publish (`bench-link:101`).
  Any copied build now holds the key. Reviewer: ELFs are copied by `tools/car_day_build.sh:52-66`.
- `bench-link:81` has a keyless Stop. With WiFi on during a drive, that is a remote hard brake.

*Recommendation:*

| Part | Proposal |
|---|---|
| Tag | HMAC from an audited crate, over boot number, counter and command |
| Key on the board | An untracked file read at build, with `compile_error!` when missing and no example default (Reviewer: `tools/legacy_firmware.sh` silently copies an example today) |
| Key on the laptop | The macOS Keychain |
| Builds | Never publish a command build |
| Order | Rotate the WiFi password (Q34) before the first command build |
| Person check | An RC switch held on: needs no jumper, USB or flash, and fits "a person on RC wins" |
| Sessions | One at a time. A second laptop reads only |
| Stop | Only inside an open test session |

Cost of the RC check: the tool is unavailable when RC is the thing that has failed. The alternative,
a typed confirmation on the laptop, shows the key holder agreed, not that anyone is at the car.

Unverified: flash encryption is not set up anywhere reviewers read, so anyone with a USB cable can
probably read the key. Also, the chip's random numbers may be weak before the radio starts, so pick
the boot number after radio start.

**B4. On the C++, a command key protects nothing (Q1, Q3).**

- `/update` lets anyone on the WiFi replace the firmware, with no password. Checked: `main.cpp:64`;
  `firmware/legacy/aav_umod_esp32/README.md`, "On the WiFi".
- It has no command timeout, no test mode and no latch.
- Reviewer: it reads no Jrk position, and a Jrk missing at boot is never commanded again
  (`jrk_g2.cpp:15`, `main.cpp:143-149`).

Five reviewers say **no commands on the C++**. The sixth, on usability, took no position. Separately,
the open `/update` page is a hazard on the car today, whatever happens to this concept.

**B5. "Temporary" and "nothing flashed at that moment" conflict (Q5).**

If no flash happens at test time, the command path sits in the image that drives the car. The old
design's two protections are gone: the separate build and the physical enable (`bench-link:44-50`,
`:88`). Nothing in the concept removes it, and the open `/update` page shows how long inherited
conveniences last.

*Recommendation:* "no flash" can hold during a bench period, not on a driving car.

| Mechanism | What it does |
|---|---|
| Two Cargo features, off by default | `wifi-status` reads; `bench-link` commands |
| `compile_error!` with `can` | It cannot outlive the UART link |
| Named ELF | `spine-esp32-umod-bench.elf`, so it can't be mistaken |
| Heartbeat and screen | Show "TEST LINK BUILD" at all times |
| Car-day check | Fails if the debug port answers on a car marked ready to drive |
| Symbol test | A release image has no command parser |
| TODO row with an owner and a date | Reflash without it before the first ground drive |

Removal needs a person with a USB cable. Rust has no over-the-air update. That is a cost, and also
a safety gain.

**B6. The "one prior flash" would be the first Rust flash ever (Q1, Q6).**

Rust has never been flashed (`firmware/spine/boards/esp32-umod/README.md`, Overview). Adding the
radio at that flash means a failure has two new suspects, which defeats the point of a tool for
ruling out causes. That flash also needs three signatures and a Pi move to version 2 (Checked:
`docs/car-day.md:536-547`).

*Recommendation:* pass the car-day checks on Rust with no radio first. Then add the radio as one change.

**B7. There is no timing baseline (Q6).**

- All the work is one loop with blocking I2C. The watchdog is fed only after a tick.
  Checked: `main.rs:453-488`. Reviewer: `main.rs:29-30`, and it is enabled before setup (`:305`).
- A failed I2C transfer becomes a stop fault, so a radio stall could stop the car. Reviewer:
  `actuators.rs:133-158`, `spine.rs:429-432`.
- Today's three log lines every 200 ms may already break the tick (Checked: `main.rs:471-476`).
  Estimate, not measured: about 250 to 280 bytes, so 22 to 24 ms at 115200 baud, if the log blocks.
  Unverified: whether it blocks.
- QEMU cannot measure this: it busy-waits. Reviewer: `main.rs:39-44`, `:248-250`.
- The current pass mark is only "written down" (Checked: `bench-link:164`).
- At 20 commands a second, two lost packets nearly reach the 100 ms exit. Stopping is the safe way
  to fail, but a test that keeps stopping is no use.

*Recommendation, in order, on the real I2C devices:*

| # | Measure |
|---|---|
| 1 | Add worst-tick and worst-gap counters. No radio. Log load on and off |
| 2 | Radio joined |
| 3 | A client attached |
| 4 | Access point lost and rejoining |
| 5 | A UDP flood |

Record worst gap, I2C errors, watchdog resets and 100 ms stops. Set the pass number before step 2.
One proposal: worst gap under 30 ms for an hour, with no I2C faults.

**B8. "What the Pi asked" and "Pi silent" cannot both be true (Q7).**

The first column needs the Pi sending. Commands need it silent. So the three columns never apply
during a command. A view with the Pi sending also means the radio is on while the Pi commands. That
reverses `bench-link:47` and `:187` (Ben, 6 Nov: "No for now").

*Recommendation:* name two modes. Ben decides whether Observe may run on the ground.

| Mode | Pi | Commands | Columns |
|---|---|---|---|
| **Observe** | Sending | None | ROS asked, board accepted, Jrk reports |
| **Direct** | Silent | Panel | Panel asked, board accepted, Jrk reports |

**B9. Throttle over WiFi would weaken a tested safety rule (Q4).**

- `Throttle` is refused without a wheel speed, because the speed exit can never fire. Checked:
  `fsm.rs:211-219`, `main.rs:397-400`.
- The wheel sensors are on the front and the motor drives the rear, so they read 0 on stands.
  Checked: `docs/actuator-tests.md:338-340`.
- A cap alone replaces neither. The number already in code is 0.15 (Checked: `fsm.rs:223`), though
  `bench-link:186` treats the cap as open.

*Recommendation:* keep the rule, and keep throttle off WiFi. Test the DAC by RC while reading its value.

### 🟡 Major

**M1. Nothing yet shows that commands are needed (all). One reviewer rated this a blocker.**

All five gaps from 6 Nov were things the team could not *read* (Checked: `bench-link:31-37`).

| Existing tool | Rules out | Limit |
|---|---|---|
| RC direct | Pi and ROS | No precise target. On the C++, brake is only full or off (Checked: `rc_handler.cpp:37`, `:45`) |
| Pololu's USB utility | Pi, ROS and ESP32 | Not the DAC, and not the ESP32's I2C path. Commanding a target from it is unverified |
| Panel through the Pi (Way B) | Nothing below the Pi | Needs the Pi and `uplink` |

The real remaining gap is narrow: **a precise brake or steering target through the ESP32's own I2C.**

*Recommendation:* use read-only plus RC first. Build commands only when a real fault is written down
that these cannot separate.

**M2. The command logic already exists: don't write it again (Q2, Q4).**

`spine-core` has a tested test mode: `Exit` then `Enter`, one actuator, a 100 ms exit, and leaving
always latches. Only the way in is missing. Checked: `fsm.rs:181-183`, `spine.rs:452-485`.

- WiFi should only fill `Inputs::test_cmd`, through a separate narrow trait. As a `CommandLink` it
  would break "exactly one link" and could reach `drive_cmd`. That is how "never for driving" gets
  enforced in the types. Reviewer: `link.rs:33-36`.
- `TestRequest::Steering` takes radians, on a scale nobody has measured. A check needs a counts
  variant. Reviewer: `docs/actuator-tests.md:138-142`.
- `SteerCal` depends on fresh UART frames, so it cannot run during silence, as `bench-link:78`
  implies. Reviewer: `firmware/spine/crates/legacy-link/README.md:76-86`.
- Unverified: the steering rate in test mode.

**M3. The uplink does not carry what the view needs (Q7).**

| Column | Today | Gap |
|---|---|---|
| Asked | `/control/car/actuator_cmd` is m/s and radians | The bridge publishes no copy of the frame it wrote. A new topic means changing `docs/interfaces.yaml` first |
| Received | Only `echo`, a counter | No received values or steering target (Checked: `link.rs:277-295`). `echo` is empty on version 1 (Reviewer: `link.rs:338-366`) |
| Did: steering, brake | Jrk positions | Only with Analog feedback, which is unconfirmed (Checked: `bench-link:157-158`) |
| Did: throttle | Nothing | A DAC write is not motion |

Also:

- `uplink` is off, and its wire is unconfirmed (TODO 50).
- The C++ sends nothing back.
- The uplink reports test mode as `Stopped` (Checked: `link.rs:259-260`).
- The car's Pi ran the inherited `aav_serial_bridge` on 6 Nov (Checked: audit `:49`), so the
  "ROS asked" column needs our bridge on the Pi first.

*Recommendation:* JSONL carries the accepted values, targets and counter. Pair columns by the
counter, never by clock. Ship "ROS asked" last.

**M4. The panel reads only ROS, and only on localhost (Q7).**

- `pixi run hw-panel` never sees the car. Checked: `docs/actuator-tests.md:220`.
- Reviewer: a second thread can feed the panel's existing channel, and stale rows already exist
  (`ros/hud/aav_hud/README.md:167-168`). Panel source not read.
- `bench-link:146-147` assumes no ROS, so this changes that design.
- Reviewer: a Mac may upset the car's DDS (audit `:112`).

*Recommendation:* one screen, with every source optional and showing its age. WiFi must work with
no ROS at all.

**M5. The stops do not reach a direct test the way people expect (Q2).**

- The board cannot see the red button until `estop-input` is wired. Checked: `main.rs:142-152`.
- `/safety/estop` reaches the board only in UART frames, which are absent in a direct test.
- A laptop still streaming might move an actuator when the button is released. Unverified: what the
  button cuts, and whether the Jrks then report a fault.
- The panel's E-STOP goes over ROS, so with no Pi it reaches nobody. Reviewer:
  `ros/hud/aav_hud/README.md:123`.

*Recommendation:* wire `estop-input` before commands. Label the button STOP TEST, and always show
"Real stop: red button". When the link is lost, grey it out and say "NOT CONNECTED: use red button".

**M6. The direct path skips locks the documents promise (safety rule).**

"`hw_panel` is the only screen that drives, and only through twist_mux, ego and the spine"
(Reviewer: `ros/hud/aav_hud/README.md:179`). Direct mode skips the geofence and every other ROS
lock. The rule says locks are never bypassed.

*Recommendation:* list which locks apply on this path, which don't, and why. Ben decides whether
that is acceptable, then the README changes.

**M7. The JSONL has no owner, and would be a fourth status format (structure).**

`interfaces.yaml` covers ROS only. There is no schema version, boot ID or build ID (Checked:
`bench-link:57-59`).

*Recommendation:* own it like `aav.dbc`: one schema file, a version field and golden lines. Build
it in a logic crate, from the same struct as the uplink. The heartbeat carries `schema`, `boot_id`,
git hash, features and `last_reset`. The panel reads an unknown schema but sends no commands to it.

**M8. Replacing the text log breaks working things (migration).**

- `tools/esp32_qemu.py` parses `EVENT`, `STATUS` and `LINK` lines. Checked: `:19-21`, `:134-139`.
- Car-day steps read them. Checked: `docs/car-day.md:547`. Reviewer: `:572`, `:828`.
- On the C++, only its own page parses `STATUS:`. Reviewer: `web_handler.cpp:53`.

*Recommendation:* add JSONL beside the text. Retire the text only after those have moved. Leaving
the C++ as it is also keeps a known rollback.

**M9. Rotating the WiFi password strands the rollback image (Q3).**

The backup holds the old password (Checked: `docs/car-day.md:534`).

*Recommendation:* rotate, rebuild and flash the C++, take a new backup, delete the old one, and only
then go to Rust. Keep the command key out of that backup.

**M10. Reading the Jrk errors clears them (Q7).**

A second read by JSONL would hide faults from the tick. Reviewer: `actuators.rs:130-132`.

*Recommendation:* JSONL copies the tick's values and never reads a device itself.

**M11. The screen hides the states a student needs (Q2, Q7).**

"Pi silent" is five different things:

| Real state | UART | On screen |
|---|---|---|
| Bridge running, nobody driving | Brake frames, 50 a second | PI SENDING |
| Orin dead, bridge alive | Frames with a frozen counter | PI COMMAND STALE |
| Bridge crashed | Nothing | NO UART DATA |
| Wire off, port failed | Nothing | NO UART DATA |
| Pi off | Nothing | NO UART DATA |

The last three look the same to the board, so the screen must never say "Pi absent" as a fact.

Each test ends with one line, so a failure points somewhere:

| Result | Tells you | Next step |
|---|---|---|
| NOT SENT | Laptop or WiFi | Check the network |
| REFUSED: reason | Board said no | Follow the reason |
| LINK LOST, stopped | WiFi, not the actuator | Move closer, repeat |
| ACCEPTED, Jrk error | Name the flag | Tell the hardware lead |
| ACCEPTED, no movement | Actuator or linkage | Check by eye |
| MOVED to N | Actuator chain works | Done, note the build |

Other screen rules:

- A pass rules out the Pi and ROS, but not this firmware. Show the build beside the result.
- Each refusal gives one action, such as "PI SENDING: stop `legacy_uart_bridge` on the Motor Pi".
- A restart reads "BOARD RESTARTED", not "wrong key".
- Add NO SENSOR and NO PI beside OK, STALE and NEVER. Neither is a fault.
- Label by source: "ROS asked", "Panel asked", "Board accepted", "Jrk reports".
- For the throttle: "DAC written: watch the rear wheels". Never "did".
- Use a full-width band: DIRECT TO ESP32, NOT ROS. Hide the ROS drive buttons in this mode.

**M12. The name and the words mislead (comprehension).**

| Word | Problem |
|---|---|
| debug | `debug_hud` never touches an actuator. This moves the car |
| the Pi | There are three: say Motor Pi. Commands start on the Orin (Reviewer: `bridge:64`) |
| spine | The docs separate "Today (ESP32)" from "With the spine" |
| heartbeat | Three meanings, only some bearing on safety |
| bench | Would run on the real car |
| test mode | Already a `spine-core` mode: reuse it, or rename |

*Recommendation:* call it the "direct test link", and put a one-table glossary at the top of the design.

**M13. Documents will contradict each other (structure).**

- `bench-link:47`, `:88`, `:92` and `:155` disagree with this concept.
- So does `TODO.md:12`. Checked.
- The board README says "exactly one link".

*Recommendation:* when a design lands, mark `bench-link` superseded and update TODO 126.

| Decision | Owner |
|---|---|
| Status schema | A contract file |
| Transport | Board README |
| Test authority | `spine-core` |
| View | `panel-core` |

### 🟢 Nits

- `jrk-g2` has no supply-voltage read, though `bench-link:65` lists it. It would add I2C time. Reviewer.
- A WebSocket means TCP, HTTP upgrade and SHA-1 on the board. UDP to one laptop may be simpler, but
  a browser can't read it. RAM use is unverified.
- Stale limit 1.0 s against a 1 s heartbeat would flicker. Reviewer: `ros/hud/aav_hud/README.md:134`, `bench-link:64`.
- `tools/esp32.sh check` needs the new feature mixes. Reviewer: `:172-179`.
- Reuse "type the test's name" as the confirmation. Reviewer: `docs/actuator-tests.md:94`.
- The Rust address is undecided: DHCP or a reservation.
- The radio ties this to the classic ESP32. Keep its code in the board crate so it can be dropped.
- `fsm.rs:181-183` lists two ways in for test requests: a new CAN frame, or a bit in DRIVE_CMD. WiFi
  would be a third, so update that comment.

### Answers to the eight questions

| # | Answer |
|---|---|
| 1 | Commands: Rust only (five reviewers, none against). Read-only on the C++: reviewers split, see below |
| 2 | One rule is not enough. Add a settling time, a person check, and "any byte ends the test" |
| 3 | Not adequate as written. Add a counter, a person check and rotation. The key lives in an untracked build file, never in published builds |
| 4 | Enforce with types (WiFi can only make `TestRequest`), hold-to-run, a session time limit, and latching on exit. Throttle stays off WiFi. It stays off even with a cap, until a driven-wheel speed exists (TODO 49b) |
| 5 | Nothing removes it today. See B5 |
| 6 | Measure the worst tick gap with no radio first. See B7 |
| 7 | Not today. It needs new fields, a second reader in the panel, and two named modes |
| 8 | Yes, with an earlier stage than proposed. See the staging table |

### Where reviewers disagreed

| Topic | Positions | This brief |
|---|---|---|
| Read-only JSONL on the C++ | Structural: useful on the car now. Design: only as an exception, with `/update` removed. Three others: leave it alone | Leave it alone. Its README says "reference only", it stays the rollback, and it reads no positions. Ben could overrule this if the Rust flash slips |
| Commands | Zoom-out: unjustified. Others: stage them | Gate them on a written fault (M1) |
| Person check | Design: RC switch. Others: a person's `Exit`, `Enter` or START | Ben and the hardware lead. Only RC shows presence |
| Silence | No bytes, or no valid frame | No bytes to enter; any byte ends the test (B2) |
| Panel before commands? | Readiness: commands first. Design, codebase, comprehension: panel first | Panel first: students learn the screen before it can move anything |

### Not verified

- Whether `esp-radio` works with esp-hal 1.2.2 and esp-rtos 0.4, and whether it fits in RAM.
- Any timing. Nothing has been measured.
- Whether the log blocks the tick.
- Whether Stage 0 has already happened on the car.
- Off-repo scripts in `~/aav-audit` were not read.

## Goals vs. Non-Goals

**In-Scope Goals:**

- See live, on the car, what 6 Nov could not show: RC channels, Jrk health, position and events.
- Structured status with a version, usable with or without the Pi.
- Tell "the Pi or ROS failed" from "the board or actuator failed".
- Give each test a one-line verdict.
- Have a written way of removing it.
- If justified later: steering and brake tests, one at a time, through the existing test mode.

**Out-of-Scope Non-Goals:**

- Driving, or any path to `drive_cmd` from WiFi.
- Throttle over WiFi, until a driven-wheel speed exists and the hardware lead sets the cap.
- Clearing an e-stop or latch from WiFi. Weakening any existing `spine-core` rule.
- Commands on the C++.
- ~~WiFi on the car's normal driving image.~~ Ben, 7 Nov: the Rust does what the C++ does, including
  WiFi. Direct commands in that image are still open (B-3).
- Replacing the binary UART uplink for ROS.
- Over-the-air firmware update.
- Multi-laptop control.

## Key Decisions & Staging for Next Steps

Everything here is a **recommendation**. Nothing is decided.

### Waiting for Ben

| # | Decision | Recommendation |
|---|---|---|
| B-1 | Commands now, or only after a written fault read-only can't separate? | After |
| B-2 | Firmware for new work | Rust. Leave the C++ unchanged |
| B-3 | Accept that "no flash" holds only for a bench period, with a reflash before the first ground drive? | Yes |
| B-4 | May read-only WiFi run while the Pi commands, on the ground (Observe)? This reverses 6 Nov | Only after the timing test, and on stands first |
| B-5 | Shared key, or keep the earlier public-key design? | Shared key, with a counter, in unpublished builds only |
| B-6 | Which locks may the direct path skip? | Write the list first |
| B-7 | Rotate the WiFi password (Q34) and close `/update`, now, as a separate job? | Yes. It is needed whatever happens here |
| B-8 | Name | "Direct test link" |
| B-9 | Who owns removal, and by when? | A named person, before the first ground drive |

### Waiting for the hardware lead

| # | Decision |
|---|---|
| H-1 | Which spare RC channel is the person check, if any |
| H-2 | Wire `estop-input`, and say what the red button cuts |
| H-3 | Confirm the uplink wire (TODO 50) |
| H-4 | Each Jrk's feedback mode, and where the position sensors connect |
| H-5 | The throttle cap: confirm or change the 0.15 in code, once throttle tests are possible |
| H-6 | Present and signing for each flash to the car |
| H-7 | With Ben: the worst-gap pass number, before any radio |

### Stages

Each stage is useful alone and can stop there.

| Stage | Adds | Useful alone because | Passes when | Rolls back to |
|---|---|---|---|---|
| 0 | Rust on the car, no radio, tick counters | Removes Rust as a suspect, gives the baseline | Car-day 6c checks; numbers recorded | C++ backup, USB |
| 1 | JSONL logic crate and schema, over USB, beside the text | Live Jrk health, no timing risk | Laptop tests; `qemu-check` still passes | Stage 0 ELF |
| 2 | Radio, read-only: status page, `/scan`, JSONL over a WebSocket | The view with no cable; the C++'s WiFi jobs, without `/update` | B7 tests meet the pass number. **If not, stop and decide again: the C++ can't be replaced as designed** | Stage 1 ELF |
| 3 | Panel reads it, sources with ages, Observe view | Answers the 6 Nov questions | Each source goes stale alone; works with no ROS; old and new schema | Panel only |
| Gate | Is a written fault left that stages 0 to 3 and RC can't separate? | | Ben decides | |
| 4 | Steering and brake commands, bench build only, filling `test_cmd` | The narrow gap in M1 | See below | Stage 3 ELF |
| 5 | Throttle | Only with a driven-wheel speed and the cap | With the hardware lead, on stands | Stage 4 ELF |

Tests stage 4 must have:

- Pi killed while driving: brake and latch, and WiFi can't unlatch.
- Pi rebooted during a test.
- Garbage bytes on the UART.
- Laptop lost mid-command.
- Bad tag, and replay.
- E-stop during a test, and release while a laptop is still streaming.

### Before `/egm-draft`

1. Ben answers B-1, B-3 and B-7. They set the size of the design.
2. Split it into two designs: read (stages 0 to 3) and commands (stage 4 on), each with its own
   safety case.
3. Write down which `bench-link` parts survive, so only one live design remains.
