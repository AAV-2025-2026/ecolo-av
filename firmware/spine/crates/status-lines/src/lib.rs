//! The ESP32's status lines: one JSON object a line, as `firmware/status/README.md` says.
//!
//! | `t` | Type | When |
//! |---|---|---|
//! | `hb` | [`Heartbeat`] | once a second |
//! | `status` | [`Status`] | 5 to 20 times a second |
//! | `event` | [`Event`] | at each change |
//! | `health` | [`Health`] | once a second: the Pi link's verdict, the devices, the faults |
//! | `config` | [`Config`] | at boot and every 10 s: the build and the numbers it runs with |
//! | `devices` | [`DeviceList`] | at boot and every 10 s: which I2C devices answered at boot |
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
/// longest status line, every number at its widest, is 783 bytes (a test checks). The
/// strings in the heartbeat, the event, the health, the config and the device lines are
/// the caller's; keep them short.
pub const MAX_LINE: usize = 832;

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
    Health(Health<'a>),
    Config(Config<'a>),
    Devices(DeviceList<'a>),
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

/// The Pi link's counts since boot, and its verdict now.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct LinkCounts {
    pub frames: u32,
    pub bad: u32,
    pub skipped: u32,
    pub repeats: u32,
    /// The board's verdict (`spine-board`'s `LinkHealth`); `None` (written `null`) on a
    /// link it doesn't judge (CAN).
    pub verdict: Option<Verdict>,
}

/// The Pi link's state, as the board judges it, by the spine's own 100 ms rule.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    /// No good frame since boot.
    NoFrames,
    /// A new command (a new counter) within 100 ms.
    Ok,
    /// Good frames came, then stopped.
    Stale,
    /// Frames come, but the Orin's counter doesn't move: its output mux isn't running.
    CounterFrozen,
    /// Bad frames or stray bytes in the last few seconds.
    BadFrames,
}

impl Verdict {
    /// Its name in a line.
    pub const fn name(self) -> &'static str {
        match self {
            Verdict::NoFrames => "no_frames",
            Verdict::Ok => "ok",
            Verdict::Stale => "stale",
            Verdict::CounterFrozen => "counter_frozen",
            Verdict::BadFrames => "bad_frames",
        }
    }
}

/// `health`: is the board working, in one small object. Also what `/health` serves.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Health<'a> {
    /// `None` on a link the board doesn't judge (CAN).
    pub link: Option<Verdict>,
    /// How old the last good frame is; `None` before the first.
    pub age_ms: Option<u32>,
    /// `None`: no frames to tell from, or no counter (version 1 frames).
    pub counter_moving: Option<bool>,
    pub counts: LinkCounts,
    /// The I2C devices that answered at boot, of how many, and the names of the rest.
    pub devices_answered: u8,
    pub devices_expected: u8,
    pub missing: &'a [&'a str],
    pub faults: u16,
    pub mode: Mode,
    pub last_reset: &'a str,
    pub build: &'a str,
    pub boot_id: u32,
}

/// `config`: the build, and the numbers the firmware runs with.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Config<'a> {
    pub build: &'a str,
    pub features: &'a str,
    /// The program's version (Cargo's).
    pub version: &'a str,
    /// `uart` or `can`.
    pub link: &'a str,
    /// The UART link's frame version (1 or 2); `None` on CAN.
    pub frame_version: Option<u8>,
    pub tick_ms: u32,
    pub watchdog_ms: u32,
    pub cmd_timeout_ms: u32,
    /// The brake while nobody drives, 0..1.
    pub idle_brake: f32,
    /// The open speed loop's scale, m/s.
    pub full_throttle_speed: f32,
    /// The I2C bus speed; `None` with stand-in devices (QEMU).
    pub i2c_khz: Option<u32>,
    pub addresses: Addresses,
    pub steering: SteeringLimits,
    pub brake: BrakeLimits,
    pub throttle_full_code: u16,
    pub last_reset: &'a str,
}

/// The four I2C devices' addresses.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Addresses {
    pub steering: u8,
    pub brake: u8,
    pub dac: u8,
    pub expander: u8,
}

/// The steering Jrk's targets: never beyond `min` and `max`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SteeringLimits {
    pub min: u16,
    pub centre: u16,
    pub max: u16,
}

/// The brake Jrk's targets, released and full.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BrakeLimits {
    pub released: u16,
    pub full: u16,
}

