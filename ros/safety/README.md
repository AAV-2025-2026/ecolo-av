# ros/safety

## Overview

Software safety layers on top of the red button. They can only **stop** the computer's
drivers; they never move the car, and they never hold back a person on the joystick.

## Subdirectories & Boundaries

| Package | What it does | Main output |
|---|---|---|
| [aav_safety](./aav_safety/README.md) | the sensor watchdog: stale, NaN, frozen, jumped or disagreeing inputs lock twist_mux | `/safety/sensor_watchdog/lock` |
| [aav_ghost](./aav_ghost/README.md) | ghost obstacles: a pretend person only Nav2 sees, to test stopping | `/safety/ghost/scan` |

## Invariants

- The watchdog lock (priority 30) holds Nav2, the point driver and the AI slot only, never people or tests.
- Fail-safe: 1 s without a lock message counts as locked.
- JUMP, DISAGREE and LOST latch until a person clears them (`/safety/sensor_watchdog/clear`).
- A ghost only ever adds an obstacle.

## Side Effects

- Publishes locks, state, `/diagnostics` and the ghost scan; logs state changes.

## Verification

- Run: `pixi run test` (or `colcon test --packages-select aav_safety aav_ghost`).
