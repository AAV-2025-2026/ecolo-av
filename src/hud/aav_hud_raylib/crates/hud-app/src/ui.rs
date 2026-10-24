//! The driving screen, drawn with raylib.
//!
//! Everything is laid out on a 1280 x 720 canvas, then scaled to the window and centred,
//! so the screen looks the same at any size. The layout:
//!
//! ```text
//! +--------------------------------------------------------------------+
//! | MODE | ARMED | GEAR | E-STOP | BATTERY | FAULTS               DEMO |
//! +----------------+--------------------------+------------------------+
//! | SPEED          | CAMERA                   |  [  E-STOP button  ]   |
//! |   12 km/h      | (STOP SIGN banner)       |  sent / failed         |
//! |                | (SIMULATED banner)       |                        |
//! +----------------+--------------------------+------------------------+
//! | (icon) GO      | TOPICS                   | GPS                    |
//! | all REAL       |  /vehicle/status  SIM OK |  RTK FIXED             |
//! +----------------+  /sensors/gps/fix  STALE |  lat, lon, accuracy    |
//! | STEERING  ---  |                          |                        |
//! | THROTTLE  ===  |                          |                        |
//! | BRAKE     ===  |                          |                        |
//! +--------------------------------------------------------------------+
//! ```
//!
//! The GO / STOP panel answers "may the car move?" for the safety drivers: a colour, an
//! icon, a word and the one main reason (hud_core::gate). The orange SIMULATED / BENCH /
//! REPLAY banner shows whenever `/system/source` says any data isn't from the real car;
//! each topic it names gets a REAL / SIM tag under TOPICS.

use std::time::Instant;

use hud_core::{
    config::Topic,
    format,
    gate::{Light, Verdict},
    gps::FixKind,
    health::Health,
    origin::Origin,
    picture::Picture,
    state::{Alarm, EstopReport, HudState},
    vehicle::VehicleStatus,
};
use raylib::prelude::*;

/// The canvas everything is drawn on, before scaling.
const CANVAS_W: f32 = 1280.0;
const CANVAS_H: f32 = 720.0;

const BACKGROUND: Color = Color::new(12, 12, 16, 255);
const PANEL: Color = Color::new(30, 32, 40, 255);
const CAPTION: Color = Color::new(160, 165, 180, 255);
const TEXT: Color = Color::new(245, 245, 245, 255);
const DIM: Color = Color::new(110, 112, 120, 255);
const GOOD: Color = Color::new(60, 200, 90, 255);
const WARN: Color = Color::new(245, 180, 40, 255);
const BAD: Color = Color::new(230, 45, 45, 255);
const ESTOP_RED: Color = Color::new(200, 20, 20, 255);
const ESTOP_HOVER: Color = Color::new(240, 40, 40, 255);
/// The not-the-real-car banner, and the tags of topics that aren't real.
const NOT_REAL: Color = Color::new(255, 140, 0, 255);

/// The steering bar's ends, in degrees each way.
const STEERING_RANGE_DEG: f32 = 30.0;

/// Fonts tried in order; raylib's own small pixel font if none is there.
const FONT_FILES: [&str; 4] = [
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf", // macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   // macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", // Ubuntu, Raspberry Pi OS
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", // Fedora, AlmaLinux
];
/// The size glyphs are rendered at; text is scaled down from it, so keep it large.
const FONT_LOAD_SIZE: i32 = 128;

/// Where each part of the screen is, on the canvas.
mod area {
    /// (x, y, width, height)
    pub type Area = (f32, f32, f32, f32);
    pub const STRIP: Area = (8.0, 8.0, 1264.0, 76.0);
    pub const SPEED: Area = (8.0, 94.0, 430.0, 300.0);
    pub const GATE: Area = (8.0, 404.0, 430.0, 176.0);
    pub const CONTROLS: Area = (8.0, 590.0, 430.0, 122.0);
    pub const CAMERA: Area = (448.0, 94.0, 504.0, 300.0);
    pub const TOPICS: Area = (448.0, 404.0, 504.0, 308.0);
    pub const ESTOP: Area = (962.0, 94.0, 310.0, 184.0);
    pub const ESTOP_NOTE: Area = (962.0, 284.0, 310.0, 110.0);
    pub const GPS: Area = (962.0, 404.0, 310.0, 308.0);
}

