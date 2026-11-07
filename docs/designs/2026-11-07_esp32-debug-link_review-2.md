# ESP32 debug plan: second review

* **Date:** 2026-11-07

## Overview

**Verdict.** The goal is right, but the plan is bigger than the question and its order doesn't hold.

| Part of the plan | Verdict |
|---|---|
| Rust replaces the C++, with its WiFi jobs | Keep. It doesn't need to come before the first answer |
| JSON status | Keep. Start with `/status.json` |
| Graphs in `hw_panel` | Start with a stock plot. Most of the data can come over the uplink |
| Layer 1 | Real, but it isn't "hardware only" |
| Layer 2, plain stand-in | Unsafe as written, and it proves little |
| Layer 3 | Mostly a recording of the same path as A9b |
| WiFi commands, deferred | Good. This removes most of the first review's risk |

**The first answer needs almost nothing new.** "Is the Pi passing messages correctly?" can be mostly
answered from counters that exist today, once a USB cable is at the car.

**How this was done.** Six reviewers read the repo, then the synthesizer reread the claims that
carry the most weight. Nothing was built, flashed or run. Every rate and timing is a calculation.

| Mark | Meaning |
|---|---|
| **Checked** | Reread in the source for this report |
| **Reviewer** | One or more reviewers read it. Not reread |
| **Unverified** | Nobody confirmed it |

Paths are from the repo root. Short names:

| Name | File |
|---|---|
| brief | `docs/designs/2026-11-07_esp32-debug-link_brief.md` |
| relay | `ros/can_bridge/aav_legacy/aav_legacy/uart_relay.py` |
| protocol | `ros/can_bridge/aav_legacy/aav_legacy/legacy_protocol.py` |
| reader | `ros/can_bridge/aav_legacy/aav_legacy/uplink_reader.py` |
| output_mux | `ros/io_mux/aav_io_mux/aav_io_mux/output_mux.py` |
| ego_node | `ros/ego/aav_ego/aav_ego/ego_node.py` |
| teleop | `ros/drivers/aav_teleop/config/teleop_twist_joy.yaml` |
| car.launch | `ros/bringup/aav_bringup/launch/car.launch.py` |
| link.rs | `firmware/spine/crates/spine-board/src/link.rs` |
| spine.rs | `firmware/spine/crates/spine-core/src/spine.rs` |
| main.rs | `firmware/spine/boards/esp32-umod/src/main.rs` |
| state.rs, calibration.rs | `ros/hud/aav_hud/crates/panel-core/src/` |
| messages | `docs/history/messages-2026-11-07.md` |

## Findings

### 🔴 Blockers

**B1. Without a USB cable, the plan can't start.** Checked, except where marked.

| Plan says | But |
|---|---|
| First Rust flash has no radio | All Rust logging goes to the USB cable (`boards/esp32-umod/README.md`, Log). With no cable and no radio, nobody sees anything |
| Way back is the USB cable (brief:696) | There's no cable (brief:88-94) |
| No cable means a signed update page (brief:94) | That needs the radio, which contradicts "no radio first" |
| Layer 1 can start | The current limit is set over USB (brief:119-122) |

Whether a Rust image loads through the C++'s `/update` is untested (brief:92). The first flash already
needs people at the car, and car day already lists the ESP32's cable (Reviewer: `docs/car-day.md:501-504`).

*Needed:* make the cable step 1, not an open question. It also removes the signed update page. Check
the connector types first: nobody confirmed "micro-USB" for the ESP32 or the Jrks. Unverified.

**B2. A stand-in with "no limits" removes a stop and the speed cap.** Five reviewers raised this.
The stand-in fits on `/ego/actuator_cmd`: the gate never looks at who publishes (Checked:
output_mux:24-25, :109-112). But it must do these jobs, none of which the brief lists:

| Job | Why | Evidence |
|---|---|---|
| Publish on a timer, always | The heartbeat beats once per command. The joystick sends only while held, plus one zero. Without a timer, the board latches at each release | Checked: output_mux:109-112, teleop:2 |
| Time out to zero | A timer repeating the last throttle keeps the heartbeat moving. The bridge's timeout and the board's 100 ms stop then see a healthy link, with nobody at the stick | Checked by reading, not run: ego_node:117-121, relay:160-162, :175-177 |
| Keep a speed cap | A9b's cap is ego's `max_speed:=0.3`. Without it, full stick is 1.0 m/s: DAC about 233, not 70. The firmware's only forward limit is the DAC top of 700 | Checked: `docs/car-day.md:705-706`, teleop:27, protocol:129, spine.rs:665-669 |
| Turn a turn rate into an angle | The stick sets a turn rate, so it can't steer at speed 0, and steering only comes with throttle. At 0.3 m/s, full stick works out to 1.07 rad against a 0.5 rad limit | Checked: teleop:11-14. Worked out here, wheelbase 1.561 m |

