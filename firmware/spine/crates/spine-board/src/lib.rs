//! The glue between `spine-core` and the car's devices, for any board.
//!
//! `spine-core` decides; this crate connects it to the hardware without knowing which
//! chip runs it. A board crate (ESP32, Pico 2 or STM32, once the team picks: Q10 to
//! Q13) implements [`Board`], builds a [`SpineBoard`], and calls
//! [`SpineBoard::tick`] about 100 times a second.
//!
//! ```text
//!  Board: clock, e-stop pin,     RC receiver's        I2C bus: steering Jrk 0x05,
//!  wheel counter, CAN            serial port          brake Jrk 0x04, DAC 0x0C,
//!  (this crate's trait)          (embedded-io)        expander 0x20 (embedded-hal)
//!        |                            |                         |
//!        +----------------------------+-------------------------+
//!                                     |
//!                           SpineBoard::tick()
//!       read  -->  Inputs  -->  Spine::step  -->  Outputs  -->  write
//! ```
//!
//! | Module | Does |
//! |---|---|
//! | [`board`] | the [`Board`] trait: what differs from chip to chip |
//! | [`calibration`] | today's numbers: addresses, steering, brake, throttle, direction |
//! | [`actuators`] | drives the devices from `Outputs` in a safe order, and reads them |
//! | [`wheel`] | the speed, from the wheel encoder's counter |
//! | [`spine_board`] | the loop: [`SpineBoard`] |
//!
//! A board crate, in outline:
//!
//! ```text
//! let bus = RefCell::new(i2c);  // one bus for four devices (embedded-hal-bus)
//! let cal = Calibration::TODAY;
//! let devices = Devices::new(RefCellDevice::new(&bus), RefCellDevice::new(&bus),
//!                            RefCellDevice::new(&bus), RefCellDevice::new(&bus), &cal);
//! let mut spine = SpineBoard::new(my_board, devices, ibus_uart, cal, SpineConfig::default());
//! spine.init();
//! loop {
//!     spine.tick();
//!     // wait for the next 10 ms
//! }
//! ```
//!
//! Plain `no_std` Rust, tested on a laptop with mocks.
#![no_std]

pub mod actuators;
pub mod board;
pub mod calibration;
#[cfg(test)]
mod rig;
pub mod spine_board;
pub mod wheel;

pub use actuators::{Actuators, Devices, Readings};
pub use board::{Board, CanFrame, WheelCount};
pub use calibration::Calibration;
pub use spine_board::SpineBoard;
pub use wheel::WheelSpeed;