/// raylib's font handle: one loaded from a file, or its built-in one.
enum HudFont {
    File(Font),
    BuiltIn(WeakFont),
}

impl HudFont {
    fn measure(&self, text: &str, size: f32) -> f32 {
        let spacing = size / 20.0;
        match self {
            Self::File(f) => f.measure_text(text, size, spacing).x,
            Self::BuiltIn(f) => f.measure_text(text, size, spacing).x,
        }
    }
}

impl AsRef<raylib::ffi::Font> for HudFont {
    fn as_ref(&self) -> &raylib::ffi::Font {
        match self {
            Self::File(f) => f.as_ref(),
            Self::BuiltIn(f) => f.as_ref(),
        }
    }
}

/// The camera picture on the graphics card.
struct CameraTexture {
    texture: Texture2D,
    width: u32,
    height: u32,
}

/// The screen: its font and the camera's texture.
pub struct Ui {
    font: HudFont,
    camera: Option<CameraTexture>,
}

impl Ui {
    /// Loads the font. Needs the window open.
    pub fn new(rl: &mut RaylibHandle, thread: &RaylibThread) -> Self {
        let loaded = FONT_FILES
            .iter()
            .filter(|path| std::path::Path::new(path).exists())
            .find_map(|path| rl.load_font_ex(thread, path, FONT_LOAD_SIZE, None).ok());
        let font = match loaded {
            Some(f) => {
                f.texture()
                    .set_texture_filter(thread, TextureFilter::TEXTURE_FILTER_BILINEAR);
                HudFont::File(f)
            }
            None => HudFont::BuiltIn(rl.get_font_default()),
        };
        Self { font, camera: None }
    }

    /// Puts a new camera picture on the graphics card.
    pub fn upload(
        &mut self,
        rl: &mut RaylibHandle,
        thread: &RaylibThread,
        picture: &Picture,
    ) -> anyhow::Result<()> {
        let same_size = self
            .camera
            .as_ref()
            .is_some_and(|c| c.width == picture.width && c.height == picture.height);
        if !same_size {
            let (w, h) = (to_i32(picture.width)?, to_i32(picture.height)?);
            // gen_image_color makes RGBA8 pixels, the layout Picture has.
            let image = Image::gen_image_color(w, h, Color::BLACK);
            let texture = rl.load_texture_from_image(thread, &image)?;
            texture.set_texture_filter(thread, TextureFilter::TEXTURE_FILTER_BILINEAR);
            self.camera = Some(CameraTexture {
                texture,
                width: picture.width,
                height: picture.height,
            });
        }
        if let Some(c) = self.camera.as_mut() {
            c.texture.update_texture(&picture.rgba)?;
        }
        Ok(())
    }

    /// The e-stop button's place in the window, in window pixels.
    pub fn estop_button(&self, window_w: i32, window_h: i32) -> Rectangle {
        Scale::new(window_w, window_h).rect(area::ESTOP)
    }

    /// Draws one frame. `hover`: the pointer is over the e-stop button.
    pub fn draw(
        &self,
        d: &mut RaylibDrawHandle,
        state: &HudState,
        now: Instant,
        source: &str,
        hover: bool,
    ) {
        let scale = Scale::new(d.get_screen_width(), d.get_screen_height());
        let blink = (d.get_time() * 2.0).fract() < 0.5;
        d.clear_background(BACKGROUND);
        let mut c = Canvas {
            d,
            font: &self.font,
            scale,
        };
        let vehicle = Fresh::of(state, Topic::VehicleStatus, now, state.vehicle);
        strip(&mut c, state, &vehicle, now, source);
        speed(&mut c, &vehicle);
        gate(&mut c, &state.verdict(now));
        controls(&mut c, &vehicle);
        camera(&mut c, state, now, self.camera.as_ref(), blink);
        topics(&mut c, state, now);
        estop(&mut c, state, &vehicle, hover);
        gps(&mut c, state, now);
    }
}

fn to_i32(n: u32) -> anyhow::Result<i32> {
    Ok(i32::try_from(n)?)
}

/// The newest message of one topic, and whether it's fresh.
struct Fresh<T> {
    value: Option<T>,
    health: Health,
}

impl<T: Copy> Fresh<T> {
    fn of(state: &HudState, topic: Topic, now: Instant, value: Option<T>) -> Self {
        Self {
            value,
            health: state.health(topic, now),
        }
    }

