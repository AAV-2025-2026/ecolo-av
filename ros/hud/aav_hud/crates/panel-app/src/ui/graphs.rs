//! The GRAPHS page: does the Pi pass ego's commands on to the ESP32? The logic, the
//! verdicts and the numbers are panel-core's `graphs`; this only draws them.
//!
//! ```text
//! | LIVE: the last 60 s    ESP32 line: its status lines (ws://..., connected) [FREEZE] |
//! | [ ego  OK ] -> [ mux  OK ] -> [ Pi wrote  OK ] -> [ ESP32 got  NOT TESTED ]         |
//! | Pi wrote 12040 (+600), 0 failed | ESP32 counted ... | uplink ... | lines lost 0       |
//! | STEERING  ~~~~~ Pi wrote (line), ESP32 (dots) ~~~~~     now / avg / low / high      |
//! | BRAKE     ...                                                                        |
//! | THROTTLE  ...                                                                        |
//! | OTHER SENSORS: the IMU's turn rate (graph), the IMU and the GPS (words)              |
//! ```
//!
//! The two lines differ in style, not only colour: the Pi's a line, the ESP32's dots,
//! each labelled at its end (review 2's nits). Gaps where lines were lost or the board
//! restarted (marked BOARD RESTARTED).

use std::time::Instant;

use hud_app::paint::ToColor;
use hud_core::{health::Health, theme::Tone};
use panel_core::{
    graphs::{Channel, Esp32Line, FreezeWhy, Graphs, Hop, Line, Point, Stats, Verdict, WINDOW},
    state::{Esp32Link, PanelState, Row},
};
use raylib::prelude::*;

use super::{fit, wrap, Button, Frame, Room, Ui, MARGIN};

const TOP: f32 = 104.0;
const CHAIN_Y: f32 = 150.0;
const CHAIN_H: f32 = 84.0;
const STRIP_Y: f32 = 244.0;
const GRAPHS_Y: f32 = 274.0;
/// The numbers' column, right of each graph.
const STATS_W: f32 = 250.0;
/// The other sensors' row at the bottom.
const OTHER_H: f32 = 96.0;
const FREEZE_W: f32 = 200.0;

/// The page's one button.
pub fn layout(w: f32) -> Vec<(Button, Rectangle)> {
    vec![(
        Button::Freeze,
        Rectangle::new(w - MARGIN - FREEZE_W, TOP - 4.0, FREEZE_W, 40.0),
    )]
}

fn tone(v: &Verdict) -> Tone {
    match v {
        Verdict::Ok(_) => Tone::Go,
        Verdict::Different(_) => Tone::Stop,
        Verdict::Stale => Tone::Wait,
        Verdict::NoData => Tone::Idle,
        Verdict::NotTested(_) => Tone::Off,
    }
}

/// The y range to draw: the channel's usual one, widened to fit the data.
fn y_range(c: Channel, lines: &[&[Point]]) -> (f64, f64) {
    let (mut lo, mut hi): (f64, f64) = match c {
        Channel::Steering => (-1.0, 1.0),
        Channel::Brake | Channel::Throttle => (0.0, 1.0),
    };
    for p in lines.iter().flat_map(|l| l.iter()) {
        lo = lo.min(p.value);
        hi = hi.max(p.value);
    }
    (lo, hi)
}

