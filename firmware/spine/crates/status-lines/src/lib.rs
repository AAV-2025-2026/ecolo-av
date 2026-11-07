//! The ESP32's status lines: one JSON object a line, as `firmware/status/README.md` says.
//!
//! | `t` | Type | When |
//! |---|---|---|
//! | `hb` | [`Heartbeat`] | once a second |
//! | `status` | [`Status`] | 5 to 20 times a second |
//! | `event` | [`Event`] | at each change |
//!
//! A [`Line`] is one of them with its `seq` and `up_ms`. It is [`Display`](core::fmt::Display),
//! so it can go straight to a log, or into a fixed buffer with [`Line::write_to`] or a
//! [`LineBuf`] for a socket. Nothing allocates. [`Spread`] keeps the lowest and highest
//! device values between two status lines; [`Trickle`] hands lines to a slow serial log a
//! few bytes a tick.
//!
//! The lines are built from values the tick already has: this crate reads nothing.
//! `golden.jsonl` beside the contract is the test: every line here is checked against it
//! byte for byte.
#![no_std]

mod json;
mod spread;
mod trickle;

use core::fmt::{self, Display, Formatter, Write};

pub use spread::Spread;
pub use trickle::{Dropped, Trickle};

use json::{Float, Text};

/// The contract's schema number (`firmware/status/README.md`).
pub const SCHEMA: u32 = 1;

/// A buffer this long holds any line this crate writes, with a little to spare: the
/// longest status line, every number at its widest, is 756 bytes (a test checks). The
/// heartbeat's and the event's strings are the caller's; keep them short.
pub const MAX_LINE: usize = 768;

/// How many RC channels a status line carries at most.
pub const MAX_CHANNELS: usize = 14;

/// One line: its kind and values, its number and the board's uptime.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Line<'a> {
    /// Counts up by one for every line of any kind: a gap means lines were lost.
    pub seq: u32,
    /// Milliseconds since boot.
    pub up_ms: u32,
    pub body: Body<'a>,
}

/// What a line says.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Body<'a> {
    Heartbeat(Heartbeat<'a>),
    Status(Status<'a>),
    Event(Event<'a>),
}

/// `hb`: the board is alive, and which program it runs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Heartbeat<'a> {
    /// Random at each boot: a new one means the board restarted.
    pub boot_id: u32,
    /// The program's git commit, short.
    pub build: &'a str,
    /// The features it was built with, comma-separated.
    pub features: &'a str,
    /// Why the chip last reset, as the HAL names it.
    pub last_reset: &'a str,
}

/// `status`: what the board received, what it asked of each device, and how it is.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Status<'a> {
    /// The last good frame from the Pi; `None` before the first.
    pub rx: Option<Rx>,
    pub out: Out,
    /// The lowest and highest of `out` since the last status line ([`Spread`]).
    pub low: Levels,
    pub high: Levels,
    pub pos: Positions,
    pub link: LinkCounts,
    pub rc: Rc<'a>,
    pub state: State,
    pub tick: Tick,
}

/// The last good frame from the Pi.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Rx {
    /// The frame's version: 1, 2 or 3.
    pub version: u8,
    /// The Orin's counter; `None` in version 1 (written `null`).
    pub counter: Option<u8>,
    /// The frame's last byte: its sum or CRC.
    pub check: u8,
    /// Steering, speed and accel, -1..1, as the frame said. A value that is not a
    /// finite number is written `null`.
    pub steer: f32,
    pub speed: f32,
    pub accel: f32,
    /// How long ago it came.
    pub age_ms: u32,
}

/// What the firmware asked of each device.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Out {
    pub steer_counts: u16,
    pub brake_counts: u16,
    pub dac: u16,
    pub reverse: bool,
}

/// The three device values that [`Spread`] follows.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Levels {
    pub steer_counts: u16,
    pub brake_counts: u16,
    pub dac: u16,
}

impl From<&Out> for Levels {
    fn from(out: &Out) -> Self {
        Levels {
            steer_counts: out.steer_counts,
            brake_counts: out.brake_counts,
            dac: out.dac,
        }
    }
}