    /// The text colour: normal when fresh, grey when old.
    fn colour(&self, fresh: Color) -> Color {
        if self.health.is_ok() {
            fresh
        } else {
            DIM
        }
    }
}

/// From the 1280 x 720 canvas to the window: one scale, and the offset that centres it.
#[derive(Clone, Copy)]
struct Scale {
    k: f32,
    x0: f32,
    y0: f32,
}

impl Scale {
    fn new(window_w: i32, window_h: i32) -> Self {
        let (w, h) = (window_w as f32, window_h as f32);
        let k = (w / CANVAS_W).min(h / CANVAS_H).max(0.01);
        Self {
            k,
            x0: (w - CANVAS_W * k) / 2.0,
            y0: (h - CANVAS_H * k) / 2.0,
        }
    }

    fn rect(self, (x, y, w, h): area::Area) -> Rectangle {
        Rectangle::new(
            self.x0 + x * self.k,
            self.y0 + y * self.k,
            w * self.k,
            h * self.k,
        )
    }
}

/// Drawing in canvas units.
struct Canvas<'a, 'b> {
    d: &'a mut RaylibDrawHandle<'b>,
    font: &'a HudFont,
    scale: Scale,
}

impl Canvas<'_, '_> {
    fn fill(&mut self, a: area::Area, colour: Color) {
        let r = self.scale.rect(a);
        self.d.draw_rectangle_rounded(r, 0.06, 8, colour);
    }

    fn outline(&mut self, a: area::Area, thick: f32, colour: Color) {
        let r = self.scale.rect(a);
        self.d
            .draw_rectangle_lines_ex(r, thick * self.scale.k, colour);
    }

    fn bar(&mut self, a: area::Area, colour: Color) {
        let r = self.scale.rect(a);
        self.d.draw_rectangle_rec(r, colour);
    }

    fn width(&self, text: &str, size: f32) -> f32 {
        self.font.measure(text, size * self.scale.k) / self.scale.k
    }

    fn text(&mut self, x: f32, y: f32, size: f32, text: &str, colour: Color) {
        let s = self.scale;
        let pos = Vector2::new(s.x0 + x * s.k, s.y0 + y * s.k);
        let px = size * s.k;
        self.d
            .draw_text_ex(self.font, text, pos, px, px / 20.0, colour);
    }

    fn centred(&mut self, cx: f32, y: f32, size: f32, text: &str, colour: Color) {
        let w = self.width(text, size);
        self.text(cx - w / 2.0, y, size, text, colour);
    }

    fn right(&mut self, x_right: f32, y: f32, size: f32, text: &str, colour: Color) {
        let w = self.width(text, size);
        self.text(x_right - w, y, size, text, colour);
    }

    /// A panel: its background and its caption.
    fn panel(&mut self, a: area::Area, caption: &str) {
        self.fill(a, PANEL);
        self.text(a.0 + 14.0, a.1 + 10.0, 18.0, caption, CAPTION);
    }

    /// The light's icon, centred at `centre` (canvas units), radius `r`: a tick in a
    /// circle (GO), a pause sign (WAIT), a stop sign (STOP), a question mark (no gate).
    fn icon(&mut self, light: Light, centre: (f32, f32), r: f32, fill: Color, ink: Color) {
        let s = self.scale;
        let at = |x: f32, y: f32| Vector2::new(s.x0 + x * s.k, s.y0 + y * s.k);
        let (cx, cy) = centre;
        let (k, c) = (s.k, at(cx, cy));
        if light == Light::Stop {
            // An octagon, flat on top, as a road's stop sign: a rim, and a bar across.
            self.d.draw_poly(c, 8, r * k, 22.5, ink);
            self.d.draw_poly(c, 8, (r - 6.0) * k, 22.5, fill);
        } else {
            self.d.draw_circle_v(c, r * k, ink);
            self.d.draw_circle_v(c, (r - 6.0) * k, fill);
        }
        let rect = |x: f32, y: f32, w: f32, h: f32| {
            Rectangle::new(
                s.x0 + (cx + x * r) * k,
                s.y0 + (cy + y * r) * k,
                w * r * k,
                h * r * k,
            )
        };
        match light {
            Light::Stop => self.d.draw_rectangle_rec(rect(-0.6, -0.16, 1.2, 0.32), ink),
            Light::Go => {
                let thick = r * 0.2 * k;
                let (a, b, e) = (
                    at(cx - r * 0.45, cy + r * 0.02),
                    at(cx - r * 0.12, cy + r * 0.36),
                    at(cx + r * 0.48, cy - r * 0.34),
                );
                self.d.draw_line_ex(a, b, thick, ink);
                self.d.draw_line_ex(b, e, thick, ink);
                self.d.draw_circle_v(b, thick / 2.0, ink);
            }
            Light::Wait => {
                self.d
                    .draw_rectangle_rec(rect(-0.32, -0.42, 0.2, 0.84), ink);
                self.d.draw_rectangle_rec(rect(0.12, -0.42, 0.2, 0.84), ink);
            }
            Light::Unknown => self.centred(cx, cy - r * 0.55, r * 1.1, "?", ink),
        }
    }

