# The bench link: the ESP32's status and test commands over WiFi

* **Author:** Ben (the direction), written up 6 Nov 2026
* **Date:** 2026-11-06
* **Status:** replaced on 7 Nov by
  [the hardware debug plan](2026-11-07_esp32-debug-link_brief.md). Kept as history. Nothing was
  built. TODO 126.

Ben, 6 Nov: "we need to braodcast like jsonl and a heartbeat and then maybe any time it gets an
update" and "for our hardware testing screen maybe we need direct control to the esp32 ... two
way communications with the spine over wifi. This will not be normal but atleast for testing".
USB or WiFi first? "I am ok with wifi and will only work with my laptop". Then: "we need to be able
to send commands and read comments directly from the esp32 over wifi (from the hareware screen
only) and then for the real one we wil hav eeveryhting go through the pi".

## The idea in one line

The ESP32 tells everyone on WiFi what it is doing. In a test build only, Ben's laptop can also
send it one small command at a time, and see the real result.

```text
 Ben's laptop                                   ESP32
 ┌───────────────┐   signed, repeating commands  ┌──────────────────┐
 │ hardware      │ ────────── UDP ─────────────► │ bench-link build │──► one actuator
 │ panel         │ ◄──────── JSONL ───────────── │ only             │
 └───────────────┘   status, heartbeat, events   └──────────────────┘
 Anyone on the WiFi can read the status. Only the key can command.
```

## Why: what 6 Nov showed

| What we couldn't tell on the car | Why not | What fixes it |
|---|---|---|
| Is the RC switch on RC or computer? | The log has no raw channels | Raw RC channels |
| Do the actuators answer now? | `STR:OK BRK:OK` is set only at boot | Live Jrk health |
| Do they have power? | Nothing reports it | Jrk errors and supply voltage |
| Did the wheel really move? | The log shows the wish only | Jrk position |
| Has anything changed? | About 130 near-identical lines a second | Events, and a slower status |

Without WiFi we'd have seen none of it. **Our Rust firmware has no WiFi today**, so flashing it
as it stands would lose the view that the C++ gives us.

## Two builds (Ben, 6 Nov)

| Build | Commands come from | Status goes to | WiFi? |
|---|---|---|---|
| **Test build** | The hardware screen, directly | The hardware screen | Yes |
| **Real car** | The Pi, over the UART | The Pi, over the UART uplink, then ROS | **No** |

The test build is two Cargo features: `wifi-status` (reads only: JSONL status, heartbeat, events)
and `bench-link` (adds commands, and needs `wifi-status`). The real car's build has neither.

## Part 1: the status (JSONL)

One JSON object per line. Every line has `seq`, so a gap shows lost data.

```json
{"t":"hb","seq":812,"up_ms":40210,"mode":"rc_fwd"}
{"t":"status","seq":813,"steer":-0.01,"dac":245,"dac_ack":true,"brake":0.0}
{"t":"event","seq":814,"what":"mode","from":"rc_brake","to":"rc_fwd"}
```

| Type | When | Holds |
|---|---|---|
| `hb` | Once a second | Alive, uptime, mode |
| `status` | 5 times a second | Targets, DAC value and acknowledge, raw RC channels, each Jrk's position, errors and supply voltage |
| `event` | At any change | Mode changes, faults, a Jrk or the DAC dropping out or coming back |

- **Over a WebSocket.** A browser can read it, as with the C++ page.
- **A slow reader loses lines.** It never slows the board; `seq` shows the gap.
- **The heartbeat is for watching only.** No safety decision uses it. The stops and the command
  timeout stay separate.
- **The binary UART uplink stays** as the channel for ROS. JSONL is for people and tools.

## Part 2: the test commands

| Command | Does | Limit |
|---|---|---|
| Steering jog | Moves a little, then holds | The rules `SteerCal` has already |
| Brake position | Moves to a position | The Jrk's limits |
| Throttle step | Sets one DAC value | A low cap, 🔒 the hardware lead's number |
| Stop | Throttle 0, brake on | Always allowed, and needs no key |

### The rules

| Rule | Why |
|---|---|
| Separate build, off by default | The car's build can't be talked into driving |
| A physical enable, read at boot 🔒 | Being on the WiFi isn't enough to move the car |
| A session opened with Ben's private key, each command then signed, with a counter | Only Ben's laptop can command, and an old message can't be replayed |
| A command older than 100 ms means stop and latch | The firmware's existing rule; a WiFi drop means stop |
| The stops and RC always win | The Kar-Tech, the red button and the safety locks are never bypassed |
| One drive path | The build ignores UART frames while the bench link is enabled |
| Wheels off the ground | The panel says so, and a person confirms it before each session |

### Only Ben's laptop: a key pair (Ben, 6 Nov)

Anyone on the car's network can reach the board, and an IP or MAC filter is easy to fake. So:

| Key | Lives | If someone copies the firmware |
|---|---|---|
| **Public** | Built into the `bench-link` firmware. Safe in a public repo | They still can't command |
| **Private** | Only in Ben's Mac's Keychain. Never in git | |

