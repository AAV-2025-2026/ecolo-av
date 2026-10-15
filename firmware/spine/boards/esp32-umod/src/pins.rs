//! The pin map: the one list of what this program does with the ESP32's pins.
//!
//! Every pin the 2025-26 C++ used is used the same way here (`hardware_configs.h`,
//! `main.cpp`). `docs/rust-firmware.md` has the same table; change both together.
//!
//! | GPIO | MicroMod pad | Signal | Goes to | From the C++ |
//! |---|---|---|---|---|
//! | 16 | 19 (RX1) | UART1 RX, 115200 8N1 | the Motor-Pi's TX: the 13-byte frames | `Serial1.begin(115200, SERIAL_8N1, 16, 17)` |
//! | 17 | 17 (TX1) | not driven | the Motor-Pi's RX | the C++ set it up as TX, and sent nothing on it |
//! | 32 | 73 (G5) | UART2 RX, 115200 8N1, pull-up | the FlySky receiver's iBUS | `IBUS_RX_PIN 32` |
//! | 33 | 71 (G6) | not driven | — | `IBUS_TX_PIN 33`, never used |
//! | 21 | 12 | I2C SDA, 100 kHz | Jrk steering 0x05, Jrk brake 0x04, DAC 0x0C, PCA9555 0x20 | `I2C_SDA 21` |
//! | 22 | 14 | I2C SCL | the same | `I2C_SCL 22` |
//! | 2 | — | output | the processor board's blue status LED | `LED_PIN 2` |
//! | 18 | 57 | output | the carrier's red LED | `RED_LED_PIN 18` |
//! | 19 | 61 | output | the carrier's green LED | `GREEN_LED_PIN 19` |
//! | 14 | 10 (D0) | output | the carrier's blue LED | `BLUE_LED_PIN 14` |
//! | 25 | 42 (G1) | TWAI TX, with `--features can` | the CAN transceiver (U7)? **UNKNOWN** | none: the C++ had no CAN |
//! | 26 | 44 (G2) | TWAI RX, with `--features can` | the same, **UNKNOWN** | none |
//! | 27 | 18 (D1) | input, pull-up, with `--features estop-input` | the e-stop's spare contact? **UNKNOWN** | none: the C++ had no e-stop input |
//!
//! The direction output is not an ESP32 pin: it is pin P00 of the PCA9555 on the I2C bus
//! (`DIR_PIN 0`), set in `spine-board`'s `Calibration::TODAY`.
//!
//! **The CAN pins are a guess** (TODO, Ben). SparkFun's ESP32 MicroMod schematic
//! (`SparkFun_MicroMod_ESP32.sch`) has no net on MicroMod's CAN pads (41, 43): if the
//! carrier wires U7 to those pads, it never reaches the ESP32. Find where U7's TXD and RXD
//! go (a meter, or the carrier's schematic), then set them here. 25 and 26 are free, and
//! sit beside the CAN pads.
//!
//! **The e-stop pin is a guess too** (Q6): nothing on this board is known to carry the
//! spare contact. 27 is free. Leave `estop-input` off until it is wired.

#[cfg(feature = "estop-input")]
use esp_hal::gpio::Level;

/// The e-stop's spare contact closes to ground while the button is out, so the pin reads
/// high when the button is pressed, and also when the wire is cut. TODO(Q6).
#[cfg(feature = "estop-input")]
pub const ESTOP_OPEN: Level = Level::High;

/// The pins, taken from the peripherals once, in the order of the table above.
macro_rules! take_pins {
    ($p:expr) => {
        $crate::pins::Pins {
            motor_pi_rx: $p.GPIO16,
            ibus_rx: $p.GPIO32,
            sda: $p.GPIO21,
            scl: $p.GPIO22,
            status_led: $p.GPIO2,
            red_led: $p.GPIO18,
            green_led: $p.GPIO19,
            blue_led: $p.GPIO14,
            #[cfg(feature = "can")]
            can_tx: $p.GPIO25,
            #[cfg(feature = "can")]
            can_rx: $p.GPIO26,
            #[cfg(feature = "estop-input")]
            estop: $p.GPIO27,
        }
    };
}
pub(crate) use take_pins;

/// The pins, by what they do.
pub struct Pins {
    pub motor_pi_rx: esp_hal::peripherals::GPIO16<'static>,
    pub ibus_rx: esp_hal::peripherals::GPIO32<'static>,
    pub sda: esp_hal::peripherals::GPIO21<'static>,
    pub scl: esp_hal::peripherals::GPIO22<'static>,
    pub status_led: esp_hal::peripherals::GPIO2<'static>,
    pub red_led: esp_hal::peripherals::GPIO18<'static>,
    pub green_led: esp_hal::peripherals::GPIO19<'static>,
    pub blue_led: esp_hal::peripherals::GPIO14<'static>,
    #[cfg(feature = "can")]
    pub can_tx: esp_hal::peripherals::GPIO25<'static>,
    #[cfg(feature = "can")]
    pub can_rx: esp_hal::peripherals::GPIO26<'static>,
    #[cfg(feature = "estop-input")]
    pub estop: esp_hal::peripherals::GPIO27<'static>,
}