    /// Text that fits in `max_w`: shrinks it down to `min_size`, no smaller.
    fn fitted(&mut self, x: f32, y: f32, size: f32, max_w: f32, text: &str, colour: Color) {
        let mut s = size;
        while s > 12.0 && self.width(text, s) > max_w {
            s -= 2.0;
        }
        self.text(x, y, s, text, colour);
    }
}

fn health_colour(h: Health) -> Color {
    match h {
        Health::Ok(_) => GOOD,
        Health::Stale(_) => WARN,
        Health::Never => BAD,
    }
}

/// The top strip: mode, armed, gear, e-stop, battery, faults, and the source.
fn strip(
    c: &mut Canvas,
    state: &HudState,
    vehicle: &Fresh<VehicleStatus>,
    now: Instant,
    source: &str,
) {
    let (x, y, _, h) = area::STRIP;
    c.fill(area::STRIP, PANEL);
    let v = vehicle.value;
    let dash = || ("--".to_owned(), DIM);
    let mode = v.map_or_else(dash, |v| (v.mode.to_string(), TEXT));
    let armed = v.map_or_else(dash, |v| {
        if v.armed {
            ("ARMED".into(), GOOD)
        } else {
            ("DISARMED".into(), WARN)
        }
    });
    let gear = v.map_or_else(dash, |v| (v.gear().letter().into(), TEXT));
    let estop = v.map_or_else(dash, |v| {
        if v.estop_active {
            ("ON".into(), BAD)
        } else {
            ("off".into(), GOOD)
        }
    });
    let battery = Fresh::of(state, Topic::Battery, now, state.battery);
    let charge = battery.value.map_or_else(dash, |b| {
        let text = match (b.percent, b.voltage) {
            (Some(p), _) => format!("{p:.0} %"),
            (None, Some(v)) => format!("{v:.1} V"),
            (None, None) => "?".into(),
        };
        let low = b.percent.is_some_and(|p| p < 20.0);
        (text, battery.colour(if low { BAD } else { TEXT }))
    });
    let faults = v.map_or_else(dash, |v| {
        if v.faults.is_empty() {
            ("none".into(), GOOD)
        } else {
            (v.faults.to_string(), BAD)
        }
    });
    let cells: [(&str, (String, Color), f32); 6] = [
        ("MODE", mode, 190.0),
        ("COMPUTER", armed, 180.0),
        ("GEAR", gear, 90.0),
        ("E-STOP", estop, 120.0),
        ("BATTERY", charge, 140.0),
        ("FAULTS", faults, 420.0),
    ];
    let mut cx = x + 16.0;
    for (caption, (value, colour), w) in cells {
        // Old news is grey, whatever it says.
        let colour = if caption == "BATTERY" {
            colour
        } else {
            vehicle.colour(colour)
        };
        c.text(cx, y + 8.0, 16.0, caption, CAPTION);
        c.fitted(cx, y + 30.0, 34.0, w - 14.0, &value, colour);
        cx += w;
    }
    let tag = match vehicle.health {
        Health::Ok(_) => source.to_owned(),
        Health::Stale(age) => format!("{source}: status {}", format::age(age)),
        Health::Never => format!("{source}: no status"),
    };
    let tag_colour = if vehicle.health.is_ok() {
        CAPTION
    } else {
        WARN
    };
    c.right(
        area::STRIP.0 + area::STRIP.2 - 14.0,
        y + h / 2.0 - 10.0,
        20.0,
        &tag,
        tag_colour,
    );
}

