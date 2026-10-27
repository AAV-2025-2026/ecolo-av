//! The HUD's heartbeat to the sensor watchdog: `/hud/heartbeat`, the number of frames the
//! screen has drawn, every [`PERIOD`], and only while that number rises.
//!
//! The safety drivers rely on the screen, so the watchdog (aav_safety, its `hud` input)
//! stops Nav2 and the AI slot when the beats stop. They stop when:
//!
//! | What failed | Why the beats stop |
//! |---|---|
//! | the window's loop froze | the frame count stops rising: [`Heartbeat::poll`] sends nothing |
//! | the ROS thread froze | the timer that polls (the e-stop's own) stops |
//! | the program died | nothing at all |
//!
//! The count is a [`Frames`] number, not a bool, so a beat says more than "something on
//! this computer is running": the watchdog also calls a count that stops rising FROZEN.

use std::time::{Duration, Instant};

/// Time between two beats: 10 Hz.
pub const PERIOD: Duration = Duration::from_millis(100);

/// How many frames the screen has drawn since the HUD started.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Default)]
pub struct Frames(pub u64);

/// The heartbeat's state: when the next beat is due, and the count the last one sent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Heartbeat {
    next_at: Option<Instant>,
    sent: Frames,
}

impl Heartbeat {
    /// Call often (every 10 ms). Returns the count to publish when a beat is due and the
    /// screen has drawn since the last one; None otherwise.
    ///
    /// Nothing before the first frame: a window that never drew isn't alive.
    pub fn poll(&mut self, now: Instant, drawn: Frames) -> Option<Frames> {
        if self.next_at.is_some_and(|due| now < due) || drawn <= self.sent {
            return None;
        }
        self.next_at = Some(now + PERIOD);
        self.sent = drawn;
        Some(drawn)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Polls every 10 ms for `span`; `frames` says how many were drawn by then.
    fn run(
        hb: &mut Heartbeat,
        start: Instant,
        span: Duration,
        frames: impl Fn(Duration) -> u64,
    ) -> Vec<(u128, u64)> {
        let step = Duration::from_millis(10);
        let mut sent = Vec::new();
        let mut t = Duration::ZERO;
        while t <= span {
            if let Some(Frames(n)) = hb.poll(start + t, Frames(frames(t))) {
                sent.push((t.as_millis(), n));
            }
            t += step;
        }
        sent
    }

    /// 30 frames a second, the first at 0 ms.
    fn at_30_fps(t: Duration) -> u64 {
        (t.as_millis() / 33 + 1) as u64
    }

    #[test]
    fn a_drawing_screen_beats_ten_times_a_second() {
        let start = Instant::now();
        let mut hb = Heartbeat::default();
        let sent = run(&mut hb, start, Duration::from_millis(990), at_30_fps);
        let times: Vec<u128> = sent.iter().map(|&(t, _)| t).collect();
        assert_eq!(times, [0, 100, 200, 300, 400, 500, 600, 700, 800, 900]);
        // Each beat carries a higher count than the one before.
        assert!(sent.windows(2).all(|w| w[1].1 > w[0].1));
    }

    #[test]
    fn nothing_before_the_first_frame() {
        let mut hb = Heartbeat::default();
        assert_eq!(
            run(&mut hb, Instant::now(), Duration::from_secs(1), |_| 0),
            []
        );
    }

    #[test]
    fn a_frozen_screen_stops_beating_and_starts_again_when_it_draws() {
        let start = Instant::now();
        let mut hb = Heartbeat::default();
        // Draws for 0.3 s, then stuck on frame 10 for a second, then draws again.
        let frames = |t: Duration| match t.as_millis() {
            0..300 => at_30_fps(t),
            300..1300 => 10,
            _ => 10 + at_30_fps(t - Duration::from_millis(1300)),
        };
        let sent = run(&mut hb, start, Duration::from_millis(1500), frames);
        let times: Vec<u128> = sent.iter().map(|&(t, _)| t).collect();
        assert_eq!(times, [0, 100, 200, 300, 1300, 1400, 1500]);
    }

    #[test]
    fn a_slow_screen_beats_as_often_as_it_draws() {
        let start = Instant::now();
        let mut hb = Heartbeat::default();
        // 4 frames a second (a resize, a busy computer): at most 4 beats.
        let sent = run(&mut hb, start, Duration::from_millis(990), |t| {
            (t.as_millis() / 250 + 1) as u64
        });
        assert_eq!(sent.len(), 4);
    }
}
