# Start here

The software for Carleton's autonomous car: a ROS 2 Jazzy workspace, plus the firmware
for the microcontroller that drives the actuators. These pages explain how it fits
together, and how to run it.

## The whole stack in one picture

![How the stack fits together](img/architecture.svg)

Read it top to bottom: **sensors become telemetry, drivers become one command, and ego
moves the car.**

| Step | What happens |
|---|---|
| 1. Sense | Sensors publish raw data. Two filters (EKFs) work out where the car is. |
| 2. Propose | Each driver proposes a speed and a turn rate: joystick, keyboard, script or Nav2. |
| 3. Pick | `twist_mux` passes on the highest-priority driver. `/estop` blocks them all. |
| 4. Convert | **ego**, the virtual car, turns that into a speed and steering angle the car can do. |
| 5. Move | One backend moves something: the real car, Gazebo, or a turtle on the screen. |

## Read these, in order

[[pages]]

## Try it in five minutes

On a Mac or on Linux, once [pixi is installed](run.md):

```bash
pixi run build       # compile our packages
pixi run turtle      # terminal 1: a turtle that steers like the car
pixi run keyboard    # terminal 2: hold i to drive, u or o to turn
```

## Where things live

| Folder | What's in it |
|---|---|
| `src/` | ROS 2 packages, one folder per layer of the picture |
| `firmware/` | microcontroller code: the CAN contract, the Rust spine, today's ESP32 |
| `tools/` | scripts: tests, keyboard, graph check, recording, these docs |
| `docs/` | these pages. Edit a `.md` file, then run `pixi run docs`. |

## Where decisions live

| What | Where |
|---|---|
| The architecture, its decisions, and open questions Q1–Q34 | the team design doc (a Claude Doc) |
| Every topic: its type, and who publishes and reads it | `docs/interfaces.yaml`, shown as [Topics](interfaces.md) |
| The CAN frames between the computer and the spine | `firmware/can/aav.dbc`, explained in [Firmware](firmware.md) |
| The car's measurements | `src/aav_description/config/vehicle.yaml`: [Car numbers](car_measurements.md) |
| Rules for code, names, secrets and git | `CLAUDE.md` |