/// The big speed.
fn speed(c: &mut Canvas, vehicle: &Fresh<VehicleStatus>) {
    let a = area::SPEED;
    c.panel(a, "SPEED");
    let cx = a.0 + a.2 / 2.0;
    match vehicle.value {
        Some(v) => {
            let colour = vehicle.colour(TEXT);
            c.centred(
                cx,
                a.1 + 50.0,
                170.0,
                &format::speed_km_per_hour(v.speed),
                colour,
            );
            c.centred(cx, a.1 + 226.0, 30.0, "km/h", CAPTION);
        }
        None => c.centred(cx, a.1 + 50.0, 170.0, "--", DIM),
    }
    if let Health::Stale(age) = vehicle.health {
        c.centred(
            cx,
            a.1 + 262.0,
            24.0,
            &format!("OLD: {}", format::age(age)),
            WARN,
        );
    } else if vehicle.health == Health::Never {
        c.centred(cx, a.1 + 262.0, 24.0, "no vehicle status", BAD);
    }
}

/// May the car move? The whole panel in the light's colour, its icon, the word, the one
/// main reason, and what a person can do (hud_core::gate).
fn gate(c: &mut Canvas, verdict: &Verdict) {
    let a = area::GATE;
    let (fill, ink) = match verdict.light {
        Light::Go => (GOOD, Color::BLACK),
        Light::Wait => (WARN, Color::BLACK),
        Light::Stop => (ESTOP_RED, TEXT),
        Light::Unknown => (PANEL, CAPTION),
    };
    c.fill(a, fill);
    let r = 52.0;
    let centre = (a.0 + 22.0 + r, a.1 + a.3 / 2.0);
    c.icon(verdict.light, centre, r, fill, ink);
    let x = a.0 + 2.0 * r + 44.0;
    let w = a.0 + a.2 - 14.0 - x;
    c.fitted(x, a.1 + 14.0, 64.0, w, verdict.headline, ink);
    c.fitted(x, a.1 + 88.0, 30.0, w, &verdict.reason, ink);
    c.fitted(x, a.1 + 132.0, 20.0, w, verdict.hint, ink);
}

/// Steering, throttle and brake, as bars: one row each.
fn controls(c: &mut Canvas, vehicle: &Fresh<VehicleStatus>) {
    let a = area::CONTROLS;
    c.fill(a, PANEL);
    let (x, right) = (a.0 + 16.0, a.0 + a.2 - 16.0);
    let (bar_x, bar_w) = (x + 130.0, right - 96.0 - (x + 130.0));
    let v = vehicle.value;
    let steer_deg = v.map(|v| v.steering_angle.to_degrees());
    let rows = ["STEERING", "THROTTLE", "BRAKE"];
    for (i, label) in rows.into_iter().enumerate() {
        let y = a.1 + 12.0 + i as f32 * 36.0;
        c.text(x, y + 4.0, 18.0, label, CAPTION);
        c.bar((bar_x, y + 2.0, bar_w, 26.0), BACKGROUND);
        let value = match (i, v) {
            (_, None) => "--".to_owned(),
            (0, Some(_)) => format::steering(steer_deg.unwrap_or(0.0)),
            (1, Some(v)) => format!("{:.0} %", v.throttle.get() * 100.0),
            (_, Some(v)) => format!("{:.0} %", v.brake.get() * 100.0),
        };
        c.right(right, y + 3.0, 20.0, &value, vehicle.colour(TEXT));
        let Some(v) = v else { continue };
        let fill = vehicle.colour(match i {
            0 => TEXT,
            1 => GOOD,
            _ => BAD,
        });
        if i == 0 {
            // Centre = straight; left of centre = turning left (positive, REP-103).
            let k = (steer_deg.unwrap_or(0.0) / STEERING_RANGE_DEG).clamp(-1.0, 1.0);
            let mid = bar_x + bar_w / 2.0;
            c.bar((mid - 1.0, y, 2.0, 30.0), CAPTION);
            let marker = mid - k * (bar_w / 2.0 - 5.0);
            c.bar((marker - 5.0, y + 2.0, 10.0, 26.0), fill);
        } else {
            let level = if i == 1 { v.throttle } else { v.brake };
            c.bar((bar_x, y + 2.0, bar_w * level.get(), 26.0), fill);
        }
    }
}