impl Ui {
    pub(super) fn draw_graphs(
        &self,
        d: &mut RaylibDrawHandle,
        state: &PanelState,
        f: &Frame<'_>,
        buttons: &[(Button, Rectangle)],
    ) -> Room {
        let t = self.theme;
        let w = d.get_screen_width() as f32;
        let h = d.get_screen_height() as f32;
        let (g, at) = f.freezer.view(&state.graphs, f.now);

        // Live or frozen; where the ESP32's line comes from.
        let (head, ink) = match f.freezer.frozen() {
            None => ("LIVE: the last 60 s".to_owned(), t.good),
            Some((when, why)) => {
                let ago = f.now.saturating_duration_since(when).as_secs();
                let why = match why {
                    FreezeWhy::Pressed => "FREEZE pressed",
                    FreezeWhy::Estop => "an e-stop came on",
                };
                (
                    format!("FROZEN {ago} s ago ({why}): P or FREEZE to go live"),
                    t.warn,
                )
            }
        };
        self.text(d, &head, MARGIN, TOP, 21.0, ink);
        let source = self.esp32_words(state, g, at);
        let x = MARGIN + self.font.measure(&head, 21.0) + 24.0;
        let source = fit(&self.font, &source, w - x - MARGIN - FREEZE_W - 16.0, 16.0);
        self.text(d, &source, x, TOP + 4.0, 16.0, t.caption);
        for &(b, r) in buttons {
            self.button(d, b, r, f, true);
        }

        self.hop_chain(d, g, at, f, w);
        self.strip(d, g, at, w);

        // The three graphs, then the other sensors.
        let bottom = h - 34.0 - OTHER_H;
        let gh = ((bottom - GRAPHS_Y) / 3.0 - 10.0).max(60.0);
        for (i, c) in Channel::ALL.into_iter().enumerate() {
            let y = GRAPHS_Y + i as f32 * (gh + 10.0);
            self.graph(d, g, at, c, Rectangle::new(MARGIN, y, w - 2.0 * MARGIN, gh));
        }
        self.other_sensors(
            d,
            state,
            g,
            at,
            f,
            Rectangle::new(MARGIN, bottom + 6.0, w - 2.0 * MARGIN, OTHER_H - 10.0),
        );

        let keys = "keys: P freeze   Tab next page   E e-stop   F11 full screen   (an e-stop \
                    freezes the graphs by itself)";
        let keys = fit(&self.font, keys, w - 2.0 * MARGIN, 15.0);
        if !f.hide_keys {
            self.text(d, &keys, MARGIN, h - 26.0, 15.0, t.dim);
        }
        // No room for the little robot here: the graphs fill the page.
        Room {
            lane: None,
            corner: None,
        }
    }

    /// Where the ESP32's line comes from, and the WebSocket's state.
    fn esp32_words(&self, state: &PanelState, g: &Graphs, at: Instant) -> String {
        let link = match state.esp32.as_ref().map(|e| &e.link) {
            None => "no --esp32".to_owned(),
            Some(Esp32Link::Connecting(url)) => format!("reaching {url}"),
            Some(Esp32Link::Connected) => "WebSocket connected".to_owned(),
            Some(Esp32Link::Lost(why)) => format!("WebSocket lost: {why}"),
        };
        let line = match g.esp32_line(at) {
            Some(Esp32Line::Received) => "ESP32 line: what it got (its status lines)",
            Some(Esp32Line::UplinkOutput) => {
                "ESP32 line: what it drives (the uplink: brake, throttle), not what it got"
            }
            None => "ESP32 line: none yet",
        };
        let problem = state
            .esp32
            .as_ref()
            .and_then(|e| e.last_problem.as_deref())
            .map_or_else(String::new, |p| format!("; last unreadable: {p}"));
        format!("{line}   ({link}{problem})")
    }

