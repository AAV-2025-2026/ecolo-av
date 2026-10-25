//! Where the HUD's news comes from: the ROS node, or the demo. The screen sees only this
//! trait, so it runs the same with either.

use std::time::Instant;

use hud_core::state::Update;

/// A source of [`Update`]s, and the way out for the e-stop button.
pub trait DataSource {
    /// A short label for the screen's corner: "ROS" or "DEMO".
    fn label(&self) -> &'static str;

    /// Everything that arrived since the last call. Never blocks.
    fn drain(&mut self, now: Instant) -> Vec<Update>;

    /// The e-stop button was pressed. The source sends the burst of `true`s itself
    /// (hud_core::estop), on its own clock, so a slow frame can't delay it.
    fn press_estop(&mut self);

    /// The window has drawn one more frame. The ROS source counts them for the
    /// heartbeat (hud_core::heartbeat): call it after each frame is on the screen.
    fn frame_drawn(&mut self) {}

    /// Whether the source has stopped (Ctrl-C, or the ROS node failed): the HUD closes.
    fn has_stopped(&self) -> bool {
        false
    }
}
