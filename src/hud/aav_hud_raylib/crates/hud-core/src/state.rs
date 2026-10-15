//! Everything the screen shows, as one value: the newest of each message, and when
//! each topic was last heard.
//!
//! A data source (the ROS node, or the demo) sends [`Update`]s; the screen calls
//! [`HudState::apply`] for each, then draws from the state.

use std::{collections::HashMap, time::Instant};

use crate::{
    config::{HudConfig, Topic},
    gps::Fix,
    health::{Health, LastSeen},
    picture::Picture,
    vehicle::VehicleStatus,
};

/// The battery (sensor_msgs/msg/BatteryState). None = not measured (NaN in the message).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Battery {
    /// Volts.
    pub voltage: Option<f32>,
    /// 0 to 100 (the message gives 0 to 1).
    pub percent: Option<f32>,
    /// Amps; negative while discharging (REP: BatteryState).
    pub current: Option<f32>,
}

impl Battery {
    /// From the message's fields: volts, charge 0..1, amps. NaN means not measured.
    pub fn from_message(voltage: f32, percentage: f32, current: f32) -> Self {
        let measured = |x: f32| x.is_finite().then_some(x);
        Self {
            voltage: measured(voltage),
            percent: measured(percentage).map(|p| (p * 100.0).clamp(0.0, 100.0)),
            current: measured(current),
        }
    }
}

/// What came of the last e-stop message the source published.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EstopReport {
    /// Published; this many nodes subscribe to the e-stop topic.
    Sent { subscribers: usize },
    /// Couldn't publish at all.
    Failed,
}

/// One piece of news from a data source.
#[derive(Debug, Clone, PartialEq)]
pub enum Update {
    Vehicle(VehicleStatus),
    Gps(Fix),
    GpsFiltered(Fix),
    StopSign(bool),
    Battery(Battery),
    Picture(Picture),
    /// The camera sent a picture the HUD can't show; why.
    BadPicture(String),
    Estop(EstopReport),
}

impl Update {
    /// The topic this news came from, if any.
    pub fn topic(&self) -> Option<Topic> {
        match self {
            Self::Vehicle(_) => Some(Topic::VehicleStatus),
            Self::Gps(_) => Some(Topic::Gps),
            Self::GpsFiltered(_) => Some(Topic::GpsFiltered),
            Self::StopSign(_) => Some(Topic::StopSign),
            Self::Battery(_) => Some(Topic::Battery),
            Self::Picture(_) | Self::BadPicture(_) => Some(Topic::Camera),
            Self::Estop(_) => None,
        }
    }
}

/// What the screen draws.
#[derive(Debug, Clone, Default)]
pub struct HudState {
    pub config: HudConfig,
    pub vehicle: Option<VehicleStatus>,
    pub gps: Option<Fix>,
    pub gps_filtered: Option<Fix>,
    pub stop_sign: bool,
    pub battery: Option<Battery>,
    /// Why the last camera picture couldn't be shown; None once one could.
    pub picture_problem: Option<String>,
    /// The last e-stop report since the button was last pressed.
    pub estop: Option<EstopReport>,
    new_picture: Option<Picture>,
    last_seen: HashMap<Topic, LastSeen>,
}

impl HudState {
    /// A state with nothing heard yet.
    pub fn new(config: HudConfig) -> Self {
        Self {
            config,
            ..Self::default()
        }
    }

    /// Takes in one update that arrived at `now`.
    pub fn apply(&mut self, update: Update, now: Instant) {
        if let Some(topic) = update.topic() {
            self.last_seen.entry(topic).or_default().heard(now);
        }
        match update {
            Update::Vehicle(v) => self.vehicle = Some(v),
            Update::Gps(f) => self.gps = Some(f),
            Update::GpsFiltered(f) => self.gps_filtered = Some(f),
            Update::StopSign(s) => self.stop_sign = s,
            Update::Battery(b) => self.battery = Some(b),
            Update::Picture(p) => {
                self.picture_problem = None;
                self.new_picture = Some(p);
            }
            Update::BadPicture(why) => self.picture_problem = Some(why),
            Update::Estop(report) => self.estop = Some(report),
        }
    }