Which protections stay, if the stand-in reads `/control/cmd_vel`:

| Protection | State |
|---|---|
| Hold-to-drive, joystick-alive, twist_mux e-stop lock | Stay (upstream) |
| Output mux gate, bridge e-stop and 0.3 s timeout | Stay |
| Board's 100 ms stop | Stays only with the timeout job above |
| Speed cap | **Lost** |
| Steering limit, 0.6 rad/s rate, reverse cap, DAC ramp | Stay on **Rust** (Checked: spine.rs:652-659, :670-674). The rate and ramp are firmware's, so taking ego out doesn't remove all smoothing |
| Reverse cap and timeout on the **C++** | Absent. Layer 2 should require Rust |

*Needed:* if a stand-in is built, write these four jobs in as its contract and test them before it
moves anything. Options are in "Decisions for Ben", D2.

**B3. "Each layer adds one part" is false, so "the fault is in what it just added" fails.**

- Layer 1 needs Rust, the uplink wire, version 3 frames, `steering_calibration: stands`, and Jrk
  analog feedback (brief:116-120, `docs/actuator-tests.md:207-211`).
- It also needs ego and an open gate. The firmware returns before it reads the calibration request
  when the counter hasn't moved (Checked: link.rs:395-398, :406), and the counter moves only for
  commands the mux passes (Checked: output_mux:109-112).
- So layer 1 already contains everything layer 2 "adds". Layer 2 then removes ego and adds new code.
- The docs already place this later: "Not on car day" (Checked: `docs/actuator-tests.md:202`).

*Needed:* use the real order in "Smallest useful first version". Layers become views of those steps.

**B4. `hw_panel` as the main screen has no agreed computer or network.**

| Source | Says | Mark |
|---|---|---|
| `docs/hud.md:822` | "the Orin's own screen or a wired laptop, not a Mac over WiFi" | Checked |
| `one-window.md:17`, `:19` | Raylib only for the HUD and street map on the Pi. The Orin runs no graphics | Checked |
| `docs/hud.md:819` | `pixi run hw-panel stands:=true` on the car's stands | Checked |
| `docs/actuator-tests.md:220` | `pixi run hw-panel` is localhost-only, "never sees the car" | Checked |
| Ben | Only has network access (messages:11) | Checked |
| `motor_pi_alone.yaml:16-23` | No IMU, GPS or wheel nodes, so those rows are empty at layers 1 and 2 | Checked |

"Only `hw_panel` can read both" isn't a property of that program. Any node on a computer that reaches
both networks could do it. Nobody has confirmed that one laptop can reach both on the day, and a Mac
may upset the car's DDS (Reviewer: `docs/history/audit-2026-11-06-car.md:112`).

*Needed:* one table: which computer, which network, which domain, for each step.

**B5. The brake has no definition of done.** Listing "no page" understates this. Checked, except where marked.

| Missing | Note |
|---|---|
| What's measured | Released, first drag, holds, hardware stop. A7 only checks that it holds (Reviewer: `docs/car-day.md:483-497`) |
| How it's judged | First drag needs a hand on a wheel, but sweeps say hands clear (Reviewer: `docs/actuator-tests.md:157`). The hardware lead must rule |
| Its current limit | brief:119 lists steering only |
| Where the numbers go | Counts go in `calibration.rs` in the firmware, not `vehicle.yaml` (Reviewer) |
| A method | `SteerCal` needs the brake on, so it can't be copied (Checked: link.rs:406-411) |

A cheaper route may exist. A frame with speed 0 and negative accel already sets a brake target (Checked:
link.rs:167), and `/vehicle/brake_actuator/raw` is already published but unread by the panel (Checked:
`aav_hud/README.md`, panel table). So a bridge mode could step the brake with no new frame. Whether
this gets past the latch on a real board: Unverified. Try it in QEMU first.

*Needed:* a paper brake sheet before any page. Pololu's tools first (Reviewer: `jrk2cmd --status`,
`docs/audit-questions.md:33`).

