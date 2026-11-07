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

use core::fmt::{self, Write};
use spine_board::{LastFrame, LinkStats, Report, TickTiming};
use spine_core::protocol::Mode;
use spine_core::{Outputs, RcSwitch};
use status_lines::{
    Body, Event, Heartbeat, Levels, Line, LinkCounts, Out, Positions, Rc, Rx, Spread, State,
    Status, Switch, Tick, Value, MAX_CHANNELS,
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
    last_reset: Short,
    spread: Spread,
    watched: Option<Watched>,
}

impl Reporter {
    /// `boot_id`: random at each boot. `last_reset`: why the chip reset, as esp-hal names
    /// it (`ChipPowerOn`, ...), if it knows.
    pub fn new(boot_id: u32, last_reset: Option<impl fmt::Debug>) -> Self {
        let mut reason = Short::new();
        // A name too long is cut: it is only for people.
        let _ = match last_reset {
            Some(r) => write!(reason, "{r:?}"),
            None => reason.write_str("Unknown"),
        };
        Reporter {
            seq: 0,
            boot_id,
            last_reset: reason,
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
                    last_reset: self.last_reset.as_str(),
                }),
            };
            emit(&line);
        }
        if ticks.is_multiple_of(STATUS_EVERY_TICKS) {
            let (low, high) = self.spread.take(Levels::from(&out));
            let (link, rx) = match s.link {
                Some((stats, frame)) => (
                    LinkCounts {
                        frames: stats.frames,
                        bad: stats.bad,
                        skipped: stats.skipped,
                        repeats: stats.repeats,
                    },
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

fn mode(m: Mode) -> status_lines::Mode {
    match m {
        Mode::Manual => status_lines::Mode::Stopped,
        Mode::Rc => status_lines::Mode::Rc,
        Mode::Computer => status_lines::Mode::Computer,
        Mode::Test => status_lines::Mode::Test,
    }
}

/// A short name, kept in place: the reset reason.
struct Short {
    buf: [u8; 32],
    len: usize,
}

impl Short {
    const fn new() -> Self {
        Short {
            buf: [0; 32],
            len: 0,
        }
    }

    fn as_str(&self) -> &str {
        core::str::from_utf8(&self.buf[..self.len]).unwrap_or("")
    }
}

impl Write for Short {
    /// Keeps what fits, whole characters only; says so when it cuts.
    fn write_str(&mut self, s: &str) -> fmt::Result {
        for c in s.chars() {
            let mut utf8 = [0; 4];
            let bytes = c.encode_utf8(&mut utf8).as_bytes();
            let end = self.len + bytes.len();
            let Some(dest) = self.buf.get_mut(self.len..end) else {
                return Err(fmt::Error);
            };
            dest.copy_from_slice(bytes);
            self.len = end;
        }
        Ok(())
    }
}
