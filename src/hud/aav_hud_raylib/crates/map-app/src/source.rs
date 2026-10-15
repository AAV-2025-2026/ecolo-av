//! Where the map window's news comes from: the ROS node, or the demo. The screen sees
//! only this trait, so it runs the same with either.

use std::time::Instant;

use map_core::state::Update;

/// A source of [`Update`]s.
pub trait DataSource {
    /// A short label for the screen's corner: "ROS" or "DEMO".
    fn label(&self) -> &'static str;

    /// Everything that arrived since the last call. Never blocks.
    fn drain(&mut self, now: Instant) -> Vec<Update>;

    /// Whether the source has stopped (Ctrl-C, or the ROS node failed): the window closes.
    fn has_stopped(&self) -> bool {
        false
    }
}
