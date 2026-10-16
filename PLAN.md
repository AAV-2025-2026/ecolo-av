# The plan: what's left to build

Written 15 October 2026, with Ben ("So what is actually left to build? Let's make a
plan"). What's already done is in [PROPOSAL.md](PROPOSAL.md); this page is only what's
left, and in what order.

> **The short version**
> - **Software we can build now**, no car needed: S1-S9. S1, S2 and S3 done in Gazebo 15 Oct.
> - **Needs the car, or the hardware lead's decision**: C1-C10. Hardware choices are the hardware lead's, not Ben's.
> - **The goal:** C9, the car drives itself from GPS point A to B and stops at B.

## The path to the goal

```text
 now (software)          Friday           hardware lead        on the car
 S1 A→B in Gazebo ──┐    C1 audit    ──►  C3 timeout     ──►  C8 stands → lot ──► C9 A→B 🎯
 S2 spine in loop ──┼──► C2 measure  ──►  C4 sensors
 S3 steering fix  ──┘                     C5 Jetson, Jazzy, C6 drivers, C7 install
```

## Software we can build now (no car)

| # | Build | Why | Size | Status |
|---|---|---|---|---|
| S1 | **GPS A → B with a smooth stop**: speed by the distance left to B, slowing at half the measured braking g | the main goal (READ-ME-TESTS 5.2), proven in Gazebo first | 1 day | ✅ in Gazebo 15 Oct: `aav_goto`, `pixi run goto`; every stop within 0.4 m of B, at 1 and 3 m/s (`sim-check --goto`). On the car: C9 |
| S2 | **The spine in the loop** in Gazebo: ego → CAN → the spine's safety logic → the actuator model → Gazebo | timeouts and e-stops tested the way the car runs them | 1-2 days | ✅ 15 Oct: `pixi run sim spine:=true`, `pixi run sim-check --spine` passes |
| S3 | **Gazebo steering fix**: full lock turns 0.43 rad, not 0.5 | the sim should steer like the car | small | ✅ done 15 Oct: 0.484 rad at full lock (Gazebo's `steering_limit` from `vehicle.py`; the last 3% is tyre slip) |
| S4 | **Ghost obstacles**: a pretend person in Nav2's map while the real car drives | test stopping on the car with nothing real to hit | 1 day | |
| S5 | **Touchscreen keyboard** for the map's search | type a destination in the car | small | |
| S6 | **Newer models**, on the same pictures and tasks: YOLO26 / RF-DETR vs YOLO11; Qwen3.5 / Gemma 4 / Granite vs Qwen3 | better or freer models | medium | |
| S7 | **Python → Rust**: ego and the spine bridge (TEAM-TODO D7) | needs Ben's go-ahead | large | |
| S8 | **OSRM street routes** | only for driving on real streets | medium | stretch |
| S9 | **CARLA (the Unreal Engine 5 version)** next to Gazebo: photo-real cameras, traffic, towns | Ben asked 15 Oct (reopens Q31). No Mac version: needs Linux or Windows with an NVIDIA RTX card (16 GB of video memory or more). [CARLA](docs/carla.md): Town10 on 0.10 (UE5); Carleton's streets from OpenStreetMap on 0.9.16 (UE5 can't import maps yet) | medium | **research done, adapter built and tested without a server (15 Oct); never run: needs the NVIDIA machine** |

## Needs the car, or the hardware lead

| # | Work | Who decides | Blocks |
|---|---|---|---|
| C1 | **The audit** (16 Oct): every computer, `best.pt`, camera code, the screens ([FRIDAY-TODO.md](FRIDAY-TODO.md)) | team | everything below |
| C2 | **Measure and weigh** the car → `vehicle.yaml` ([READ-ME-MEASURE-THE-CAR.md](READ-ME-MEASURE-THE-CAR.md)) | team | an accurate sim |
| C3 | ⚠️ **The safety timeout**: flash the Rust ESP32 or patch today's board (TEAM-TODO B2) | **hardware lead** | any drive on the ground |
| C4 | **Closed-loop sensors**: steering angle from the Jrk, wheel speed (CAN boards or not), brake position | **hardware lead** | closed-loop control |
| C5 | **Back up and upgrade the Jetson**, then Jazzy on every car computer | team | our software on the car |
| C6 | **Drivers for the real parts**: the lidar (probably a Velodyne), the cameras from the Pis, the GPS | after C1 | full perception |
| C7 | **Install**: the car kit, the two screens at boot ([docs/car-screens.md](docs/car-screens.md)) | after C5 | |
| C8 | **Tests on stands, then in the lot**: `pixi run actuator-test` ([docs/actuator-tests.md](docs/actuator-tests.md)) | after C3 | real numbers |
| C9 | **GPS A → B on the car** | after C3-C8 | 🎯 the goal |
| C10 | A Gazebo copy of the real test lot | the lot chosen | |

The tests for each step, in order: [READ-ME-TESTS.md](READ-ME-TESTS.md). The team's work
list: [TEAM-TODO.md](TEAM-TODO.md).