**B6. The Pi's UART isn't ready, and no step says so.** Checked.

- The kernel console is on the ESP32's UART (`docs/history/audit-2026-11-06-car.md:49`). `docs/car-day.md`
  has no console step at all. The brief has one table row (brief:83).
- `docs/car-day.md:543` uses `systemctl stop`, not `disable`. If `aav_serial_bridge` starts at boot, a
  reboot brings back a second writer. Unverified. A login prompt on that port: also Unverified.

*Needed:* one written Pi step for console, login prompt and service, with its rollback, before the uplink.

### 🟡 Major

**M1. The counter doesn't identify a frame.** Checked.

- Commands and counters come as separate messages, and the bridge writes on its own timer
  (output_mux:111-112, relay:107-115). A frame can pair new values with an old counter.
- Stop frames repeat the counter with **different values** (relay:13-15, :184-185). So one counter
  can mean several frames, exactly when there's a fault.
- The firmware updates its counter before the repeat check, then drops the repeat (link.rs:383, :395-398).
  So "received" needs a definition: last seen, or last used.

*Needed:* pair on counter plus the frame's CRC byte (Reviewer proposal). That also avoids JSON rounding
breaking "identical". Show frozen-counter periods as "no fresh frame", not as a difference.

**M2. The brief's fault table points the wrong way.** Checked.

| Brief says (brief:197-202) | Really |
|---|---|
| Pi wrote vs received differ: "wire, noise or a wrong frame version" | Bad frames are dropped and counted (link.rs:376-380). A mismatch on a good frame is more likely a pairing or reporting bug |
| Received vs sent differ: "firmware's rules" | Normal: steering slews and throttle ramps (spine.rs:659) |
| Sent vs really at differ: actuator fault | Normal while it moves (Reviewer) |

The real proof of the wire is **counts, over the same interval**: frames written against `frames`, plus
`bad` and `skipped` staying flat, and the counter moving.

**M3. Some lines don't mean what their labels say.**

| Line | Problem | Mark |
|---|---|---|
| "What ego asked", from `/control/car/actuator_cmd` | That's the mux's output, silent when the gate is shut. Ego's is `/ego/actuator_cmd` | Checked: output_mux:109-112 |
| Ego on the brake graph | Ego has no brake value. In open mode, the frame's brake is 0, 0.3 or 1.0 | Checked: protocol:127-132, :154 |
| Layer 1 sweeps on the frame graph | Frames carry stop values, and the jog target sits elsewhere. The graph looks flat | Checked: relay:171-174 |
| "Where it really is" | It's what the Jrk reports. A slipped linkage still reads fine | Reviewer |
| `/vehicle/steering.command` | Ego's angle, not the board's target | Checked: reader:72-74 |
| "Version 2 frames only" (brief:206) | Layer 1 needs version 3 | Checked: relay:143 |

**M4. Five lines hide the verdict, and can show a false pass.** One reviewer rated this a blocker.

- Three graphs mean 14 lines and 56 numbers. Reviewer's count.
- Identical lines sit on top of each other, so "matching" and "one line missing" look the same.
- A parked car agrees on every line, so no changing value was ever compared.

*Needed:* first a chain of hops, `Stand-in or ego > Pi > ESP32 > Jrk`, each saying `OK`, `DIFFERENT`,
`STALE`, `NO DATA` or `NOT TESTED: value hasn't changed`. A graph opens from a hop, showing two lines.
Never green without a changed value. Say "sampled N frames", never "every frame".

**M5. An existing bug: the panel's "is the car moving?" check passes on NaN.** Checked by reading, not run.

- On this board, `/vehicle/status` speed is NaN (reader:65-67).
- `seen_speed` passes it through (state.rs:312-317), and no NaN check is on that path.
- `NaN.abs() >= 0.05` is false, so `readiness` says allowed (calibration.rs:158-161). This breaks the
  README's "asks nothing while the speed is unseen".
- The bridge checks speed only with a fresh `/vehicle/odom` (relay:151-153), which `motor_pi_alone` doesn't have.

*Needed:* treat NaN as unseen, then require a person's "on stands" confirmation. Worth fixing now,
whatever happens to this plan. It also feeds the stands check (`panel-app/src/main.rs:513`).

**M6. Turning ego off also turns off the output mux, and the names mislead.** Checked.