Checking a signature may be too slow for 20 commands a second next to a 10 ms tick (not measured).
So the slow check happens once, in a low-priority task:

```text
 Laptop                                ESP32
   │ ◄──────── a fresh random number ───── │  so an old session can't be replayed
   │ ── its answer, signed with the ─────► │  checks it with the public key
   │    private key, plus a key exchange   │
   │ ◄═══ a session key, for this run ═══► │
   │ ── commands, each with a fast tag ──► │  ends at a timeout or a power-off
```

Use a known protocol and audited crates: look at Noise first, with Ed25519 and X25519. We don't
invent our own. To change laptops or replace a lost key, build and flash a new public key.

### On the wire

Commands go as one JSON line with its tag per UDP packet, 20 a second while a button is held. UDP
doesn't resend, and a late command is worthless anyway: the next one replaces it.

## The hardware panel: all six (Ben, 6 Nov)

Three actuators and three sensors, on one screen. The wheel sensor isn't on the ESP32, so the
panel has two sources.

| Part | Kind | Reaches the panel by | Command it? |
|---|---|---|---|
| Steering | Actuator | ESP32, WiFi | ✅ jog |
| Brake | Actuator | ESP32, WiFi | ✅ position |
| Drive (throttle DAC) | Actuator | ESP32, WiFi | ✅ capped step |
| Steering position | Sensor | ESP32, WiFi (the Jrk's scaled feedback) | Reads only |
| Brake position | Sensor | ESP32, WiFi (the Jrk's scaled feedback) | Reads only |
| Wheel speed | Sensor | CAN → Orin → the panel | Reads only |

```text
 Steering, brake, drive ──► ESP32 ──── WiFi: JSONL, commands ───┐
 Steering, brake position ─┘                                    ├──► hardware panel
 Wheel sensor ──CAN──► Orin ──► JSONL relay, reads only ────────┘
```

- **The wheel sensor comes through a small relay on the Orin.** `spine_bridge role:=sensors`
  already turns the CAN frames (0x200, 0x201) into `/vehicle/wheels`. The relay reads that topic
  and sends the same JSONL. The panel's bench mode then needs no ROS at all, so `hw_panel` stays
  locked to one computer for ROS (`tools/ros.sh --local`).
- **Each source shows its own age.** A dead Orin must show "wheel: no data", not a stale speed.
- **The wheel sensors are on the front wheels, and the motor drives the rear.** On stands, a
  throttle step won't turn them. They prove the drive only on the ground. On stands, test them by
  turning a front wheel by hand, and watch the rear wheels or the motor for the drive.
- **It is a separate mode,** chosen by name at start. It shows each command beside its result:
  "asked 0.5, Jrk has no power".

It isn't a driver: no ROS topic changes, and `docs/interfaces.yaml` stays as it is.

**Check on the car:** `docs/actuator-tests.md` step A3. A position reads only if each Jrk's
feedback mode is Analog. If it isn't, that sensor is wired somewhere else.

## Risks to measure first

| Risk | Test | Pass |
|---|---|---|
| WiFi delays the 10 ms tick or trips the 100 ms watchdog | `wifi-status` on the bench, the tick's worst gap, with a client connected and the router going away | No missed watchdog, worst gap written down |
| WiFi drops trip the 100 ms stop too often | Hold a command for 10 minutes beside the car; count the stops | Few enough to test with. Stopping is the safe way to fail |
| Not enough memory for WiFi on the classic ESP32 | Build it and read the sizes | It fits |
| The key check stalls the control loop | Time the session's start on the board, with the tick running | No missed tick or watchdog |

Untested: all of it. The WiFi crates for this `esp-hal` version aren't in the firmware yet.

## How to build it, in order

1. `wifi-status` on the bench: the timing test. Stop here if it fails.
2. The JSONL lines in a logic crate, tested on a laptop.
3. Live Jrk health, in `spine-board`, using the `jrk-g2` driver.
4. `bench-link`: command parsing and signing in a logic crate, with tests for a bad key, a replay
   and a timeout.
5. The panel's bench mode.
6. On stands, with the hardware lead and the Kar-Tech stop in hand: each command, one at a time.

## Questions

| # | Question | For | Proposed |
|---|---|---|---|
| 1 | Which pin or switch is the physical enable? | 🔒 Hardware lead | A jumper on a spare pin |
| 2 | How low is the throttle step's cap? | 🔒 Hardware lead | Well below today's 700 of 1023 |
| 3 | Do we ever want read-only `wifi-status` on the real car, as a second view when the Pi is down? | Ben | No for now: everything goes through the Pi (Ben, 6 Nov) |
| 5 | Where do the steering and brake sensors connect? We guess they are inside the actuators (Ben, 6 Nov) | 🔒 The hardware people | Check the wire count, then step A3 |
| 4 | Should RC or the bench link win on stands? | Ben and the hardware lead | RC, always |
