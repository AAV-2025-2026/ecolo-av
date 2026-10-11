//! CAN through the MCP2515: what `spine_board::Board` asks for, and keeping the chip up.
//!
//! The spine works without CAN too: the RC transmitter still drives, and the computer can't.
//! So a chip that doesn't answer at boot is tried again every second, and a chip that reset
//! itself (a dip in its supply) is set up again.

use crate::{CAN_BITRATE, CAN_CHECK_MS, CAN_CRYSTAL, CAN_MODE, CAN_RETRY_MS};
use defmt::{info, warn, Debug2Format};
use embassy_time::Delay;
use embedded_hal::spi::SpiDevice;
use mcp2515::{BitTiming, Config, ErrorState, Filters, Frame, Mcp2515, StandardId};
use spine_board::CanFrame;
use spine_core::protocol::{DRIVE_CMD_ID, ESTOP_CMD_ID};

/// The only frames the spine takes (`firmware/can/aav.dbc`); the chip drops the rest.
const ESTOP_CMD: StandardId = StandardId::new(ESTOP_CMD_ID).expect("an 11-bit ID");
const DRIVE_CMD: StandardId = StandardId::new(DRIVE_CMD_ID).expect("an 11-bit ID");

/// The MCP2515, and whether it is set up and on the bus.
pub struct CanPort<SPI> {
    chip: Mcp2515<SPI>,
    /// None if the crystal can't make the bitrate: then CAN never comes up.
    config: Option<Config>,
    up: bool,
    next_check_ms: u32,
    state: Option<ErrorState>,
}

impl<SPI: SpiDevice> CanPort<SPI> {
    pub fn new(chip: Mcp2515<SPI>, now_ms: u32) -> Self {
        let config = BitTiming::new(CAN_CRYSTAL, CAN_BITRATE)
            .ok()
            .zip(Filters::standard_ids(&[ESTOP_CMD, DRIVE_CMD]).ok())
            .map(|(timing, filters)| Config {
                timing,
                filters,
                mode: CAN_MODE,
            });
        CanPort {
            chip,
            config,
            up: false,
            next_check_ms: now_ms,
            state: None,
        }
    }

    pub fn is_up(&self) -> bool {
        self.up
    }

    /// Once a tick: set the chip up if it is down (every `CAN_RETRY_MS`), or check it
    /// (every `CAN_CHECK_MS`).
    pub fn service(&mut self, now_ms: u32) {
        if (now_ms.wrapping_sub(self.next_check_ms) as i32) < 0 {
            return;
        }
        if self.up {
            self.check(now_ms);
        } else {
            self.bring_up(now_ms);
        }
    }

    /// The next frame for the spine, if any. A remote or an extended frame with one of our
    /// IDs passes the filters, but isn't ours: it is skipped.
    pub fn receive(&mut self) -> Option<CanFrame> {
        if !self.up {
            return None;
        }
        for _ in 0..2 {
            match self.chip.receive() {
                Ok(Some(frame)) => {
                    if let Some((id, data)) = frame.standard_data() {
                        return CanFrame::new(id, data);
                    }
                }
                Ok(None) | Err(_) => return None,
            }
        }
        None
    }

    /// Queue a frame; false if it can't go (the chip is down, off the bus, or full).
    pub fn send(&mut self, frame: &CanFrame) -> bool {
        self.up
            && Frame::new_standard(frame.id(), frame.data())
                .is_some_and(|frame| self.chip.send(&frame).is_ok())
    }

    fn bring_up(&mut self, now_ms: u32) {
        self.next_check_ms = now_ms.wrapping_add(CAN_RETRY_MS);
        let Some(config) = self.config else {
            warn!("CAN off: the crystal can't make the bitrate (CAN_CRYSTAL)");
            return;
        };
        match self.chip.init(&config, &mut Delay) {
            Ok(()) => {
                info!("CAN up: MCP2515, {} bit/s", CAN_BITRATE.bps());
                self.up = true;
                self.state = None;
                self.next_check_ms = now_ms.wrapping_add(CAN_CHECK_MS);
            }
            Err(e) => warn!("CAN down, again in 1 s: {}", Debug2Format(&e)),
        }
    }

    fn check(&mut self, now_ms: u32) {
        self.next_check_ms = now_ms.wrapping_add(CAN_CHECK_MS);
        match self.chip.bus_status() {
            Ok(status) if status.mode == Some(CAN_MODE) => {
                if status.rx_overflow {
                    warn!("CAN: a frame was lost, with both receive buffers full");
                }
                if self.state != Some(status.state) {
                    info!(
                        "CAN: {} (errors: {} sent, {} received)",
                        Debug2Format(&status.state),
                        status.tx_errors,
                        status.rx_errors
                    );
                    self.state = Some(status.state);
                }
            }
            Ok(_) => {
                warn!("CAN: the MCP2515 reset itself; setting it up again");
                self.up = false;
                self.bring_up(now_ms);
            }
            Err(e) => {
                warn!("CAN: no answer from the MCP2515: {}", Debug2Format(&e));
                self.up = false;
            }
        }
    }
}
