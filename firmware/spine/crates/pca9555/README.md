# pca9555

The PCA9555 16-bit I/O expander, on I2C: sixteen pins, P00 to P07 and P10 to P17,
each an input or an output. Plain `no_std` Rust, written against `embedded-hal` 1.0.

| On today's car | Value |
|---|---|
| Address | 0x20 |
| P00 | the drive direction: high forward, low reverse (unconfirmed: Q4) |
| The other 15 pins | outputs, driven high; what they connect to is unknown (Q13) |

In every 16-bit value, bit n is pin n: P00 is bit 0, P17 is bit 15.

## API

| Call | Sends | Does |
|---|---|---|
| `Pca9555::new(i2c, address)` | nothing | remembers all outputs as high, like the chip at power-up |
| `set_outputs(levels)` | `0x02`, port 0, port 1 | sets all sixteen output levels; 1 is high |
| `set_pin(pin, high)` | `0x02`, port 0, port 1 | sets one output, keeps the others |
| `outputs()` | nothing | the levels last asked for |
| `set_inputs(mask)` | `0x06`, port 0, port 1 | 1 makes a pin an input, 0 an output |
| `set_polarity(mask)` | `0x04`, port 0, port 1 | 1 inverts how an input reads |
| `read_inputs()` | `0x00`, reads 2 bytes | the level on every pin |
| `Pin::P00.mask()` | | a pin's bit |
| `release()` | | gives the bus back |

From TI's PCA9555 data sheet (SCPS131J), section 8.5.2, "Register Map". At power-up
every pin is an input, the output levels are all high, and nothing is inverted.

## Test

```sh
cd firmware/spine
cargo test -p pca9555
```

The tests play the expander with `embedded-hal-mock`, including the exact bytes of the
C++ start-up.

## Ported from

The 2025-26 firmware in `firmware/legacy/aav_umod_esp32/src/` (from AAV_cortex,
commit 90de619e52). It used hideakitai's PCA95x5 Arduino library, version 0.1.3.

| Here | C++ file | C++ function or name |
|---|---|---|
| `set_polarity`, `set_inputs`, `set_outputs` at start-up | `main.cpp` | `setup()`: `polarity(ORIGINAL_ALL)`, `direction(OUT_ALL)`, `write(H_ALL)` |
| `set_pin` | `modules/dac/dac.cpp` | `ext_digitalWrite()`, through the library's `write(port, level)` |
| remembering the levels, starting high | the PCA95x5 library | its `output` copy, which starts at `0xFFFF` |
| P00 is the direction | `modules/hardware_configs.h` | `DIR_PIN` (0) |
| address 0x20 | the PCA95x5 library, `modules/web_handler/web_handler.cpp` | `BASE_I2C_ADDR`; the label in `handleScan()` |

New here, not used by the C++: `read_inputs`.