/// Each Jrk's position in counts; `None` when not known (written `null`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Positions {
    pub steer: Option<u16>,
    pub brake: Option<u16>,
}

/// The Pi link's counts since boot.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct LinkCounts {
    pub frames: u32,
    pub bad: u32,
    pub skipped: u32,
    pub repeats: u32,
}

/// The RC: its mode switch, and the raw channels (none while it is silent).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rc<'a> {
    pub switch: Switch,
    /// At most [`MAX_CHANNELS`] are written.
    pub channels: &'a [u16],
}

/// The RC's mode switch.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Switch {
    Computer,
    /// RC through ROS (the three-position switch's middle).
    ViaRos,
    /// RC straight to this board.
    Direct,
    /// The receiver is silent, or the switch is out of range.
    NoSignal,
}

impl Switch {
    /// Its name in a line.
    pub const fn name(self) -> &'static str {
        match self {
            Switch::Computer => "computer",
            Switch::ViaRos => "via_ros",
            Switch::Direct => "direct",
            Switch::NoSignal => "no_signal",
        }
    }
}

/// Who drives.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    /// Nobody: the actuators are idle (`spine-core`'s `Manual`).
    Stopped,
    Rc,
    Computer,
    /// The hardware test mode.
    Test,
}

impl Mode {
    /// Its name in a line.
    pub const fn name(self) -> &'static str {
        match self {
            Mode::Stopped => "stopped",
            Mode::Rc => "rc",
            Mode::Computer => "computer",
            Mode::Test => "test",
        }
    }
}

/// The spine's state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct State {
    pub mode: Mode,
    pub armed: bool,
    pub estop: bool,
    /// `spine-core`'s fault bits.
    pub faults: u16,
}

/// The tick's timing since boot (`spine-board`'s `TickTiming`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Tick {
    pub worst_gap_us: u32,
    pub overruns: u32,
}

/// `event`: something changed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Event<'a> {
    /// What changed: `mode`, `armed`, ...
    pub what: &'a str,
    pub from: Value<'a>,
    pub to: Value<'a>,
}

/// One value in an event.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Value<'a> {
    Text(&'a str),
    Flag(bool),
    Number(u32),
}

/// The line did not fit in the buffer. Nothing in it is to be used.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TooLong;

impl Display for TooLong {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_str("the status line did not fit in its buffer")
    }
}

impl Line<'_> {
    /// The line into `buf`, without a newline. Returns the part of `buf` it filled.
    pub fn write_to<'b>(&self, buf: &'b mut [u8]) -> Result<&'b str, TooLong> {
        let mut w = SliceWriter { buf, len: 0 };
        write!(w, "{self}").map_err(|_| TooLong)?;
        let SliceWriter { buf, len } = w;
        // Only whole `str`s went in, so the bytes are UTF-8.
        core::str::from_utf8(&buf[..len]).map_err(|_| TooLong)
    }
}

impl Display for Line<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let t = match self.body {
            Body::Heartbeat(_) => "hb",
            Body::Status(_) => "status",
            Body::Event(_) => "event",
        };
        write!(
            f,
            r#"{{"t":"{t}","schema":{SCHEMA},"seq":{},"up_ms":{}"#,
            self.seq, self.up_ms
        )?;
        match &self.body {
            Body::Heartbeat(hb) => write!(
                f,
                r#","boot_id":"{:08x}","build":{},"features":{},"last_reset":{}"#,
                hb.boot_id,
                Text(hb.build),
                Text(hb.features),
                Text(hb.last_reset)
            )?,
            Body::Status(s) => s.fmt(f)?,
            Body::Event(e) => write!(
                f,
                r#","what":{},"from":{},"to":{}"#,
                Text(e.what),
                e.from,
                e.to
            )?,
        }
        f.write_char('}')
    }
}