- The `ego` part starts ego, the sensor mux and the output mux together (car.launch:463-468).
- The `mux` part is twist_mux (car.launch:439-440). So `ego: false, mux: true` looks right and leaves no gate.
- Nothing stops ego and a stand-in running together. Their commands would interleave, with a healthy
  heartbeat. Reviewer: `provenance.py:38-50` watches sensors only.

*Needed:* split the part, make it an either/or at launch, and add a graph check.

**M7. The panel can't tell which layer is really running.** Reviewer.

Layers are launch and yaml states on the Pi, not panel tabs. Each change means hand edits (Checked:
`docs/actuator-tests.md:207-211`). A tab saying "layer 2" could be wrong. The panel also doesn't read
the gate state (Checked: `aav_hud/README.md`, panel table), so a shut gate shows as flat lines.

*Needed:* the panel works out who publishes and shows it, or says `CAN'T TELL`. Add an always-on strip
for gate, e-stop, heartbeat and why. Warn while `steering_calibration` isn't `none`.

**M8. WiFi data sitting outside ROS loses three things.** Reviewer.

It isn't in `docs/interfaces.yaml`, a bag can't record it, and Gazebo and bench can't produce it, so
the graphs can't be tested at home. That goes against the drop-in rule. Options: D4.

**M9. The panel's code isn't ready for a second source.** Reviewer.

| Gap | Where |
|---|---|
| The sender is private to the ROS source, and the screen holds one source | `panel-app/src/ros.rs:95`, `main.rs:328`, `:531` |
| No ROS means the program exits | `main.rs:334`, `:340`; `source.rs:24` |
| The queue drops silently, and ROS samples have no `seq`, so gaps draw as real data | `ros.rs:62-63`, `:405-409` |
| No plot code, no WebSocket crate | Search of `ros/hud` |

Threads aren't the problem: a third thread with its own queue fits. WiFi values must never reach the
GO gate or the calibration page's rules.

**M10. Results vanish.** Checked, except where marked.

- History lives in the reader for 60 s (brief:175). Only steering has SAVE.
- `tools/record.sh:24-32` leaves out `/control/car/actuator_cmd`, `/control/car/heartbeat`, both raw
  topics, `/vehicle/rc` and `/safety/output_mux/state`. It does include `/control/cmd_vel` and `/ego/actuator_cmd`.
- Car day records on the Orin, but A9b runs nothing there (Reviewer: `docs/car-day.md:625`).
- A saved number has a long way home: file, then `calibration.rs` or `vehicle.yaml`, then reflash or
  rebuild. No table shows it, and the panel can't show measured against flashed (Reviewer).

*Needed:* add the topics, say where to record, add FREEZE (automatic on a stop), and a one-page table of
each number's route.

**M11. Wheel size has a broken trail, and may not change the car's speed.**

| Fact | Mark |
|---|---|
| 0.36 in `vehicle.yaml:28`, 0.30 in `spine-board/README.md` | Checked |
| `vehicle.yaml:28` asks for a rollout test. M3 is a tape measure, and no rollout procedure was found | Reviewer |
| `/vehicle/wheels` comes from the Arduino, so its scale probably lives there | Reviewer. Arduino code unread |
| The car's brake is on when idle, so rolling it needs a plan | Reviewer: main.rs:117 |

This isn't a debug-screen job. *Needed:* name who owns the scale, then write a rollout step: a mark on
the tyre, weight on, several turns, a tape.

**M12. `vehicle.yaml` has duplicate keys.** Checked: `centre_of_mass`, `tyre_grip` and
`encoder_counts_per_rev` sit at `:58-63` and `:69-75` in the same block. Common YAML loaders keep the
last, so a student's measurement in the first block would be ignored. Values match today. Whether a test
catches this: Unverified.

**M13. The word "layer" clashes.** Reviewer: `docs/how-it-fits.md:135-161`, `docs/faq.md:76-89` already
use numbered safety layers. "Layer 2 failed" could read as a safety failure. Short codes collide too:
B9 and M3 each have two meanings. *Proposal:* tabs named **1 PARTS**, **2 HAND**, **3 EGO**.

**M14. No student runbook.** Reviewer.

- No page says, per step, what to launch, who stands where, what passes and which file to keep.
- Existing docs use an e-stop person, a wheel watcher and a laptop person. The plan assigns none.
- A joystick holder can't read small moving numbers: press, watch, FREEZE, then read.
- `ALLOWED` could read as "safe to sweep". Say `SOFTWARE ALLOWS`, with a checklist including who set
  the current limit.
