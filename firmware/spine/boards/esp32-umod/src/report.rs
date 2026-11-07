//! The status lines (`firmware/status`), from what the tick already has.
//!
//! With `json-log` they go on the USB cable, a chunk a tick (`status_lines::Trickle`), in
//! place of the text lines. With `wifi-status` they go to the WiFi tasks (`wifi.rs`), which
//! never make the tick wait.
//!
//! | Line | When |
//! |---|---|
//! | `hb` | once a second |
//! | `status` | every [`STATUS_EVERY_TICKS`] |
//! | `event` | the tick the mode, arming, e-stop or faults change |
//! | `health` | once a second: the Pi link's verdict, the devices, the faults |
//! | `config`, `devices` | 250 and 350 ms after boot, then every 10 s, so a late reader sees them |

use spine_board::{DeviceCheck, LastFrame, LinkReport, LinkStats, LinkVerdict, Report, TickTiming};
use spine_core::protocol::Mode;
use spine_core::{Outputs, RcSwitch};
use status_lines::{
    Body, Config, DeviceList, DeviceSeen, Event, Health, Heartbeat, Levels, Line, LinkCounts, Out,
    Positions, Rc, Rx, Spread, State, Status, Switch, Tick, Value, Verdict, MAX_CHANNELS,
};

/// `status` lines: 10 a second with the WiFi (for its graphs), 5 on the cable alone. Both
/// are inside the contract's 5 to 20.
pub const STATUS_EVERY_TICKS: u32 = if cfg!(feature = "wifi-status") {
    10
} else {
    20
};

/// `hb` lines: once a second, on a tick no status line is on.
const HEARTBEAT_EVERY_TICKS: u32 = 100;
const HEARTBEAT_AT_TICK: u32 = 5;

/// `health` lines: once a second, on a tick no other line is on.
const HEALTH_EVERY_TICKS: u32 = 100;
const HEALTH_AT_TICK: u32 = 55;

/// `config` and `devices` lines: every 10 s, from just after boot.
const CONFIG_EVERY_TICKS: u32 = 1000;
const CONFIG_AT_TICK: u32 = 25;
const DEVICES_AT_TICK: u32 = 35;

/// What one tick had, for its lines. Nothing in it is read from a device for the lines.
pub struct Snapshot<'a> {
    pub now_ms: u32,
    pub out: &'a Outputs,
    /// The tick's `Report` (the RC, the Jrks' positions).
    pub report: Option<&'a Report>,
    /// The RC's raw channels; none while it is silent.
    pub channels: &'a [u16],
    /// The last target sent to each Jrk, the DAC's code, the direction.
    pub steer_counts: u16,
    pub brake_counts: u16,
    pub dac: u16,
    pub reverse: bool,
    /// The Pi link: its counts and last good frame (none on CAN).
    pub link: Option<(LinkStats, Option<LastFrame>)>,
    /// The Pi link's verdict this tick (none on CAN).
    pub health: Option<LinkReport>,
    pub timing: &'a TickTiming,
}

/// The tick's state that an `event` line reports when it changes.
#[derive(Clone, Copy, PartialEq, Eq)]
struct Watched {
    mode: status_lines::Mode,
    armed: bool,
    estop: bool,
    faults: u16,
}

