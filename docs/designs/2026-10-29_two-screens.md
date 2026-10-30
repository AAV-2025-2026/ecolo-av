# Two screens: one to test the hardware, one to show what the car sees

* **Author:** Ben (the ask), written up 29 Oct 2026
* **Status:** Proposed, revised after the EGM review (design, code details), 29 Oct

Ben, 29 Oct evening (word for word in `docs/history/messages-2026-10-29.md`): "we need one
screen just to test all the sensors and operate all the actuators and another screen to
show off the voxels", "increment the speed, break and steering. and maybe a center
button. We need very simple buttons."

## The idea in one line

Split today's debug HUD in two: a **hardware screen** with big buttons and every sensor's
number, and a **seeing screen** with the 3D cubes and two top-down maps.

## Screen 1: the hardware screen

```
 ┌─────────────────────────────────────────────────────┐
 │ STANDS · SIM          E-STOP (big, red)             │
 │                                                     │
 │  [ Speed + ]     [ Brake + ]     [ ◀ ]  [ ▶ ]       │
 │  [ Speed − ]     [ Brake − ]     [  CENTRE  ]       │
 │  asked 0.3 m/s   asked 20 %      asked +0.10 rad    │
 │  seen  0.0 m/s   seen  18 %      seen  +0.09 rad    │
 │                                                     │
 │  IMU   ax ay az, gyro (bars; shake the car)  OK     │
 │  Wheels  L R m/s                              OK    │
 │  GPS  fix, satellites, accuracy               NONE  │
 │  Lidar Hz · Radar Hz · Camera Hz · Battery V        │
 └─────────────────────────────────────────────────────┘
```

| Rule | Why |
|---|---|
| **Its own program, `hw_panel`**, sharing the readers with `debug_hud` | `debug_hud` stays read-only (D3, `docs/hud.md`); only `hw_panel` ever publishes |
| **Speed: hold to drive.** Speed +/− set the step (0.1 m/s, cap below); the car moves only while Space or the GO button is held | a lost key-up, a lost focus or a frozen window gives 0 |
| **Steering ◀ ▶**: 0.05 rad a press, turned into a yaw rate (ω = v·tan δ / L) | a `TwistStamped` carries a yaw rate; ego holds the wheels below 0.05 m/s, so steering moves only while creeping (as the preflight does) |
| **Brake**: read-only in step 1; "STOP" sets speed 0 at once | ego always slows at its fixed 2.0 m/s²; a brake percentage needs option B |
| **CENTRE**: steering 0 at a creep, then speed 0 | at standstill the wheels wouldn't move |
| Publishes only while the drawn-frame count rises (`hud-core`'s `Heartbeat`) | a frozen window stops publishing; twist_mux (0.5 s) and ego (0.3 s) then stop the car |
| Zeroes everything and needs fresh presses after: an e-stop, someone else driving (`/control/cmd_vel` not ours for 0.3 s), a source change | the joystick's release must not hand back an old speed |
| E-STOP: `hud-core`'s burst (true 5 times, never false) | no button clears an e-stop |
| Each sensor: its number and OK / STALE / NEVER; on stands the wheel speed says **"front, not driven"** and the throttle is shown as "seen" | TODO 49b |

### How a press reaches the car

| Option | Path | Verdict |
|---|---|---|
| A | buttons → `/drivers/buttons/cmd_vel` (contract first) → twist_mux **slot 45** → ego → spine | **step 1**. 45 is free and below the geofence's lock (51) and the no-timeout lock (60), so both hold it; above the sensor locks (30), so it works on stands; people (90-100) always win |
| B | buttons → the spine's hardware test mode (Arsh's #15) | **step 2**, for brake and steering only: on today's board (`SpeedFeedback::None`) the spine turns throttle requests into Hold; it needs Exit, Enter with the car still, a request every 100 ms; no transport yet (TODO 0b) |
| C | buttons → the actuator straight | **no**: around the spine's caps and e-stop (D3) |

### Where it may drive

| Source (`/system/source`, `safety.py`'s rules, ported with the same test vectors) | Speed buttons |
|---|---|
| SIM, BENCH | on, cap 1.0 m/s |
| REAL, `--stands` given | copies the preflight's refusal (`preflight_refusal`): off until a driven-wheel speed exists (TODO 49b), the Rust ESP32, and `speed_loop.mode open`; then cap 0.3 m/s, `safety.unseen`'s 4 s rule |
| REAL on the ground, or nothing announced | **off** in step 1 |

Run from the Orin's own screen or a wired laptop; not a Mac over WiFi in step 1 (debug HUD D4).

## Screen 2: the seeing screen

```
 ┌──────────────────────────┬───────────────┐
 │                          │ lidar map,    │
 │   3D cubes (big)         │ top-down,     │
 │   the car, the path      │ the car on it │
 │                          ├───────────────┤
 │                          │ NDT's match:  │
 │                          │ the scan on   │
 │                          │ the map cells │
 └──────────────────────────┴───────────────┘
```

| Part | Today | Later |
|---|---|---|
| Left, 3D | the debug HUD's cubes, fading, every localizer's car | the cubes flattened to a cost map; cubes grouped into objects |
| Right top | the NDT map's points from above, every localizer's car | the car's own map from KISS-ICP |
| Right bottom | NDT's 1 m cells as ellipses, the latest scan over them, its score | the same, live on the car |

The seeing screen is today's `debug_hud` with a new layout (key L swaps it back): it
still publishes nothing. The hardware screen is `hw_panel`.

## Checks

| Test | Pass |
|---|---|
| `panel-core`: a press makes one step; hold-to-drive; CENTRE; the caps; zero after an e-stop, a takeover, a source change | `cargo test` |
| The source rules match `safety.py`'s test vectors | `cargo test` |
| A frozen window (SIGSTOP): publishing stops within 0.5 s | Gazebo |
| The geofence locked: the buttons are held | Gazebo |
| After an e-stop and the joystick let go, the car stays at 0 | the bench check |
| twist_mux: a person's joystick beats the buttons | the bench check |
| Gazebo: press Speed + three times, the car reaches 0.3 m/s; CENTRE stops it | `debugdemo` |

## Order

1. The seeing screen's layout (no new topics).
2. The hardware screen, read-only (the numbers).
3. `interfaces.yaml` and twist_mux's slot 45 first; then the buttons (option A) in Gazebo, then the bench.
4. Option B once the spine's test requests have a transport.

## Questions for Ben (picked the recommended answer)

| # | Question | Picked |
|---|---|---|
| T1 | One program with two modes, or two programs? | two: `debug_hud` stays read-only (review) |
| T2 | Buttons through twist_mux first, or wait for the spine's test mode? | twist_mux first (A); B for brake and steering later |
| T3 | Its slot in twist_mux | 45: the geofence and no-timeout locks hold it (review: 60 would skip them) |
| T4 | Mouse only, or keys too? | both: arrows, +/−, Space held = GO, C = CENTRE |
| T5 | Drive the real car on the ground in step 1? | no: SIM, BENCH, and stands once 49b is answered |
