# mcp2515

## Overview

The Microchip MCP2515 CAN controller, over SPI. The Pico 2's chip (the RP2350) has no CAN
controller of its own, so the spine reaches the car's bus through an MCP2515 and a
transceiver. Plain `no_std` Rust against `embedded-hal` 1.0's `SpiDevice`.

Not the `mcp2515` crate on crates.io: this one is ours, by path.

## Why our own driver

Two crates on crates.io drive this chip. Neither is clearly better than a few hundred lines of
our own, tested like our other drivers.

| Crate | Last release | Why not |
|---|---|---|
| `mcp2515` 0.3.0 | Oct 2024 | no release for two years; fixed Arduino bit timings (75 %, three samples a bit); needs a delay; no error state |
| `mcp25xx` 0.4.0 | Sep 2025 | maintained, `embedded-hal` 1.0: the closer call. But fixed Arduino timings: at 16 MHz and 500 kbit/s it samples at 56 %, where SocketCAN on the Orin samples at 87.5 %; no error state, only raw registers |

## Set up

The bus runs at 500 kbit/s (`firmware/can/aav.dbc`). The bit timing comes from the module's
crystal: read it off the crystal's can ("8.000" or "16.000").

| Crystal | CNF1, CNF2, CNF3 | Quanta a bit | Sample point |
|---|---|---|---|
| 16 MHz | 0x00, 0xB5, 0x01 | 16 | 87.5 %, as Linux sets it |
| 8 MHz | 0x00, 0x91, 0x01 | 8 | 75 %: the most 8 quanta allow |

`BitTiming::new` works it out the way Linux's `can_calc_bittiming()` does, for any crystal
and bitrate, and refuses one it can't make exactly (8 MHz can't make 1 Mbit/s).

## Interface

| Item | Does |
|---|---|
| `Mcp2515::new(spi)` | the chip on an `SpiDevice` (mode 0, at most 10 MHz) |
| `init(&config, &mut delay)` | reset, the bit timing, the filters, INT on a frame, then the mode. Checks that a chip answers |
| `send(&frame)` | into the first free transmit buffer of three; the chip retries until acknowledged |
| `receive()` | the next frame, or `None`; the older buffer first |
| `bus_status()` | a `BusStatus`: `state` (an `ErrorState`, below), `tx_errors`, `rx_errors`, `rx_overflow` (a lost frame), and `mode` (`None` after the chip reset itself) |
| `Config` | `BitTiming`, `Filters`, `Mode` (`Normal`, `ListenOnly`, `Loopback`) |
| `Frame::new_standard(id, data)`, `standard_data()` | an 11-bit data frame by number, and back |
| `Frame::new(id, data)`, `new_remote(id, dlc)` | any classic frame, standard or extended; `Frame` also implements `embedded_can::Frame` |
| `Frame::id()`, `data()`, `dlc()`, `is_remote()` | read a frame back |
| `Crystal` | `MHZ_8`, `MHZ_16`, or `from_hz(hz)`; `hz()` |
| `Bitrate` | `KBPS_125`, `KBPS_250`, `KBPS_500`, `MBPS_1`, or `from_bps(bps)`; `bps()` |
| `BitTiming::new(crystal, bitrate)` | the timing, or a `TimingError`; `registers()`, `sample_point_permille()` |
| `BitTiming::quanta()`, `segments()`, `bitrate(crystal)` | quanta a bit; the prescaler and segments (prop, phase 1, phase 2, SJW); the bitrate it gives |
| `release()` | gives the SPI device back |

It re-exports `embedded_can`'s `Id`, `StandardId` and `ExtendedId`.

| Error | When |
|---|---|
| `Spi(e)` | a transfer failed |
| `NoChip` | after a reset, no MCP2515 answers, or it doesn't keep what was written |
| `ModeTimeout` | the mode didn't change within 10 ms |
| `TxBusy` | all three transmit buffers still wait: nobody acknowledges, or the bus is full |
| `BusOff` | the chip left the bus after too many errors; it returns by itself after 128 × 11 idle bits |

## Filters

`Filters::standard_ids(&[ids])` keeps only standard frames with those IDs (1 to
`MAX_IDS` = 6); else a `FilterError` (`NoIds`, `TooManyIds`). `Filters::ids()` gives the
six IDs back (`None` for `all()`). The
spine keeps two: `ESTOP_CMD` 0x010 and `DRIVE_CMD` 0x100. All six filters get a wanted ID,
because a filter left at 0 would let in ID 0x000. `Filters::all()` keeps everything.

## Error states

| State | Counters | Means |
|---|---|---|
| `Active` | under 96 | all well |
| `Warning` | 96 or more | working, but the bus has trouble |
| `Passive` | 128 or more | working, but it signals errors quietly |
| `BusOff` | transmit over 255 | off the bus until it has been idle |

## Invariants

- Never a filter left at its reset value: that would let in ID 0x000.
- The bit timing is exact, or refused. Never a near miss.
- At 16 MHz it samples at 87.5 %, as SocketCAN on the Orin does.
- `init` checks that a chip answers before it trusts it (`NoChip`).
- `send` never overwrites a buffer still waiting (`TxBusy`), and refuses to send
  while off the bus (`BusOff`).
- Errors come back as `Error<E>`; nothing panics.
- The CAN IDs come from `firmware/can/aav.dbc`; this crate knows none of them.

## Side Effects

- SPI transfers to the chip. `init` resets it and changes its mode.
- `send` puts frames on the car's CAN bus; the chip retries until one is
  acknowledged.
- `receive` frees a receive buffer. `init` blocks on the delay (the reset, and up
  to 10 ms for a mode change).

## Verification

```sh
cd firmware/spine
cargo test -p mcp2515
```

The tests play the chip with `embedded-hal-mock`, instruction by instruction: set-up at
8 and 16 MHz, a chip that is missing or can't hear us, each mode, each transmit buffer, both
receive buffers, every error state, and a failing SPI bus. The bit timing is checked against
Linux's numbers, and against the data sheet's rules for every crystal from 4 to 25 MHz.

## Sources

- Microchip, *MCP2515 Stand-Alone CAN Controller with SPI Interface*, DS20001801K:
  Table 12-1 (instructions), Table 11-1 (registers), sections 4.5 (filters), 5 (bit timing)
  and 6.6 (error states).
- Linux: `drivers/net/can/spi/mcp251x.c` (the chip's limits) and
  `drivers/net/can/dev/calc_bittiming.c` (choosing the timing).
