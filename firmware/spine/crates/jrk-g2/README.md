# jrk-g2

## Overview

The Pololu Jrk G2 motor controller, over I2C. A Jrk drives one motor to a target
(0 to 4095), using its own feedback sensor. Plain `no_std` Rust, written against
`embedded-hal` 1.0, so it runs on any board.

Today's car has two:

| Jrk | Address | Targets on today's car |
|---|---|---|
| Steering | 0x05 | 400 to 3500, centre 1950 (unconfirmed: Q2) |
| Brake | 0x04 | 400 released, 3500 full (unconfirmed: Q3) |

## Interface

| Call | Sends | Does |
|---|---|---|
| `JrkG2::new(i2c, address)` | nothing | one Jrk at that address |
| `set_target(t)` | `0xC0 + (t & 0x1F)`, `t >> 5` | moves to `t`; above 4095 sends 4095 |
| `stop_motor()` | `0xFF` | stops; the Jrk then waits for a new target |
| `target()` | `0xA3`, reads 2 bytes | the target it is working to |
| `feedback()` | `0xA5`, reads 2 bytes | the raw sensor reading |
| `scaled_feedback()` | `0xA7`, reads 2 bytes | the sensor reading, in target units |
| `feedback_mode()` | `0xEA 0x18`, reads 1 byte | the "Feedback mode" setting: `None`, `Analog` (a position), `Frequency`, or `Other(u8)` for a byte it doesn't know |
| `error_flags()` | `0xE5 0x12`, reads 2 bytes | what is stopping the motor; clears nothing |
| `take_error_flags()` | `0xB3`, reads 2 bytes | the same, and clears latched errors |
| `take_errors_occurred()` | `0xB5`, reads 2 bytes | every error since the last call; clears them |
| `ping()` | `0xA3`, reads 2 bytes | checks that the Jrk answers |
| `ErrorFlags::is_fault()` | | true for any bit except "awaiting command" |
| `ErrorFlags::contains(bits)` | | true if every bit in `bits` is set |
| `FeedbackMode::is_position()` | | true only for `Analog`: then the scaled feedback is where the motor is |
| `FeedbackMode::from_byte(b)` | | the mode for the setting's byte: 0, 1, 2, else `Other` |
| `address()` | | the address it was made with |
| `release()` | | gives the bus back |

Also: `MAX_TARGET` (4095), `DEFAULT_ADDRESS` (0x0B, a new Jrk's), and the raw
bytes in the public `command` module.

The error bits, for `ErrorFlags::contains(bits)`, are constants on `ErrorFlags` (bit 0
to 13): `AWAITING_COMMAND`, `NO_POWER`, `MOTOR_DRIVER`, `INPUT_INVALID`,
`INPUT_DISCONNECT`, `FEEDBACK_DISCONNECT`, `SOFT_OVERCURRENT`, `SERIAL_SIGNAL`,
`SERIAL_OVERRUN`, `SERIAL_RX_BUFFER_FULL`, `SERIAL_CRC`, `SERIAL_PROTOCOL`,
`SERIAL_TIMEOUT`, `HARD_OVERCURRENT`.

The bytes come from Pololu's *Jrk G2 Motor Controller User's Guide*,
[pololu.com/docs/0J73](https://www.pololu.com/docs/0J73):

| Section | Has |
|---|---|
| 13, I²C command encoding | the bytes of each command |
| 11, Command reference | what each command does |
| 10, Variable reference | where each variable sits |
| 7.7, Error handling | the error bits |

## Before it works

- Set the Jrk's input mode to "Serial / I²C / USB", or it ignores targets.
- The Jrk stretches the I2C clock, so the board's I2C must allow that.
- Above 100 kHz, leave the bus quiet for 100 µs after each read. The 2025-26
  firmware ran at 100 kHz.

## Invariants

- Never sends a target above 4095.
- `ping()` only reads: it never moves the motor.
- `error_flags()` clears nothing; the `take_*` calls clear what they read.
- The Jrk decides what a target means (a position with analog feedback). This
  crate knows no radians: `spine-board` turns them into targets.
- Bus errors come back as `Result`; nothing panics.

## Side Effects

- I2C writes and reads to one Jrk. `set_target` and `stop_motor` move or stop a
  motor (steering or brake), and restart the Jrk's serial timeout.
- The `take_*` calls clear the Jrk's latched error bits.

## Verification

```sh
cd firmware/spine
cargo test -p jrk-g2
```

The tests play the Jrk with `embedded-hal-mock` and check the exact bytes. One of them
is the user's guide's own example: a target of 3229 is `0xDD 0x64`.

## Ported from

The 2025-26 firmware in `firmware/legacy/aav_umod_esp32/src/` (from AAV_cortex,
commit 90de619e52):

| Here | C++ file | C++ function |
|---|---|---|
| `set_target` | `modules/jrk_g2/jrk_g2.cpp` | `setSteer()` and `setBrake()`, through Pololu's `JrkG2I2C::setTarget()` |
| `take_error_flags` | `modules/jrk_g2/jrk_g2.cpp` | `setSteer()` and `setBrake()`: `getErrorFlagsHalting()` after each target |
| `ping` | `modules/jrk_g2/jrk_g2.cpp` | `jrkPing()` |
| addresses 0x05 and 0x04 | `modules/hardware_configs.h` | `STEER_ID`, `BRAKE_ID` |

Changed on purpose:

| What | C++ | Here |
|---|---|---|
| `ping` | an empty write | a read of the target: it proves the Jrk answers, without an empty write |
| Jrk errors | printed, then ignored | `spine-board` turns them into driver faults, which stop the car |

New here, not in the C++: `stop_motor`, `target`, `feedback`, `scaled_feedback`,
`error_flags`, `take_errors_occurred`.