/// The camera picture, and the stop-sign banner over it.
fn camera(
    c: &mut Canvas,
    state: &HudState,
    now: Instant,
    texture: Option<&CameraTexture>,
    blink: bool,
) {
    let a = area::CAMERA;
    let topic = state.config.topic(Topic::Camera);
    c.panel(a, &format!("CAMERA  {topic}"));
    let inner = (a.0 + 10.0, a.1 + 36.0, a.2 - 20.0, a.3 - 46.0);
    c.bar(inner, Color::BLACK);
    let health = state.health(Topic::Camera, now);
    if let Some(t) = texture {
        // Fit the picture in the panel, keeping its shape.
        let (tw, th) = (t.width as f32, t.height as f32);
        let k = (inner.2 / tw).min(inner.3 / th);
        let (w, h) = (tw * k, th * k);
        let dest = (
            inner.0 + (inner.2 - w) / 2.0,
            inner.1 + (inner.3 - h) / 2.0,
            w,
            h,
        );
        let src = Rectangle::new(0.0, 0.0, tw, th);
        let tint = if health.is_ok() { Color::WHITE } else { DIM };
        let dest = c.scale.rect(dest);
        c.d.draw_texture_pro(&t.texture, src, dest, Vector2::zero(), 0.0, tint);
    }
    let cx = inner.0 + inner.2 / 2.0;
    let cy = inner.1 + inner.3 / 2.0;
    match health {
        Health::Never => c.centred(cx, cy - 14.0, 28.0, "NO PICTURE YET", BAD),
        Health::Stale(age) => {
            let msg = format!("CAMERA STOPPED {}", format::age(age));
            c.centred(cx, cy - 14.0, 28.0, &msg, WARN);
        }
        Health::Ok(_) => {}
    }
    // Not the real car: a big orange band along the bottom, always on.
    let banner_h = 70.0;
    let not_real = state.origins.banner();
    if let Some(words) = &not_real {
        let band = (inner.0, inner.1 + inner.3 - banner_h, inner.2, banner_h);
        c.bar(band, NOT_REAL);
        c.centred(cx, band.1 + 8.0, 52.0, words, Color::BLACK);
    }
    let lift = if not_real.is_some() { banner_h } else { 0.0 };
    if let Some(why) = &state.picture_problem {
        c.fitted(
            inner.0 + 8.0,
            inner.1 + inner.3 - 30.0 - lift,
            18.0,
            inner.2 - 16.0,
            why,
            WARN,
        );
    }
    let mut top = inner.1;
    if state.stop_sign && state.health(Topic::StopSign, now).is_ok() {
        let banner = (inner.0, inner.1, inner.2, 84.0);
        c.bar(banner, if blink { BAD } else { ESTOP_RED });
        c.centred(cx, inner.1 + 14.0, 56.0, "STOP SIGN", TEXT);
        top += 84.0;
    }
    // The sensor watchdog: what failed, and whether Nav2 and the AI slot stopped for it.
    if let Some(alarm) = state.sensor_alarm(now) {
        let (text, colour) = match &alarm {
            Alarm::Stop(t) => (t, if blink { BAD } else { ESTOP_RED }),
            Alarm::Warn(t) => (t, WARN),
        };
        c.bar((inner.0, top, inner.2, 40.0), colour);
        c.fitted(
            inner.0 + 8.0,
            top + 9.0,
            22.0,
            inner.2 - 16.0,
            text,
            Color::BLACK,
        );
    }
}

/// Every topic the HUD listens to: OK / STALE / NEVER, how long ago, and where its data
/// comes from (REAL, SIM...) when `/system/source` says.
fn topics(c: &mut Canvas, state: &HudState, now: Instant) {
    let a = area::TOPICS;
    c.panel(a, "TOPICS");
    let (x, right) = (a.0 + 16.0, a.0 + a.2 - 16.0);
    for (i, (name, health)) in state.topic_health(now).enumerate() {
        let y = a.1 + 42.0 + i as f32 * 43.0;
        let status = format::health(health);
        let status_w = c.width(&status, 24.0);
        c.right(right, y, 24.0, &status, health_colour(health));
        let mut name_right = right - status_w - 16.0;
        if let Some(origin) = state.origins.of_topic(name) {
            let tag = origin.tag();
            let colour = if origin == Origin::Real {
                CAPTION
            } else {
                NOT_REAL
            };
            c.right(name_right, y + 2.0, 20.0, tag, colour);
            name_right -= c.width(tag, 20.0) + 12.0;
        }
        c.fitted(x, y, 24.0, name_right - x, name, TEXT);
    }
}

