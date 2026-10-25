//! The in-car HUD's logic, with no ROS and no raylib, so it is tested on any laptop.
//!
//! | Module | What it holds |
//! |---|---|
//! | [`config`] | the topic names, from `config/hud.yaml` |
//! | [`units`] | speed in m/s and km/h, angles |
//! | [`vehicle`] | `/vehicle/status`: mode, gear letter, fault names |
//! | [`gps`] | a GPS fix: what kind, how accurate |
//! | [`health`] | when each topic was last heard, and OK / STALE / NEVER |
//! | [`origin`] | `/system/source`: real, simulated, bench or replay, per topic |
//! | [`picture`] | a camera picture turned into RGBA pixels for the screen |
//! | [`estop`] | the e-stop button: five `true`s, 0.1 s apart, never `false` |
//! | [`heartbeat`] | `/hud/heartbeat` to the sensor watchdog: 10 Hz while the screen draws |
//! | [`watchdog`] | the sensor watchdog's verdict, as a banner (the map window's too) |
//! | [`gate`] | may the car move? GO / WAIT / STOP and the one main reason: the e-stop, the output mux, the watchdog |
//! | [`state`] | everything above, as one value the screen draws |
//! | [`format`] | numbers turned into short text for the screen |
//! | [`screen`] | which monitor a window goes on (`--monitor HDMI-1`), for two screens |

pub mod config;
pub mod estop;
pub mod format;
pub mod gate;
pub mod gps;
pub mod health;
pub mod heartbeat;
pub mod origin;
pub mod picture;
pub mod screen;
pub mod state;
pub mod units;
pub mod vehicle;
pub mod watchdog;
