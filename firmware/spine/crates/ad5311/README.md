# ad5311

The throttle DAC: an Analog Devices AD5311, a 10-bit DAC on I2C. Its output goes to
the motor controller's throttle input: code 0 is 0 V, code 1023 is almost its supply
voltage. Plain `no_std` Rust, written against `embedded-hal` 1.0.

| On today's car | Value |
|---|---|
| Address | 0x0C (A0 pin low) |
| Highest code | 700 of 1023, about 68 % (unconfirmed: Q4) |

## Which chip

The 2025-26 firmware never names the chip. Three clues fit the AD5311:

| Clue | The C++ | The AD5311 data sheet |
|---|---|---|
| Address | 0x0C | `000110`, then the A0 pin: 0x0C with A0 low |
| Its own label | "DAC (A0=GND)" | the address pin is called A0 |
| The two bytes | `(v >> 6) & 0x0F`, `(v << 2) & 0xFC` | `x x PD1 PD0 D9..D6`, then `D5..D0 x x` |

TI's DAC101C081 takes the same two bytes, but it answers at 0x0C only with its ADR0
pin floating (0x0D when tied to ground). This driver works for either.
TODO(Q13): read the part number off today's board.

## API

| Call | Does |
|---|---|
| `Ad5311::new(i2c, address)` | a DAC with no limit below 1023 |
| `Ad5311::with_limit(i2c, address, limit)` | a DAC that never writes above `limit` |
| `set_code(code)` | sets the output; above the limit it writes the limit, and returns what it wrote |
| `power_down(mode)` | turns the output off: pulled down through 1 kΩ or 100 kΩ, or floating |
| `read()` | reads back the code and mode; also checks the DAC answers |
| `encode(code, mode)`, `decode(bytes)` | the two bytes, without a bus |
| `release()` | gives the bus back |

From the *AD5301/AD5311/AD5321* data sheet (Rev. C), sections "Serial interface",
"Input shift register" (Figure 27), "Read operation" and "Power-down modes" (Table 6).

## Test

```sh
cd firmware/spine
cargo test -p ad5311
```

The tests play the DAC with `embedded-hal-mock`. One checks every code, 0 to 1023,
against the C++ formula.

## Ported from

The 2025-26 firmware in `firmware/legacy/aav_umod_esp32/src/` (from AAV_cortex,
commit 90de619e52):

| Here | C++ file | C++ function or name |
|---|---|---|
| `encode`, `set_code` | `modules/dac/dac.cpp` | `writeDAC()` |
| the limit (700) | `modules/dac/dac.cpp`, `modules/hardware_configs.h` | `writeDACRamped()` clamps to `DAC_MAX_CAP` |
| `read` as a presence check | `modules/dac/dac.cpp` | `detectDAC()` |
| address 0x0C | `modules/hardware_configs.h`, `modules/web_handler/web_handler.cpp` | `DAC_ADDR`; the label in `handleScan()` |

Changed on purpose:

| What | C++ | Here |
|---|---|---|
| A code above 1023 | masked with `0x3FF`, so 1024 became 0 | sent as 1023, or the limit |
| Presence check | an empty write | a read of the DAC's register |

The throttle's ramp and its scaling (0..1 to 0..700) are in `spine-board`.