    /// ego -> mux -> Pi wrote -> ESP32 got, each with its verdict.
    fn hop_chain(&self, d: &mut RaylibDrawHandle, g: &Graphs, at: Instant, f: &Frame<'_>, w: f32) {
        let t = self.theme;
        let hops = g.hops(at, f.stale_after);
        let arrow = 34.0;
        let n = Hop::ALL.len() as f32;
        let bw = (w - 2.0 * MARGIN - (n - 1.0) * arrow) / n;
        for (i, report) in hops.iter().enumerate() {
            let x = MARGIN + i as f32 * (bw + arrow);
            let r = Rectangle::new(x, CHAIN_Y, bw, CHAIN_H);
            d.draw_rectangle_rounded(r, t.style.corner(0.12), 6, t.section.rl());
            d.draw_rectangle_rounded_lines_ex(r, t.style.corner(0.12), 6, 1.0, t.glass_edge.rl());
            self.text(
                d,
                report.hop.label(),
                x + 10.0,
                CHAIN_Y + 8.0,
                18.0,
                t.caption,
            );
            let word = report.verdict.word();
            let p = t.pill(tone(&report.verdict));
            let ww = self.font.measure(word, 18.0);
            let px = x + bw - ww - 26.0;
            d.draw_rectangle_rounded(
                Rectangle::new(px, CHAIN_Y + 6.0, ww + 16.0, 26.0),
                t.style.corner(0.4),
                6,
                p.fill.rl(),
            );
            self.text(d, word, px + 8.0, CHAIN_Y + 9.0, 18.0, p.ink);
            let why = report.verdict.why();
            for (j, l) in wrap(&self.font, why, bw - 20.0, 14.0)
                .iter()
                .take(3)
                .enumerate()
            {
                self.text(
                    d,
                    l,
                    x + 10.0,
                    CHAIN_Y + 38.0 + 15.0 * j as f32,
                    14.0,
                    t.text,
                );
            }
            if i + 1 < hops.len() {
                let ax = x + bw + 6.0;
                let ay = CHAIN_Y + CHAIN_H / 2.0;
                d.draw_line_ex(
                    Vector2::new(ax, ay),
                    Vector2::new(ax + arrow - 14.0, ay),
                    3.0,
                    t.caption.rl(),
                );
                d.draw_triangle(
                    Vector2::new(ax + arrow - 4.0, ay),
                    Vector2::new(ax + arrow - 16.0, ay - 8.0),
                    Vector2::new(ax + arrow - 16.0, ay + 8.0),
                    t.caption.rl(),
                );
            }
        }
    }

    /// The counts that prove the wire: frames written, counted, lost and bad.
    fn strip(&self, d: &mut RaylibDrawHandle, g: &Graphs, at: Instant, w: f32) {
        let t = self.theme;
        let c = g.counts(at);
        let mut parts = Vec::new();
        parts.push(match c.pi {
            Some((written, errors, rise)) => {
                format!("Pi wrote {written} (+{rise} in 60 s), {errors} failed")
            }
            None => "Pi wrote: no link_frame".to_owned(),
        });
        parts.push(match c.esp32 {
            Some((total, rise)) => format!(
                "ESP32 counted {} (+{}), bad {} (+{}), skipped {} (+{}), repeats {}",
                total.frames,
                rise.frames,
                total.bad,
                rise.bad,
                total.skipped,
                rise.skipped,
                total.repeats
            ),
            None => "ESP32: no status lines".to_owned(),
        });
        parts.push(match c.uplink {
            Some(u) => format!(
                "uplink {} frames, lost {}, bad {}{}",
                u.frames,
                u.lost,
                u.bad,
                if u.fresh { "" } else { " (NOT FRESH)" }
            ),
            None => "uplink: no health".to_owned(),
        });
        parts.push(format!("status lines lost {}", c.lines_lost));
        let bad = c.restarted
            || c.lines_lost > 0
            || c.pi.is_some_and(|(_, e, _)| e > 0)
            || c.esp32.is_some_and(|(_, r)| r.bad + r.skipped > 0)
            || c.uplink.is_some_and(|u| !u.fresh);
        if c.restarted {
            parts.push("BOARD RESTARTED".to_owned());
        }
        let s = fit(&self.font, &parts.join("   |   "), w - 2.0 * MARGIN, 16.0);
        self.text(
            d,
            &s,
            MARGIN,
            STRIP_Y,
            16.0,
            if bad { t.warn } else { t.caption },
        );
    }

    /// x for a time in the window: 60 s ago at the left, `at` at the right.
    fn x_of(plot: Rectangle, at: Instant, when: Instant) -> f32 {
        let ago = at.saturating_duration_since(when).as_secs_f32();
        plot.x + plot.width * (1.0 - ago / WINDOW.as_secs_f32())
    }