    /// The e-stop button was pressed: forget the last press's report.
    pub fn estop_pressed(&mut self) {
        self.estop = None;
    }

    /// The newest picture, once: the screen uploads it, then it's gone from here.
    pub fn take_new_picture(&mut self) -> Option<Picture> {
        self.new_picture.take()
    }

    /// OK / STALE / NEVER for one topic, at `now`.
    pub fn health(&self, topic: Topic, now: Instant) -> Health {
        self.last_seen
            .get(&topic)
            .copied()
            .unwrap_or_default()
            .health(now, self.config.stale_after())
    }

    /// Every listened topic's name and health, in screen order.
    pub fn topic_health(&self, now: Instant) -> impl Iterator<Item = (&str, Health)> + '_ {
        Topic::LISTENED
            .into_iter()
            .map(move |t| (self.config.topic(t), self.health(t, now)))
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::*;
    use crate::gps::{FixKind, RawFix};
    use crate::units::MetresPerSecond;

    #[test]
    fn updates_mark_their_topic_heard() {
        let start = Instant::now();
        let mut s = HudState::new(HudConfig::default());
        assert_eq!(s.health(Topic::VehicleStatus, start), Health::Never);
        let v = VehicleStatus {
            speed: MetresPerSecond(2.0),
            ..VehicleStatus::default()
        };
        s.apply(Update::Vehicle(v), start);
        assert!(s.health(Topic::VehicleStatus, start).is_ok());
        assert_eq!(s.vehicle.map(|v| v.speed), Some(MetresPerSecond(2.0)));
        let later = start + Duration::from_secs(2);
        assert!(matches!(
            s.health(Topic::VehicleStatus, later),
            Health::Stale(_)
        ));
        assert_eq!(s.health(Topic::Gps, later), Health::Never);
    }

    #[test]
    fn topic_health_lists_names_from_the_config() {
        let mut config = HudConfig::default();
        config.set_topic(Topic::Gps, "/sensors/gps/fix".into());
        let s = HudState::new(config);
        let names: Vec<&str> = s.topic_health(Instant::now()).map(|(n, _)| n).collect();
        assert_eq!(names.len(), Topic::LISTENED.len());
        assert!(names.contains(&"/sensors/gps/fix"));
    }

    #[test]
    fn a_no_fix_message_still_counts_as_heard() {
        // "Is there GPS data?" A receiver with no fix is alive; a silent one isn't.
        let now = Instant::now();
        let mut s = HudState::new(HudConfig::default());
        let raw = RawFix {
            status: -1,
            ..RawFix::default()
        };
        s.apply(Update::Gps(Fix::from(raw)), now);
        assert!(s.health(Topic::Gps, now).is_ok());
        assert_eq!(s.gps.map(|f| f.kind), Some(FixKind::NoFix));
    }

    #[test]
    fn a_picture_is_taken_once() {
        let now = Instant::now();
        let mut s = HudState::new(HudConfig::default());
        s.apply(Update::BadPicture("yuv422".into()), now);
        assert!(s.picture_problem.is_some());
        let p = Picture {
            width: 1,
            height: 1,
            rgba: vec![0, 0, 0, 255],
        };
        s.apply(Update::Picture(p), now);
        assert!(s.picture_problem.is_none());
        assert!(s.take_new_picture().is_some());
        assert!(s.take_new_picture().is_none());
    }

    #[test]
    fn battery_from_message() {
        let b = Battery::from_message(50.9, 0.997, f32::NAN);
        assert_eq!(b.voltage, Some(50.9));
        assert!(b.percent.is_some_and(|p| (p - 99.7).abs() < 1e-3));
        assert_eq!(b.current, None);
    }

    #[test]
    fn estop_reports_reset_on_press() {
        let mut s = HudState::new(HudConfig::default());
        s.apply(
            Update::Estop(EstopReport::Sent { subscribers: 0 }),
            Instant::now(),
        );
        assert!(s.estop.is_some());
        s.estop_pressed();
        assert!(s.estop.is_none());
    }
}
