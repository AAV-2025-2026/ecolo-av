# aav_battery_victron

Reads the battery monitor's Victron VE.Direct serial text and publishes it as a
`sensor_msgs/BatteryState`, plus a heartbeat. Inherited from the 2024-25 team's
`Carleton-AAV-Capstone/Battery-Monitor-ROS`, ported to Jazzy: see
[PROVENANCE.md](./PROVENANCE.md). Called `battery_monitor` until 26 Oct 2026.

`aav_sensors`' `sensors.launch.py battery:=true` starts it. In bench mode,
`aav_bench`'s `mock_battery` stands in.

## Overview

```
Victron monitor ─VE.Direct serial─> VEDirect (parser) ─> BatteryMonitor ─> /vehicle/battery
                                                                        └─> /vehicle/battery/heartbeat
```

VE.Direct sends text lines, `KEY \t VALUE \r \n`, in blocks that end with a
`Checksum` line. A block whose bytes don't sum to 0 (mod 256) is dropped.

## Interface

### Executable: `battery_monitor`

It runs two nodes in one process.

| Node | Publishes | Type |
|---|---|---|
| `battery_state_publisher` | `/vehicle/battery` | `sensor_msgs/BatteryState`, frame `base_link` |
| `heartbeat_publisher` | `/vehicle/battery/heartbeat` | `std_msgs/String`: "Current Time: ..." |

Both publish once per good block that holds `V`, `I`, `SOC` and `VS`.

| Parameter (on `battery_state_publisher`) | Default | Means |
|---|---|---|
| `port` | `/dev/aav/battery` | the udev name (`tools/udev/99-aav.rules`) |
| `baud` | 19200 | VE.Direct's speed |

### What goes in `BatteryState`

| Field | From | Unit |
|---|---|---|
| `voltage` | `V` / 1000 | V (VE.Direct sends mV) |
| `current` | `I` / 1000 | A (VE.Direct sends mA) |
| `percentage` | `SOC` / 1000 | 0 to 1 (VE.Direct sends tenths of a percent) |
| `cell_voltage` | [`V`, `VS`] / 1000 | [pack, 12 V regulator], V |
| the rest | NaN, or UNKNOWN | |

### Modules

| Module | Holds | ROS? |
|---|---|---|
| `VEDirect.py` | `VEDirect`: the byte-by-byte parser, `process_byte`, `check_checksum`, `set_block` | no |
| `battery_monitor.py` | `BatteryMonitor` (block to message) and `main` | yes |
| `BatteryStatePublisher.py` | `BatteryStatePublisher`, a node with one publisher | yes |
| `HeartbeatPublisher.py` | `TimePublisher`, the heartbeat node | yes |

## Invariants

- Only blocks with a good checksum update the data.
- Nothing is published until a block holds `V`, `I`, `SOC` and `VS`.
- SI units out: volts, amps, a 0 to 1 share.
- Inherited code: every change goes in `PROVENANCE.md`.

## Side Effects

- Opens the serial port and reads it in a loop until Ctrl-C, then closes it.
- Prints to stdout ("Sending Data", bad checksums).
- Publishes the two topics above.

## Verification

```sh
pixi run build && colcon test --packages-select aav_battery_victron && colcon test-result --verbose
```

The tests are the stock lint checks (copyright, flake8, pep257); there are no unit
tests. `pixi run test` runs everything. Untested on the car.

## Known gaps

- The nodes never spin, so `ros2 param set` and services don't answer.
- The module has no docstring listing its topics (`CLAUDE.md` asks for one).
- `serial_number` is fixed at `BW12500`.
- The logic (`createBatteryState`) sits in the ROS module, not in a ROS-free one.