    /// One graph: its two lines, the restarts, and the numbers.
    fn graph(&self, d: &mut RaylibDrawHandle, g: &Graphs, at: Instant, c: Channel, r: Rectangle) {
        let t = self.theme;
        let pi = g.line(c, Line::PiWrote, at);
        let esp = g.line(c, Line::Esp32, at);
        let plot = Rectangle::new(r.x + 96.0, r.y, r.width - 96.0 - STATS_W - 12.0, r.height);
        self.text(d, c.label(), r.x, r.y + 4.0, 17.0, t.caption);
        let unit = match c {
            Channel::Steering => "-1..1, + left",
            Channel::Brake => "0..1 demand",
            Channel::Throttle => "frame speed",
        };
        self.text(d, unit, r.x, r.y + 26.0, 13.0, t.dim);
        d.draw_rectangle_rec(plot, t.track.rl());
        let (lo, hi) = y_range(c, &[&pi, &esp]);
        let y_of = |v: f64| {
            let k = ((v - lo) / (hi - lo)) as f32;
            plot.y + plot.height * (1.0 - k)
        };
        // Zero, and the time marks.
        if lo < 0.0 && hi > 0.0 {
            d.draw_line_ex(
                Vector2::new(plot.x, y_of(0.0)),
                Vector2::new(plot.x + plot.width, y_of(0.0)),
                1.0,
                t.dim.rl(),
            );
        }
        for (secs, word) in [(60.0, "-60 s"), (30.0, "-30 s"), (0.0, "now")] {
            let x = plot.x + plot.width * (1.0 - secs / 60.0);
            d.draw_line_ex(
                Vector2::new(x, plot.y),
                Vector2::new(x, plot.y + plot.height),
                1.0,
                t.section.rl(),
            );
            if c == Channel::Throttle {
                let ww = self.font.measure(word, 12.0);
                let lx = (x - ww / 2.0).clamp(plot.x, plot.x + plot.width - ww);
                self.text(d, word, lx, plot.y + plot.height + 1.0, 12.0, t.dim);
            }
        }
        self.text(
            d,
            &format!("{hi:+.2}"),
            plot.x + 4.0,
            plot.y + 2.0,
            12.0,
            t.dim,
        );
        self.text(
            d,
            &format!("{lo:+.2}"),
            plot.x + 4.0,
            plot.y + plot.height - 14.0,
            12.0,
            t.dim,
        );
        for when in g.restarts(at) {
            let x = Self::x_of(plot, at, when);
            d.draw_line_ex(
                Vector2::new(x, plot.y),
                Vector2::new(x, plot.y + plot.height),
                2.0,
                t.bad.rl(),
            );
            self.text(d, "BOARD RESTARTED", x + 4.0, plot.y + 2.0, 12.0, t.bad);
        }
        // The Pi's: a line. The ESP32's: dots, on top.
        let point = |p: &Point| Vector2::new(Self::x_of(plot, at, p.at), y_of(p.value));
        for pair in pi.windows(2) {
            if !pair[1].gap_before {
                d.draw_line_ex(point(&pair[0]), point(&pair[1]), 2.0, t.text.rl());
            }
        }
        for p in &esp {
            d.draw_circle_v(point(p), 2.5, t.accent.rl());
        }
        for (line, word, ink) in [(&pi, "Pi", t.text), (&esp, "ESP32", t.accent)] {
            if let Some(p) = line.last() {
                let v = point(p);
                self.text(d, word, (v.x - 46.0).max(plot.x), v.y - 16.0, 13.0, ink);
            }
        }
        if pi.is_empty() && esp.is_empty() {
            self.text(
                d,
                "no data",
                plot.x + plot.width / 2.0 - 30.0,
                plot.y + plot.height / 2.0 - 9.0,
                17.0,
                t.dim,
            );
        }

        // The numbers.
        let sx = plot.x + plot.width + 12.0;
        let mut y = r.y;
        for (line, word, ink) in [(&pi, "PI WROTE", t.text), (&esp, "ESP32", t.accent)] {
            self.text(d, word, sx, y, 14.0, ink);
            y += 16.0;
            let s = Stats::of(line).map_or_else(
                || "-".to_owned(),
                |s| {
                    format!(
                        "now {:+.2}  avg {:+.2}\nlow {:+.2}  high {:+.2}",
                        s.now, s.avg, s.low, s.high
                    )
                },
            );
            for l in s.lines() {
                self.text(d, l, sx, y, 15.0, t.caption);
                y += 17.0;
            }
            y += 4.0;
        }
    }