- On stands, throttle stops at a DAC code. The verdict should be `DAC OK, wheels: person says ___`.

**M15. The brief isn't fit to draft from.** Reviewer, spot-checked.

| Problem | Lines |
|---|---|
| Overview still says "without the Pi or ROS in the path" | brief:8-10 |
| "Nothing is decided" beside Ben's decisions | brief:662 |
| Stages never mention layers or graphs | brief:694-702 |
| OTA is a non-goal, and also proposed | brief:657, :94 |
| Two sections called "latest direction" | brief:96, :133 |
| `/update` has three answers | brief:46, :94, :145 |
| Graph scale differs | brief:178, :204 |

*Needed:* one page, "the plan now", on top: decisions, one order, and a retired list. Move the old review under "history".

**M16. Ben's stand-in decision isn't on the word-for-word record.** Checked: messages ends at line 31,
with "going directly to pi -> esp32". Keeping the mux and using a stand-in isn't there, though brief:124 credits it
to him. *Needed:* add his words, as the repo's rules require.

**M17. Other contracts need a home or a change.** Reviewer.

| Item | Change |
|---|---|
| JSON status | One contract file, a version field and golden lines, like `firmware/can/`. One struct with the uplink |
| New "Pi wrote" topic | Name it by role under `/control/car/`: `legacy_uart_bridge` is interim |
| `/ego/actuator_cmd` | Has no `drop_in:` rule (`docs/interfaces.yaml:199-204`). Add the 50 Hz promise |
| "Ackermann appears only after ego" | A stand-in needs a written exception |
| `aav_hud/README.md`: drives "only through twist_mux, ego and the spine" (Checked) | Reword if layer 2 lands |
| Test authority | `SteerCal` and `TestRequest` overlap. Pick one before adding the brake |
| WiFi password | Read-only Rust now holds it at build, so the ELF is no longer safe to publish (`tools/car_day_build.sh`). Needs the untracked-file rule too |
| `bench-link` | Mark it superseded |

**M18. The `uplink` build changes the RC map.** Checked: main.rs:383-389 picks `THREE_POSITION`. RC direct
moves from above 1500 to above 1700 (Reviewer: `ibus/src/rc.rs`). "A person on RC wins" depends on this, so
check it on the bench before any motion at layer 1.

### 🟢 Nits

- `/vehicle/throttle` looks like a small fix, since `throttle_out` is already in the uplink (Checked:
  reader:67-69). It's the value before the ramp, so label it that way. Contract first.
- The uplink reader already counts `lost` and `bad`, but doesn't publish them (Checked: reader:31-32, :49-52).
- `legacy.yaml:16` says version 1, the code defaults to 2 (Reviewer).
- Lichtblick's plot window is 30 s today, one setting (Checked: `tools/foxglove/driving.json:63`, `:74`).
- The numbers' window is unclear: 60 s or "last few seconds" (brief:181). An average over a lock-to-lock run means nothing.
- Time axis: show "seconds ago", and mark `BOARD RESTARTED`.
- Use labels at line ends and line styles, not colour alone. `~/.local/share` is hidden in Finder.
- `motor_pi_alone` has no `foxglove` part (Checked). The load on the Pi is unmeasured.

### Where reviewers disagreed

| Topic | Positions | This report |
|---|---|---|
| Layer 2 | Design, codebase, zoom-out: ego with a loose config. Readiness, structural: build only if a recording points at ego. Comprehension: keep it, with a loud warning | Record A9b first. Ben decides (D2) |
| Graph home | Design, zoom-out, codebase: Lichtblick first. Structural: laptop relay plus stock plots. Comprehension: `hw_panel` is a sensible home, graphs later | Stock first, logic in an engine-free crate |
| Route for ESP32 data | Design, zoom-out: uplink. Structural, readiness: relay WiFi into ROS on a laptop | Uplink for graphs, WiFi as the witness that skips the Pi. Ben asked for WiFi (D4) |
| Is `foxglove_bridge.yaml` allowing `/vehicle/*`? | Codebase: yes. Readiness: search found nothing | **Yes.** Checked: line 24 blocks only listed heavy topics |
| CH6 check (H10) | Codebase: check first. Readiness: a two-position switch reads the same, so it shouldn't block | Check once by hand. Hardware lead |
| Today's C++ log as a first answer | Only zoom-out raised it | Kept, with its limits |