/// A status line's fields after `up_ms`, each with its leading comma.
impl Display for Status<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_str(r#","rx":"#)?;
        match &self.rx {
            None => f.write_str("null")?,
            Some(rx) => {
                write!(f, r#"{{"v":{},"counter":"#, rx.version)?;
                json::option(f, rx.counter)?;
                write!(
                    f,
                    r#","check":{},"steer":{},"speed":{},"accel":{},"age_ms":{}}}"#,
                    rx.check,
                    Float(rx.steer),
                    Float(rx.speed),
                    Float(rx.accel),
                    rx.age_ms
                )?;
            }
        }
        let o = &self.out;
        write!(
            f,
            r#","out":{{"steer_counts":{},"brake_counts":{},"dac":{},"reverse":{}}}"#,
            o.steer_counts, o.brake_counts, o.dac, o.reverse
        )?;
        write!(f, r#","low":{},"high":{}"#, self.low, self.high)?;
        f.write_str(r#","pos":{"steer":"#)?;
        json::option(f, self.pos.steer)?;
        f.write_str(r#","brake":"#)?;
        json::option(f, self.pos.brake)?;
        let l = &self.link;
        write!(
            f,
            r#"}},"link":{{"frames":{},"bad":{},"skipped":{},"repeats":{}}}"#,
            l.frames, l.bad, l.skipped, l.repeats
        )?;
        write!(f, r#","rc":{{"switch":"{}","ch":["#, self.rc.switch.name())?;
        for (i, ch) in self.rc.channels.iter().take(MAX_CHANNELS).enumerate() {
            if i > 0 {
                f.write_char(',')?;
            }
            write!(f, "{ch}")?;
        }
        let s = &self.state;
        write!(
            f,
            r#"]}},"state":{{"mode":"{}","armed":{},"estop":{},"faults":{}}}"#,
            s.mode.name(),
            s.armed,
            s.estop,
            s.faults
        )?;
        write!(
            f,
            r#","tick":{{"worst_gap_us":{},"overruns":{}}}"#,
            self.tick.worst_gap_us, self.tick.overruns
        )
    }
}

impl Display for Levels {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(
            f,
            r#"{{"steer_counts":{},"brake_counts":{},"dac":{}}}"#,
            self.steer_counts, self.brake_counts, self.dac
        )
    }
}

impl Display for Value<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        match *self {
            Value::Text(s) => Text(s).fmt(f),
            Value::Flag(b) => write!(f, "{b}"),
            Value::Number(n) => write!(f, "{n}"),
        }
    }
}

/// A line in a buffer of its own, `N` bytes: for a queue or a socket.
#[derive(Clone)]
pub struct LineBuf<const N: usize = MAX_LINE> {
    buf: [u8; N],
    len: usize,
}

impl<const N: usize> LineBuf<N> {
    /// An empty buffer.
    pub const fn new() -> Self {
        LineBuf {
            buf: [0; N],
            len: 0,
        }
    }

    /// Replace what it holds with `line`. On [`TooLong`] it holds nothing.
    pub fn set(&mut self, line: &Line<'_>) -> Result<(), TooLong> {
        self.len = 0;
        let len = line.write_to(&mut self.buf)?.len();
        self.len = len;
        Ok(())
    }

    /// The line, without a newline; empty if none.
    pub fn as_str(&self) -> &str {
        // `set` only keeps what `write_to` checked.
        core::str::from_utf8(&self.buf[..self.len]).unwrap_or("")
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.len]
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

impl<const N: usize> Default for LineBuf<N> {
    fn default() -> Self {
        Self::new()
    }
}

impl<const N: usize> fmt::Debug for LineBuf<N> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.debug_tuple("LineBuf").field(&self.as_str()).finish()
    }
}

/// `fmt::Write` into a byte slice; an error once it is full.
struct SliceWriter<'b> {
    buf: &'b mut [u8],
    len: usize,
}

impl Write for SliceWriter<'_> {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        let end = self.len.checked_add(s.len()).ok_or(fmt::Error)?;
        let dest = self.buf.get_mut(self.len..end).ok_or(fmt::Error)?;
        dest.copy_from_slice(s.as_bytes());
        self.len = end;
        Ok(())
    }
}

#[cfg(test)]
mod tests;
