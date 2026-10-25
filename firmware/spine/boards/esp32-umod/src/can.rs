//! CAN through the ESP32's own controller (TWAI), for `--features can`: the frames of
//! `firmware/can/aav.dbc`, classic CAN at 500 kbit/s, 11-bit IDs.

use embedded_can::Frame as _;
use esp_hal::time::{Duration, Instant};
use esp_hal::twai::{EspTwaiFrame, StandardId, Twai};
use esp_hal::Blocking;
use spine_board::CanFrame;

/// How long a send may wait for the one transmit buffer: a frame takes about 0.25 ms at
/// 500 kbit/s, and two leave in the same tick (VEHICLE_FEEDBACK and VEHICLE_STATUS).
const SEND_WAIT: Duration = Duration::from_millis(2);
/// How often to try to leave bus-off.
const RECOVERY_PERIOD_MS: u32 = 1000;

/// The TWAI controller, as `spine_board::Board` wants it.
pub struct CanPort {
    twai: Twai<'static, Blocking>,
    last_recovery_ms: u32,
}

impl CanPort {
    pub fn new(twai: Twai<'static, Blocking>) -> Self {
        CanPort {
            twai,
            last_recovery_ms: 0,
        }
    }

    /// The next data frame with an 11-bit ID, if any. Others are for someone else.
    pub fn receive(&mut self) -> Option<CanFrame> {
        loop {
            let frame = self.twai.receive().ok()?;
            let embedded_can::Id::Standard(id) = frame.id() else {
                continue;
            };
            if frame.is_remote_frame() {
                continue;
            }
            return CanFrame::new(id.as_raw(), frame.data());
        }
    }

    /// Send a frame, waiting a little for the transmit buffer. False if it couldn't go.
    pub fn send(&mut self, frame: &CanFrame) -> bool {
        let Some(id) = StandardId::new(frame.id()) else {
            return false;
        };
        let Some(out) = EspTwaiFrame::new(id, frame.data()) else {
            return false;
        };
        let start = Instant::now();
        loop {
            match self.twai.transmit(&out) {
                Ok(()) => return true,
                Err(nb::Error::WouldBlock) if start.elapsed() < SEND_WAIT => {}
                Err(_) => return false,
            }
        }
    }

    /// After each tick: start the way back from bus-off, now and then.
    pub fn service(&mut self, now_ms: u32) {
        if self.twai.is_bus_off()
            && now_ms.wrapping_sub(self.last_recovery_ms) >= RECOVERY_PERIOD_MS
        {
            self.last_recovery_ms = now_ms;
            self.twai.initiate_recovery();
        }
    }
}