### First review: does the plan answer it now?

| Item | State |
|---|---|
| Silent UART isn't a stopped car | Deferred with WiFi commands, not solved. Returns if they do |
| `/update` has no password | Open, and tied to the cable. A cable settles most of it. The C++'s page is still a hazard today |
| WiFi password (Q34) | Open, and worse: the radio now stays on while driving |
| Throttle refused without wheel speed | Answered: by hand on stands. That route opens B2 |
| Radio timing | Still unmeasured, no fallback (brief:52-54). The uplink route stops graphs depending on it |
| First flash with no radio | Kept, but impossible without a cable (B1) |

## Answers to the six questions

**1. Can a stand-in fit?** Yes, mechanically, but not as "plain". It publishes `AckermannDriveStamped` on
`/ego/actuator_cmd`. The gate needs the sensor mux's OK, no foreign source and 2 s of settling, not ego.
The locks stay if it reads `/control/cmd_vel`. See B2 and M6. **What it proves:** only that a fault goes away
without ego. RC direct skips the Pi. A9b runs the whole path. Comparing `/control/cmd_vel` with
`/ego/actuator_cmd` during A9b shows what ego did, both are already in `tools/record.sh`, and it adds no
new suspect.

**2. Is `hw_panel` the right home?** For buttons and hop verdicts, yes: students know it. For 60 s graphs,
not first. Threads are fine, but the code isn't ready (M9) and nothing names its computer (B4). A stock plot
already draws steering, needs no ROS on the laptop, and a bag saves it. Unconfirmed: now/average/low/high
numbers in Lichtblick, and how it runs on the car. Put parsing, pairing and statistics in an engine-free
crate, so raylib or Bevy stays a thin view.

**3. Can the lines be lined up honestly?** Only as a spot check.

| Comparison | Proved? |
|---|---|
| Frames written vs `frames`, `bad`, `skipped`, over an interval | Yes, every frame. **This is the real proof** |
| Counter advancing, `repeats` vs a baseline | Yes, freshness. Needs a measured baseline |
| Counter plus CRC, sampled | Yes, 10-40% of frames at 5-20 Hz. Encoding is already covered by shared vectors |
| Values paired by counter alone | No (M1) |
| Delay between Pi and ESP32 | No: two clocks. WiFi jitter adds to it |
| `serial.write` reached the wire | No: only that the kernel took the bytes (Reviewer) |

**4. Does the layer order hold?** No (B3). A simpler real first step exists: read the existing logs, then
Pololu's tools, which need no ESP32 at all.

**5. Is there a smaller first version?** Yes. See below.

**6. What's missing for measuring?** A brake method (B5), a wheel-size owner and rollout (M11), saved results
and their route home (M10), a day sheet with roles (M14), and a working "still" check (M5). Throttle has only
a person's eyes on stands, or a tachometer.

## Smallest useful first version

**Goal:** answer "is the Pi passing messages correctly?" with a PASS or FAIL.

| Step | Needs | New code | Gives |
|---|---|---|---|
| A. Today's log | WiFi only: `websocat ws://<esp>:81`, filtered with `grep`. Optional on the Pi: pyserial's `spy://` in `port` (Reviewer) | None | Values the C++ received (Checked: `ros2_handler.cpp:54`, `:67`) |
| B. Rust, no radio | Cable, A7 done | None | `LINK` line: `frames`, `bad`, `skipped`, `repeats`, `counter` (Checked: main.rs:525-537), with `ros2 topic hz /control/car/heartbeat` |
| C. A9b, recorded | The joystick, `motor_pi_alone`, the added bag topics | `tools/record.sh` | The whole path, and what ego did |
| D. One new topic | Contract first, then the uplink wire | Small | Frames written, counter, CRC. Publish `lost` and `bad`. A script prints PASS or FAIL |
| E. One Lichtblick layout | D | A layout file | Graphs at 50 Hz, saved in a bag |

**Limits of step A.** It's the only step that works with just the network, but:

- It says nothing about the Rust.
- Brake frames print no values (Checked: `ros2_handler.cpp:47-49`), and idle frames are brake frames
  (Checked: protocol:127-128). So steering only shows with throttle on.
- The C++ has no timeout, so stands only (Checked: `motor_pi_alone.yaml:11`).
- CORTEX ran the inherited bridge on 6 Nov, so `spy://` needs our bridge there. That port 81 really carries
  these lines on the car: Unverified.