/// The e-stop button, and what came of the last press.
fn estop(c: &mut Canvas, state: &HudState, vehicle: &Fresh<VehicleStatus>, hover: bool) {
    let a = area::ESTOP;
    c.fill(a, if hover { ESTOP_HOVER } else { ESTOP_RED });
    c.outline(a, 4.0, TEXT);
    let cx = a.0 + a.2 / 2.0;
    c.centred(cx, a.1 + 40.0, 72.0, "E-STOP", TEXT);
    c.centred(cx, a.1 + 128.0, 20.0, "tap to stop the car", TEXT);

    let n = area::ESTOP_NOTE;
    let car_stopped = vehicle.health.is_ok() && vehicle.value.is_some_and(|v| v.estop_active);
    let estop_topic = state.config.topic(Topic::Estop);
    let lines: Vec<(String, Color)> = match state.estop {
        None if car_stopped => vec![("The car says: E-STOP ON".into(), BAD)],
        None => vec![("Not pressed".into(), DIM)],
        Some(EstopReport::Sent { subscribers: 0 }) => vec![
            ("E-STOP FAILED".into(), BAD),
            (format!("nothing listens on {estop_topic}"), BAD),
            ("Press the car's red button!".into(), BAD),
        ],
        Some(EstopReport::Sent { subscribers }) => vec![
            (format!("SENT to {subscribers} node(s)"), GOOD),
            if car_stopped {
                ("The car says: E-STOP ON".into(), BAD)
            } else {
                ("waiting for the car...".into(), WARN)
            },
            ("Clear it from a laptop".into(), CAPTION),
        ],
        Some(EstopReport::Failed) => vec![
            ("E-STOP FAILED: not sent".into(), BAD),
            ("Press the car's red button!".into(), BAD),
        ],
    };
    for (i, (line, colour)) in lines.iter().enumerate() {
        let y = n.1 + 8.0 + i as f32 * 32.0;
        c.fitted(n.0 + 8.0, y, 24.0, n.2 - 16.0, line, *colour);
    }
}

/// Is there GPS data? The answer first, big; then the numbers.
fn gps(c: &mut Canvas, state: &HudState, now: Instant) {
    let a = area::GPS;
    let topic = state.config.topic(Topic::Gps);
    c.panel(a, &format!("GPS  {topic}"));
    let (x, w) = (a.0 + 16.0, a.2 - 32.0);
    let health = state.health(Topic::Gps, now);
    let fix = state.gps;
    let (headline, colour) = match (health, fix) {
        (Health::Never, _) | (_, None) => ("NO GPS DATA".to_owned(), BAD),
        (Health::Stale(_), _) => ("GPS SILENT".to_owned(), WARN),
        (Health::Ok(_), Some(f)) => (f.kind.to_string(), kind_colour(f.kind)),
    };
    c.fitted(x, a.1 + 40.0, 44.0, w, &headline, colour);

    let dim_if_old = |col: Color| if health.is_ok() { col } else { DIM };
    let mut rows: Vec<(&str, String)> = Vec::new();
    if let Some(f) = fix {
        if !health.is_ok() {
            rows.push(("LAST", f.kind.to_string()));
        }
        match f.position {
            Some((lat, lon)) => {
                rows.push(("LAT", format::latitude(lat)));
                rows.push(("LON", format::longitude(lon)));
            }
            None => rows.push(("POS", "none".into())),
        }
        let acc = f
            .horizontal_sigma
            .map_or("not given".into(), |s| format!("+/- {}", format::metres(s)));
        rows.push(("ACC", acc));
    }
    let age = health.age().map_or("never".into(), format::age);
    rows.push(("AGE", age));
    for (i, (label, value)) in rows.iter().enumerate() {
        let y = a.1 + 104.0 + i as f32 * 38.0;
        c.text(x, y, 22.0, label, CAPTION);
        let colour = if *label == "AGE" {
            health_colour(health)
        } else {
            dim_if_old(TEXT)
        };
        c.fitted(x + 70.0, y, 24.0, w - 70.0, value, colour);
    }
}

fn kind_colour(kind: FixKind) -> Color {
    match kind {
        FixKind::NoFix => BAD,
        FixKind::Unknown | FixKind::Fix2d | FixKind::RtkFloat => WARN,
        FixKind::Fix3d | FixKind::Dgps | FixKind::RtkFixed => GOOD,
    }
}
