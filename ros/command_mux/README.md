# ros/command_mux

## Overview

Picks **one** command for ego from all the drivers: the stock twist_mux, set up for the car.

```
/drivers/*/cmd_vel ──▶ twist_mux (+ locks) ──▶ /control/cmd_vel ──▶ ego
```

## Subdirectories & Boundaries

| Package | What it is |
|---|---|
| [aav_mux](./aav_mux/README.md) | twist_mux config: nine inputs (joy 100 … ai 10), locks `estop` (255), `stop_sign` and `sensors` (30) |

## Invariants

- The highest fresh input wins (0.5 s timeout).
- Locks never hold a person or a test; only the e-stop holds everyone.
- The sensors lock locks after 1 s of silence (fail-safe).

## Side Effects

- Publishes `/control/cmd_vel` and lock diagnostics.

## Verification

- Run: `pixi run test` (`tools/tests/test_topic_areas.py` and `aav_bringup`'s launch tests check the config).