    /// The sensors already on the panel: the IMU's turn rate as a small graph, the IMU and
    /// the GPS as words.
    fn other_sensors(
        &self,
        d: &mut RaylibDrawHandle,
        state: &PanelState,
        g: &Graphs,
        at: Instant,
        f: &Frame<'_>,
        r: Rectangle,
    ) {
        let t = self.theme;
        self.text(d, "OTHER SENSORS", r.x, r.y, 15.0, t.caption);
        let half = (r.width - 24.0) / 2.0;
        let plot = Rectangle::new(r.x + 96.0, r.y + 20.0, half - 96.0, r.height - 22.0);
        self.text(d, "IMU yaw", r.x, r.y + 24.0, 15.0, t.caption);
        self.text(d, "deg/s", r.x, r.y + 42.0, 13.0, t.dim);
        d.draw_rectangle_rec(plot, t.track.rl());
        let imu = g.imu_line(at);
        let (lo, hi) = imu.iter().fold((-10.0_f64, 10.0_f64), |(lo, hi), p| {
            (lo.min(p.value), hi.max(p.value))
        });
        let y_of = |v: f64| plot.y + plot.height * (1.0 - ((v - lo) / (hi - lo)) as f32);
        for pair in imu.windows(2) {
            if !pair[1].gap_before {
                d.draw_line_ex(
                    Vector2::new(Self::x_of(plot, at, pair[0].at), y_of(pair[0].value)),
                    Vector2::new(Self::x_of(plot, at, pair[1].at), y_of(pair[1].value)),
                    1.5,
                    t.text.rl(),
                );
            }
        }
        if let Some(s) = Stats::of(&imu) {
            let words = format!(
                "now {:+.1}  avg {:+.1}  low {:+.1}  high {:+.1}",
                s.now, s.avg, s.low, s.high
            );
            self.text(
                d,
                &fit(&self.font, &words, plot.width - 8.0, 12.0),
                plot.x + 4.0,
                plot.y + 2.0,
                12.0,
                t.dim,
            );
        }
        // The words: from each sensor's own topic, as on the DRIVE page (live, not frozen).
        let x = r.x + half + 24.0;
        let mut y = r.y + 20.0;
        for row in [Row::Imu, Row::Gps] {
            let health = state.health(row, f.now);
            let (word, ink) = match health {
                Health::Ok(_) => ("OK", t.good),
                Health::Stale(_) => ("STALE", t.warn),
                Health::Never => ("NEVER", t.dim),
            };
            self.text(d, row.label(), x, y, 16.0, t.text);
            self.text(d, word, x + 60.0, y, 16.0, ink);
            let detail = match health {
                Health::Never => "not on this computer's topics".to_owned(),
                _ => state.detail(row, f.now, None),
            };
            let detail = fit(&self.font, &detail, half - 150.0, 15.0);
            self.text(d, &detail, x + 140.0, y + 1.0, 15.0, t.caption);
            y += 26.0;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_y_range_widens_to_fit() {
        let now = Instant::now();
        let p = |v| Point {
            at: now,
            value: v,
            gap_before: false,
        };
        assert_eq!(y_range(Channel::Steering, &[]), (-1.0, 1.0));
        assert_eq!(y_range(Channel::Brake, &[&[p(1.2)]]), (0.0, 1.2));
        assert_eq!(
            y_range(Channel::Throttle, &[&[p(-0.1)], &[p(0.5)]]),
            (-0.1, 1.0)
        );
    }

    #[test]
    fn verdicts_have_their_own_tones() {
        assert_eq!(tone(&Verdict::Ok(String::new())), Tone::Go);
        assert_eq!(tone(&Verdict::Different(String::new())), Tone::Stop);
        assert_eq!(tone(&Verdict::NotTested(String::new())), Tone::Off);
    }
}