/// Numbers its lines, and decides which lines a tick makes.
pub struct Reporter {
    seq: u32,
    boot_id: u32,
    config: Config<'static>,
    devices: [DeviceSeen<'static>; 4],
    missing: [&'static str; 4],
    missing_len: usize,
    spread: Spread,
    watched: Option<Watched>,
}

impl Reporter {
    /// `boot_id`: random at each boot. `config`: the build and its numbers, with why the
    /// chip last reset. `devices`: what answered at boot.
    pub fn new(boot_id: u32, config: Config<'static>, devices: &DeviceCheck) -> Self {
        let mut seen = [DeviceSeen {
            name: "",
            address: 0,
            answered: false,
            feedback: None,
        }; 4];
        let mut missing = [""; 4];
        let mut missing_len = 0;
        for (slot, found) in seen.iter_mut().zip(devices.iter()) {
            *slot = crate::device_seen(found);
            if !found.answered {
                if let Some(m) = missing.get_mut(missing_len) {
                    *m = found.device.name();
                    missing_len += 1;
                }
            }
        }
        Reporter {
            seq: 0,
            boot_id,
            config,
            devices: seen,
            missing,
            missing_len,
            spread: Spread::new(),
            watched: None,
        }
    }

    /// One tick: give `emit` each line it makes, in order.
    pub fn tick(&mut self, ticks: u32, s: &Snapshot<'_>, mut emit: impl FnMut(&Line<'_>)) {
        let out = Out {
            steer_counts: s.steer_counts,
            brake_counts: s.brake_counts,
            dac: s.dac,
            reverse: s.reverse,
        };
        self.spread.add(Levels::from(&out));
        let state = State {
            mode: mode(s.out.mode),
            armed: s.out.armed,
            estop: s.out.estop_active,
            faults: s.out.faults,
        };
        let now = Watched {
            mode: state.mode,
            armed: state.armed,
            estop: state.estop,
            faults: state.faults,
        };
        if let Some(was) = self.watched.replace(now) {
            for (what, from, to) in changes(&was, &now) {
                let line = Line {
                    seq: self.next_seq(),
                    up_ms: s.now_ms,
                    body: Body::Event(Event { what, from, to }),
                };
                emit(&line);
            }
        }
        if ticks % HEARTBEAT_EVERY_TICKS == HEARTBEAT_AT_TICK {
            let line = Line {
                seq: self.next_seq(),
                up_ms: s.now_ms,
                body: Body::Heartbeat(Heartbeat {
                    boot_id: self.boot_id,
                    build: env!("AAV_BUILD"),
                    features: env!("AAV_FEATURES"),
                    last_reset: self.config.last_reset,
                }),
            };
            emit(&line);
        }
        if ticks % CONFIG_EVERY_TICKS == CONFIG_AT_TICK {
            let line = Line {
                seq: self.next_seq(),
                up_ms: s.now_ms,
                body: Body::Config(self.config),
            };
            emit(&line);
        }
        if ticks % CONFIG_EVERY_TICKS == DEVICES_AT_TICK {
            let line = Line {
                seq: self.next_seq(),
                up_ms: s.now_ms,
                body: Body::Devices(DeviceList {
                    devices: &self.devices,
                }),
            };
            emit(&line);
        }
        if ticks % HEALTH_EVERY_TICKS == HEALTH_AT_TICK {
            let answered = self.devices.iter().filter(|d| d.answered).count();
            let counts = s
                .health
                .map_or(LinkCounts::default(), |h| counts(&h.stats, Some(&h)));
            let line = Line {
                seq: self.next_seq(),
                up_ms: s.now_ms,
                body: Body::Health(Health {
                    link: s.health.map(|h| verdict(h.verdict)),
                    age_ms: s.health.and_then(|h| h.age_ms),
                    counter_moving: s.health.and_then(|h| h.counter_moving),
                    counts,
                    devices_answered: u8::try_from(answered).unwrap_or(u8::MAX),
                    devices_expected: u8::try_from(self.devices.len()).unwrap_or(u8::MAX),
                    missing: &self.missing[..self.missing_len],
                    faults: s.out.faults,
                    mode: state.mode,
                    last_reset: self.config.last_reset,
                    build: self.config.build,
                    boot_id: self.boot_id,
                }),
            };
            emit(&line);
        }
        if ticks.is_multiple_of(STATUS_EVERY_TICKS) {
            let (low, high) = self.spread.take(Levels::from(&out));
            let (link, rx) = match s.link {
                Some((stats, frame)) => (
                    counts(&stats, s.health.as_ref()),
                    frame.map(|f| Rx {
                        version: f.version,
                        counter: f.counter,
                        check: f.check,
                        steer: f.values.steering,
                        speed: f.values.speed,
                        accel: f.values.accel,
                        age_ms: f.age_ms(s.now_ms),
                    }),
                ),
                None => (LinkCounts::default(), None),
            };
            let positions = s.report.map(|r| r.positions).unwrap_or_default();
            let switch = match s.report.and_then(|r| r.rc) {
                None => Switch::NoSignal,
                Some(rc) => match rc.switch {
                    RcSwitch::Computer => Switch::Computer,
                    RcSwitch::ViaRos => Switch::ViaRos,
                    RcSwitch::Direct => Switch::Direct,
                },
            };
            let status = Status {
                rx,
                out,
                low,
                high,
                pos: Positions {
                    steer: positions.steering_counts,
                    brake: positions.brake_counts,
                },
                link,
                rc: Rc {
                    switch,
                    channels: &s.channels[..s.channels.len().min(MAX_CHANNELS)],
                },
                state,
                tick: Tick {
                    worst_gap_us: s.timing.worst_gap_us(),
                    overruns: s.timing.overruns(),
                },
            };
            let line = Line {
                seq: self.next_seq(),
                up_ms: s.now_ms,
                body: Body::Status(status),
            };
            emit(&line);
        }
    }

    /// The next line's number.
    fn next_seq(&mut self) -> u32 {
        let seq = self.seq;
        self.seq = self.seq.wrapping_add(1);
        seq
    }
}

/// The event lines for what changed between two ticks.
fn changes(
    was: &Watched,
    now: &Watched,
) -> impl Iterator<Item = (&'static str, Value<'static>, Value<'static>)> {
    [
        (was.mode != now.mode).then_some((
            "mode",
            Value::Text(was.mode.name()),
            Value::Text(now.mode.name()),
        )),
        (was.armed != now.armed).then_some((
            "armed",
            Value::Flag(was.armed),
            Value::Flag(now.armed),
        )),
        (was.estop != now.estop).then_some((
            "estop",
            Value::Flag(was.estop),
            Value::Flag(now.estop),
        )),
        (was.faults != now.faults).then_some((
            "faults",
            Value::Number(u32::from(was.faults)),
            Value::Number(u32::from(now.faults)),
        )),
    ]
    .into_iter()
    .flatten()
}

/// The link's counts for a line, with the verdict when there is one.
fn counts(stats: &LinkStats, health: Option<&LinkReport>) -> LinkCounts {
    LinkCounts {
        frames: stats.frames,
        bad: stats.bad,
        skipped: stats.skipped,
        repeats: stats.repeats,
        verdict: health.map(|h| verdict(h.verdict)),
    }
}

fn verdict(v: LinkVerdict) -> Verdict {
    match v {
        LinkVerdict::NoFramesYet => Verdict::NoFrames,
        LinkVerdict::Ok => Verdict::Ok,
        LinkVerdict::Stale { .. } => Verdict::Stale,
        LinkVerdict::CounterFrozen { .. } => Verdict::CounterFrozen,
        LinkVerdict::BadFrames { .. } => Verdict::BadFrames,
    }
}

fn mode(m: Mode) -> status_lines::Mode {
    match m {
        Mode::Manual => status_lines::Mode::Stopped,
        Mode::Rc => status_lines::Mode::Rc,
        Mode::Computer => status_lines::Mode::Computer,
        Mode::Test => status_lines::Mode::Test,
    }
}
