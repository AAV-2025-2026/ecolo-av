//! Where the debug window's news comes from: the ROS node, or the demo. The screen sees
//! only this trait, so it runs the same with either.

use std::time::Instant;

use debug_core::{cubes::CubeScan, state::Update};

/// A source of [`Update`]s and scans.
pub trait DataSource {
    /// A short label for the panel's corner: "ROS" or "DEMO".
    fn label(&self) -> &'static str;

    /// Everything that arrived since the last call. Never blocks.
    fn drain(&mut self, now: Instant) -> Vec<Update>;

    /// The newest scan's cubes, if a new one is ready (older ones were dropped).
    fn take_scan(&mut self) -> Option<CubeScan>;

    /// Whether the source has stopped (Ctrl-C, or the ROS node failed): the window closes.
    fn has_stopped(&self) -> bool {
        false
    }
}
