# The KEFC CAN plan and our CAN contract (14 October)

Ben's KEFC request (October 2026, tab "Bens Mods") puts steering, braking and throttle on
a CAN bus. Our code already has a CAN contract, `firmware/can/aav.dbc` (v0.1.0). This page
compares the two, and says what changes.

**Status: Implemented, and merged on 15 Oct at Ben's request** ("These are important").
DBC v0.2.0, `spine_bridge` and the bench use it; the wheel node boards are still to write.

## The plan in one picture

```text
Orin #1 ── CAN Pal (40-pin header) ──┬──────────────┬──────────────┐
  EKF, ego, spine_bridge             │              │              │
                              AAV control board  Wheel node L   Wheel node R
                              ESP32 MicroMod     ESP32-CAN-X2   ESP32-CAN-X2
                              2 Jrk G2, DAC      Hall sensor    Hall sensor
```

120 Ω at each end: on the CAN Pal, and on the last X2 board.

## What already matches

| Idea | KEFC PDF | Our DBC and code |
|---|---|---|
| ROS stops at the CAN bus | yes | yes: `spine_bridge` over `ros2_socketcan` |
| One command frame at 50 Hz | 0x100 | 0x100 `DRIVE_CMD`, 50 Hz |
| Status frame from the board | 0x180 | 0x180 `VEHICLE_FEEDBACK`, 0x181 `VEHICLE_STATUS` |
| A counter and a checksum, so a frozen Orin is caught | yes | yes: every frame, CRC-8 |
| Brake on silence | 100 ms | 100 ms (v0.2.0; it was 200 ms) |
| The speed loop on the board, not the Orin | yes | yes: `spine-core` |

## What is different

| # | Difference | KEFC PDF | Our DBC | Proposed |
|---|---|---|---|---|
| 1 | Which board is "the spine" | the existing ESP32 control board | a new Pico 2 | **the ESP32 control board.** It is already on the car, with its CAN plug |
| 2 | What 0x100 carries | steering, brake and throttle targets | target speed and steering angle | **ours.** The PDF's own loop table has the board running the speed loop, so it needs a speed, not a throttle |
| 3 | 0x010 | a heartbeat | the software e-stop | **ours.** Every frame's counter is already the heartbeat |
| 4 | Wheel speed | 0x200 left, 0x201 right, 100 Hz | one `wheel_ticks` in 0x180 | **add 0x200 and 0x201** from the PDF |
| 5 | Timeout | 100 ms | 200 ms | **100 ms**, from the PDF |
| 6 | Steering position | from the KTC-100 pot, via the Jrk | `measured_steering_angle` in 0x180 | the same: the board reads it from the Jrk |

## What changes in the code

| Where | Change |
|---|---|
| `aav.dbc` | v0.2.0: add `WHEEL_SPEED_L` 0x200 and `WHEEL_SPEED_R` 0x201, node `WHEEL_L`, `WHEEL_R`; the timeout to 100 ms; the spine node is the ESP32 board |
| `can_codec.py`, `protocol.rs`, test vectors | the two new frames, as `CLAUDE.md` says |
| `spine_bridge` | the two wheel speeds into `/vehicle/odom`, and `/vehicle/wheels` (the front two; the same topic Gazebo fills) |
| `spine-core` | stays: it has no chip in it. A new board crate for the ESP32 (`esp-hal`, Embassy, the TWAI CAN driver) beside the Pico 2 one |
| Wheel nodes | a small Rust program for the ESP32-CAN-X2 (an ESP32-S3): count pulses, send a frame |
| Gazebo, bench | the bench's spine simulator sends the two wheel frames too |

!!! note "Rust on an ESP32"
    The ESP32 and ESP32-S3 use Xtensa cores. Rust needs Espressif's toolchain
    (`espup`), not the stock one in Pixi. It is well supported: `esp-hal` has Embassy and a
    CAN (TWAI) driver.

## Still to confirm (from the PDF)

- The control board's CAN transceiver (U7) is fitted and works. The photos show the
  CANH/CANL plug ([The car in photos](car-photos.md)).
- The steering and brake actuators' wire counts: 5-6 wires means built-in feedback.
- The front brake rotors are steel, and have enough holes for the speed resolution.
- What the brake does when it loses power.