**The real order for the whole plan:**

| # | Step | Was in the plan as |
|---|---|---|
| 0 | Read today's log, step A | Not in the plan |
| 1 | Cable. Pololu's tools: feedback mode, both current limits, steering ends (Way A) | Part of layer 1 |
| 2 | Paper sheets: brake marks, rollout. Fix M5 and M12 | Missing |
| 3 | Pi ready: console, service, our bridge (B6) | One table row |
| 4 | Rust, no radio, version 2, RC direct, car-day checks | Stage 0 |
| 5 | A9b, recorded. Steps B and C | "Layer 2" and most of "layer 3" |
| 6 | Uplink wire, steps D and E | Graphs |
| 7 | Way B on the panel, then the brake if still needed | Layer 1 |
| 8 | Radio, after a timing test: `/status.json`, then `/scan`, the page, the WebSocket | Rust's WiFi jobs |
| Gate | A written fault steps 0 to 8 can't separate? Then stand-in, raylib graphs, WiFi commands | Layer 2, graphs, part 5 |

**Left out for now:** stand-in node, raylib graphs, five lines, signed update page, brake page. Ben's
direction that the Rust does all the C++'s WiFi jobs still stands. They just don't need to come first or
carry the graphs. Once the radio is in, the ESP32's page stays useful as the witness that doesn't depend
on the Pi being tested.

## Decisions for Ben, and for the hardware lead

### For Ben

| # | Decision | Recommendation |
|---|---|---|
| D1 | Make the USB cable step 1, and drop the signed update page? | Yes |
| D2 | Layer 2: see below | Record A9b first, and build only if a fault remains |
| D3 | Graphs: stock plot first, `hw_panel` for verdicts and buttons? This partly reverses `docs/foxglove.md:102` (Reviewer) | Yes. He said "maybe" for `hw_panel` (messages:31) |
| D4 | ESP32 data for graphs: uplink, or WiFi as he asked (messages:21)? | Uplink for graphs, WiFi as the Pi-free witness. If the wire can't be confirmed, WiFi |
| D5 | Which computer and network runs the panel on the day? | A wired laptop, as `docs/hud.md:822` says. Test reaching the ESP32 from it |
| D6 | Replace the five lines with hops, and two lines per graph? | Yes |
| D7 | Put his stand-in decision on the record, in his words | Yes |
| D8 | Tab names instead of "layer"? | PARTS, HAND, EGO |
| D9 | Fix M5 and M12 now, as their own small changes? | Yes |

**D2 options, if something must take ego out:**

| Option | New code | Speed cap | Contract change | Catch |
|---|---|---|---|---|
| Record A9b, plot ego's input and output | Bag topics | Ego's | None | Ego stays in the path |
| Ego with a loose stands config: `max_jerk: 0`, more accel, `max_speed:=0.3` | A config | Ego's | None | Not a true pass-through. Body limits stay. Unconfirmed that it accepts them |
| Plain stand-in, plus a stands teleop config with lower scales | A node, a launch split | Teleop's | Yes | Needs all of B2 and M6. Lowering only the speed scale makes full lock come with less stick, so lower the turn scale too. The fixed `no limits` wording changes |

Only a direct stick-to-angle mapping would give steering at standstill. That's a different node and skips
twist_mux if it reads the joystick, so it needs its own safety case.

### For the hardware lead

| # | Decision |
|---|---|
| H1 | Is CORTEX the Motor Pi? Confirm the GPIO17 uplink wire (H9) |
| H2 | Each Jrk's feedback mode, and the current limit for **both**, including the brake |
| H3 | Brake marks, and whether a hand may touch a wheel to find first drag |
| H4 | The stick's top value on stands, if ego is ever out, and what throttle is acceptable |
| H5 | Check CH6 and RC direct with the `uplink` build, before any motion |
| H6 | Wheel rollout: who owns the scale, and which number is right |
| H7 | Present for the first flash and for the console change |

### Not verified by anyone

- Anything on the real car. All timing, `repeats`, load on the Pi, and whether the gate opens on `motor_pi_alone`.
- `spy://` on the Pi's pyserial. `websocat`'s licence and its install on a Mac.
- Lichtblick's 60 s plot and statistics on the car. Whether ego accepts the loose config.
- The Arduino's wheel code. Whether QEMU can show the brake route. Whether a Rust image loads through `/update`.