/// `devices`: which I2C devices answered at boot.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DeviceList<'a> {
    pub devices: &'a [DeviceSeen<'a>],
}

/// One I2C device at boot.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DeviceSeen<'a> {
    pub name: &'a str,
    pub address: u8,
    pub answered: bool,
    /// A Jrk's feedback mode (`none`, `analog`, `frequency`, `other`, or `unknown` when
    /// the read failed); `None` (written `null`) for the others.
    pub feedback: Option<&'a str>,
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
            Body::Health(_) => "health",
            Body::Config(_) => "config",
            Body::Devices(_) => "devices",
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
            Body::Health(h) => h.fmt(f)?,
            Body::Config(c) => c.fmt(f)?,
            Body::Devices(d) => d.fmt(f)?,
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
            r#"}},"link":{{"frames":{},"bad":{},"skipped":{},"repeats":{},"verdict":"#,
            l.frames, l.bad, l.skipped, l.repeats
        )?;
        verdict(f, l.verdict)?;
        f.write_char('}')?;
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

/// A verdict, quoted, or `null`.
fn verdict(f: &mut Formatter<'_>, v: Option<Verdict>) -> fmt::Result {
    match v {
        Some(v) => write!(f, r#""{}""#, v.name()),
        None => f.write_str("null"),
    }
}

/// A health line's fields after `up_ms`.
impl Display for Health<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.write_str(r#","link":"#)?;
        verdict(f, self.link)?;
        f.write_str(r#","age_ms":"#)?;
        json::option(f, self.age_ms)?;
        f.write_str(r#","counter_moving":"#)?;
        json::option(f, self.counter_moving)?;
        let c = &self.counts;
        write!(
            f,
            r#","frames":{},"bad":{},"skipped":{},"repeats":{},"devices":{{"answered":{},"expected":{},"missing":["#,
            c.frames, c.bad, c.skipped, c.repeats, self.devices_answered, self.devices_expected
        )?;
        for (i, name) in self.missing.iter().enumerate() {
            if i > 0 {
                f.write_char(',')?;
            }
            Text(name).fmt(f)?;
        }
        write!(
            f,
            r#"]}},"faults":{},"mode":"{}","last_reset":{},"build":{},"boot_id":"{:08x}""#,
            self.faults,
            self.mode.name(),
            Text(self.last_reset),
            Text(self.build),
            self.boot_id
        )
    }
}

/// A config line's fields after `up_ms`.
impl Display for Config<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(
            f,
            r#","build":{},"features":{},"version":{},"link":{},"frame_version":"#,
            Text(self.build),
            Text(self.features),
            Text(self.version),
            Text(self.link)
        )?;
        json::option(f, self.frame_version)?;
        write!(
            f,
            r#","tick_ms":{},"watchdog_ms":{},"cmd_timeout_ms":{},"idle_brake":{},"full_throttle_speed":{},"i2c_khz":"#,
            self.tick_ms,
            self.watchdog_ms,
            self.cmd_timeout_ms,
            Float(self.idle_brake),
            Float(self.full_throttle_speed)
        )?;
        json::option(f, self.i2c_khz)?;
        let (a, s, b) = (&self.addresses, &self.steering, &self.brake);
        write!(
            f,
            r#","addresses":{{"steering":{},"brake":{},"dac":{},"expander":{}}}"#,
            a.steering, a.brake, a.dac, a.expander
        )?;
        write!(
            f,
            r#","steering":{{"min":{},"centre":{},"max":{}}},"brake":{{"released":{},"full":{}}}"#,
            s.min, s.centre, s.max, b.released, b.full
        )?;
        write!(
            f,
            r#","throttle_full_code":{},"last_reset":{}"#,
            self.throttle_full_code,
            Text(self.last_reset)
        )
    }
}

/// A devices line's fields after `up_ms`.
impl Display for DeviceList<'_> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        let answered = self.devices.iter().filter(|d| d.answered).count();
        write!(
            f,
            r#","answered":{},"expected":{},"list":["#,
            answered,
            self.devices.len()
        )?;
        for (i, d) in self.devices.iter().enumerate() {
            if i > 0 {
                f.write_char(',')?;
            }
            write!(
                f,
                r#"{{"name":{},"address":{},"answered":{},"feedback":"#,
                Text(d.name),
                d.address,
                d.answered
            )?;
            match d.feedback {
                Some(name) => Text(name).fmt(f)?,
                None => f.write_str("null")?,
            }
            f.write_char('}')?;
        }
        f.write_char(']')
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
