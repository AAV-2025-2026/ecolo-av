//! The screens' colours: one [`Theme`] holds every colour the HUD and the map window
//! draw with, so the drawing code has no colour of its own.
//!
//! | Theme | When | Where its colours come from |
//! |---|---|---|
//! | `mocha` (the default) | night, and a dark cabin | Catppuccin Mocha |
//! | `latte` | daytime | Catppuccin Latte |
//! | `calm` | not yet: a copy of `mocha` | Ben's Carleton theme, to come |
//!
//! Catppuccin (<https://catppuccin.com>, MIT licence) gives the base colours. The
//! status colours keep their meaning in every theme: green GO / OK, amber WAIT /
//! warning, red STOP / e-stop. Where a Catppuccin colour is too light to read on its
//! background (Latte's green and yellow on white), it is darkened, and the unit tests
//! check every pair against WCAG's contrast ratios.
//!
//! `config/hud.yaml` and `config/map.yaml` choose one: `theme: mocha`.

use std::{fmt, str::FromStr};

use serde::Deserialize;
use thiserror::Error;

/// A colour: red, green, blue and alpha (0 = see-through, 255 = solid), 0-255 each.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Rgba {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Rgba {
    /// Solid black and white, for mixing.
    pub const BLACK: Rgba = Rgba::hex(0x000000);
    pub const WHITE: Rgba = Rgba::hex(0xffffff);

    /// A solid colour from its web code: `Rgba::hex(0x1e1e2e)` is `#1e1e2e`.
    pub const fn hex(rgb: u32) -> Self {
        Self {
            r: ((rgb >> 16) & 0xff) as u8,
            g: ((rgb >> 8) & 0xff) as u8,
            b: (rgb & 0xff) as u8,
            a: 255,
        }
    }

    /// The same colour, `alpha` see-through (0-255).
    pub const fn alpha(self, alpha: u8) -> Self {
        Self { a: alpha, ..self }
    }

    /// `percent` of the way from this colour to `other` (0 = this, 100 = other). The
    /// alpha is this colour's.
    pub const fn mix(self, other: Rgba, percent: u8) -> Self {
        const fn channel(a: u8, b: u8, t: u16) -> u8 {
            let t = if t > 100 { 100 } else { t };
            ((a as u16 * (100 - t) + b as u16 * t + 50) / 100) as u8
        }
        let t = percent as u16;
        Self {
            r: channel(self.r, other.r, t),
            g: channel(self.g, other.g, t),
            b: channel(self.b, other.b, t),
            a: self.a,
        }
    }

    /// What this colour looks like painted over a solid `back`: its alpha blended away.
    pub fn over(self, back: Rgba) -> Rgba {
        let k = f64::from(self.a) / 255.0;
        let blend = |f: u8, b: u8| (f64::from(f) * k + f64::from(b) * (1.0 - k)).round() as u8;
        Rgba {
            r: blend(self.r, back.r),
            g: blend(self.g, back.g),
            b: blend(self.b, back.b),
            a: 255,
        }
    }

    /// WCAG 2's relative luminance: 0 for black, 1 for white. Alpha ignored.
    pub fn luminance(self) -> f64 {
        let lin = |c: u8| {
            let c = f64::from(c) / 255.0;
            if c <= 0.040_45 {
                c / 12.92
            } else {
                ((c + 0.055) / 1.055).powf(2.4)
            }
        };
        0.2126 * lin(self.r) + 0.7152 * lin(self.g) + 0.0722 * lin(self.b)
    }

    /// WCAG 2's contrast ratio, 1 to 21: 4.5 or more for text, 3 or more for large text
    /// and shapes. Both solid (use [`Rgba::over`] first for a see-through one).
    pub fn contrast(self, other: Rgba) -> f64 {
        let (a, b) = (self.luminance(), other.luminance());
        (a.max(b) + 0.05) / (a.min(b) + 0.05)
    }
}

/// A theme's name, as `config/*.yaml` and the `theme` parameter write it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ThemeName {
    /// Catppuccin Mocha: dark, for night and a dark cabin. The default.
    #[default]
    Mocha,
    /// Catppuccin Latte: light, for daytime.
    Latte,
    /// Ben's Carleton theme. For now a copy of Mocha (see [`CALM`]).
    Calm,
}

impl ThemeName {
    /// Every theme, in the order the docs list them.
    pub const ALL: [ThemeName; 3] = [ThemeName::Mocha, ThemeName::Latte, ThemeName::Calm];

    /// The name as written in the settings.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Mocha => "mocha",
            Self::Latte => "latte",
            Self::Calm => "calm",
        }
    }

    /// The theme's colours.
    pub fn theme(self) -> &'static Theme {
        match self {
            Self::Mocha => &MOCHA,
            Self::Latte => &LATTE,
            Self::Calm => &CALM,
        }
    }
}

impl fmt::Display for ThemeName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A theme name that isn't one.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
#[error("no theme called {0:?}: mocha, latte or calm")]
pub struct UnknownTheme(pub String);

impl FromStr for ThemeName {
    type Err = UnknownTheme;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|t| t.as_str() == s.trim())
            .ok_or_else(|| UnknownTheme(s.to_owned()))
    }
}

/// Nav2's occupancy grid, as a picture: free, occupied and unknown cells.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GridColours {
    pub free: Rgba,
    pub occupied: Rgba,
    pub unknown: Rgba,
}

/// The street map (OpenStreetMap) under Nav2's map.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StreetColours {
    pub land: Rgba,
    pub green: Rgba,
    pub campus: Rgba,
    pub water: Rgba,
    pub building: Rgba,
    pub waterway: Rgba,
    /// The edge under the major roads and highways.
    pub casing: Rgba,
    pub label: Rgba,
    pub label_halo: Rgba,
    /// Each road class, from the least: path, rail, service, minor, medium, major,
    /// highway.
    pub path: Rgba,
    pub rail: Rgba,
    pub service: Rgba,
    pub minor: Rgba,
    pub medium: Rgba,
    pub major: Rgba,
    pub highway: Rgba,
}

/// Every colour the HUD and the map window use.
///
/// The pairs that must read (text on its panel, ink on its fill) are checked in the
/// tests: 4.5 : 1 for text, 3 : 1 for large text and shapes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Theme {
    // The window behind everything: a soft gradient, and two faint glows.
    pub background: Rgba,
    pub background_low: Rgba,
    pub glow_a: Rgba,
    pub glow_b: Rgba,

    // Frosted glass: the panels, see-through, with a soft edge and a shine on top.
    pub panel: Rgba,
    pub glass_edge: Rgba,
    pub glass_shine: Rgba,
    /// Glass over the map: the chips, the north arrow, the scale bar.
    pub overlay: Rgba,
    /// Thicker glass over the map: the search box, its list, the keyboard.
    pub overlay_strong: Rgba,
    /// A bar's empty part (steering, throttle, brake).
    pub track: Rgba,
    /// Behind the camera's picture.
    pub camera_back: Rgba,

    // Words.
    pub text: Rgba,
    pub caption: Rgba,
    /// Old news, and nothing yet.
    pub dim: Rgba,

    // Status, as words or lines on a panel.
    pub good: Rgba,
    pub warn: Rgba,
    pub bad: Rgba,
    /// A topic's SIM / BENCH / REPLAY tag.
    pub not_real_text: Rgba,

    // Status, as filled shapes with words on them.
    pub go_fill: Rgba,
    pub go_ink: Rgba,
    pub wait_fill: Rgba,
    pub wait_ink: Rgba,
    /// STOP, the stop-sign banner, the e-stop button.
    pub stop_fill: Rgba,
    /// The same, blinking, and under the pointer.
    pub stop_fill_alt: Rgba,
    pub stop_ink: Rgba,
    /// The SIMULATED / BENCH / REPLAY band.
    pub not_real: Rgba,
    pub not_real_ink: Rgba,

    // The map window.
    /// Nav2's plan, the search box while typing, the Enter key.
    pub accent: Rgba,
    pub accent_ink: Rgba,
    /// Under the plan, so it shows on any colour.
    pub plan_casing: Rgba,
    /// street_router's street route.
    pub street_route: Rgba,
    pub goal: Rgba,
    /// The place picked in the search.
    pub picked: Rgba,
    /// CONFIRM: stop and read.
    pub confirm: Rgba,
    pub confirm_ink: Rgba,
    pub car_body: Rgba,
    /// The edge of the car, the goal and the pin.
    pub marker_edge: Rgba,
    pub selected_row: Rgba,
    pub key: Rgba,
    pub key_command: Rgba,
    pub key_down: Rgba,
    pub grid: GridColours,
    /// Nav2's map over the streets: see-through.
    pub grid_over_streets: GridColours,
    pub grid_line: Rgba,
    pub grid_line_over_streets: Rgba,
    pub streets: StreetColours,
}

/// Catppuccin's official palettes (<https://catppuccin.com/palette>, MIT licence).
pub mod catppuccin {
    use super::Rgba;

    /// Mocha: the dark one.
    pub mod mocha {
        use super::Rgba;
        pub const RED: Rgba = Rgba::hex(0xf38ba8);
        pub const MAROON: Rgba = Rgba::hex(0xeba0ac);
        pub const PEACH: Rgba = Rgba::hex(0xfab387);
        pub const YELLOW: Rgba = Rgba::hex(0xf9e2af);
        pub const GREEN: Rgba = Rgba::hex(0xa6e3a1);
        pub const SKY: Rgba = Rgba::hex(0x89dceb);
        pub const BLUE: Rgba = Rgba::hex(0x89b4fa);
        pub const LAVENDER: Rgba = Rgba::hex(0xb4befe);
        pub const MAUVE: Rgba = Rgba::hex(0xcba6f7);
        pub const PINK: Rgba = Rgba::hex(0xf5c2e7);
        pub const TEXT: Rgba = Rgba::hex(0xcdd6f4);
        pub const SUBTEXT1: Rgba = Rgba::hex(0xbac2de);
        pub const SUBTEXT0: Rgba = Rgba::hex(0xa6adc8);
        pub const OVERLAY2: Rgba = Rgba::hex(0x9399b2);
        pub const OVERLAY1: Rgba = Rgba::hex(0x7f849c);
        pub const OVERLAY0: Rgba = Rgba::hex(0x6c7086);
        pub const SURFACE2: Rgba = Rgba::hex(0x585b70);
        pub const SURFACE1: Rgba = Rgba::hex(0x45475a);
        pub const SURFACE0: Rgba = Rgba::hex(0x313244);
        pub const BASE: Rgba = Rgba::hex(0x1e1e2e);
        pub const MANTLE: Rgba = Rgba::hex(0x181825);
        pub const CRUST: Rgba = Rgba::hex(0x11111b);
    }

    /// Latte: the light one.
    pub mod latte {
        use super::Rgba;
        pub const RED: Rgba = Rgba::hex(0xd20f39);
        pub const MAROON: Rgba = Rgba::hex(0xe64553);
        pub const PEACH: Rgba = Rgba::hex(0xfe640b);
        pub const YELLOW: Rgba = Rgba::hex(0xdf8e1d);
        pub const GREEN: Rgba = Rgba::hex(0x40a02b);
        pub const SKY: Rgba = Rgba::hex(0x04a5e5);
        pub const BLUE: Rgba = Rgba::hex(0x1e66f5);
        pub const LAVENDER: Rgba = Rgba::hex(0x7287fd);
        pub const MAUVE: Rgba = Rgba::hex(0x8839ef);
        pub const PINK: Rgba = Rgba::hex(0xea76cb);
        pub const TEXT: Rgba = Rgba::hex(0x4c4f69);
        pub const SUBTEXT1: Rgba = Rgba::hex(0x5c5f77);
        pub const SUBTEXT0: Rgba = Rgba::hex(0x6c6f85);
        pub const OVERLAY2: Rgba = Rgba::hex(0x7c7f93);
        pub const OVERLAY1: Rgba = Rgba::hex(0x8c8fa1);
        pub const OVERLAY0: Rgba = Rgba::hex(0x9ca0b0);
        pub const SURFACE2: Rgba = Rgba::hex(0xacb0be);
        pub const SURFACE1: Rgba = Rgba::hex(0xbcc0cc);
        pub const SURFACE0: Rgba = Rgba::hex(0xccd0da);
        pub const BASE: Rgba = Rgba::hex(0xeff1f5);
        pub const MANTLE: Rgba = Rgba::hex(0xe6e9ef);
        pub const CRUST: Rgba = Rgba::hex(0xdce0e8);
    }
}

/// The e-stop's red, in both themes: Latte's red, the deepest Catppuccin has. Mocha's
/// own red is a pastel pink, and an e-stop must shout. Its words are white.
const ESTOP_RED: Rgba = catppuccin::latte::RED;
/// A little brighter, for the blink and the pointer: still white words at 4.5 : 1, and
/// still 3 : 1 on Mocha's dark window.
const ESTOP_RED_ALT: Rgba = ESTOP_RED.mix(Rgba::hex(0xff2050), 30);
const ESTOP_INK: Rgba = Rgba::WHITE;

/// Catppuccin Mocha: dark. The car's default (night, cabin glare).
pub const MOCHA: Theme = {
    use catppuccin::mocha::*;
    Theme {
        background: BASE,
        background_low: CRUST,
        glow_a: MAUVE.alpha(20),
        glow_b: BLUE.alpha(16),

        panel: SURFACE0.alpha(184),
        glass_edge: TEXT.alpha(30),
        glass_shine: TEXT.alpha(16),
        overlay: MANTLE.alpha(215),
        overlay_strong: MANTLE.alpha(240),
        track: CRUST.alpha(170),
        camera_back: CRUST,

        text: TEXT,
        caption: SUBTEXT0,
        dim: OVERLAY2.mix(SUBTEXT0, 30),

        good: GREEN,
        warn: YELLOW,
        bad: RED,
        not_real_text: PEACH,

        go_fill: GREEN,
        go_ink: CRUST,
        wait_fill: YELLOW,
        wait_ink: CRUST,
        stop_fill: ESTOP_RED,
        stop_fill_alt: ESTOP_RED_ALT,
        stop_ink: ESTOP_INK,
        not_real: PEACH,
        not_real_ink: CRUST,

        accent: BLUE,
        accent_ink: CRUST,
        plan_casing: CRUST.alpha(210),
        street_route: MAUVE,
        goal: GREEN,
        picked: PINK,
        confirm: PEACH,
        confirm_ink: CRUST,
        car_body: CRUST,
        marker_edge: TEXT,
        selected_row: SURFACE1,
        key: SURFACE1,
        key_command: SURFACE0,
        key_down: SURFACE2,
        grid: GridColours {
            free: SUBTEXT1,
            occupied: CRUST,
            unknown: SURFACE1,
        },
        grid_over_streets: GridColours {
            free: BLUE.alpha(40),
            occupied: TEXT.alpha(215),
            unknown: BASE.alpha(0),
        },
        grid_line: CRUST.alpha(40),
        grid_line_over_streets: TEXT.alpha(18),
        streets: StreetColours {
            land: BASE,
            green: GREEN.mix(BASE, 86),
            campus: MAUVE.mix(BASE, 90),
            water: SKY.mix(BASE, 78),
            building: SURFACE0,
            waterway: SKY.mix(BASE, 60),
            casing: CRUST,
            label: SUBTEXT0,
            label_halo: CRUST.alpha(230),
            path: SURFACE1,
            rail: SURFACE2,
            service: SURFACE1,
            minor: SURFACE2,
            medium: OVERLAY0,
            major: OVERLAY1,
            highway: PEACH.mix(BASE, 45),
        },
    }
};

/// Catppuccin Latte: light, for daytime. Its green, yellow and peach are darkened for
/// words on white (Catppuccin's own are under 3 : 1 there).
pub const LATTE: Theme = {
    use catppuccin::latte::*;
    let green = GREEN.mix(Rgba::BLACK, 35);
    let amber = YELLOW.mix(Rgba::BLACK, 40);
    let orange = PEACH.mix(Rgba::BLACK, 30);
    Theme {
        background: BASE,
        background_low: CRUST,
        glow_a: LAVENDER.alpha(36),
        glow_b: PINK.alpha(28),

        panel: Rgba::WHITE.alpha(175),
        glass_edge: TEXT.alpha(30),
        glass_shine: Rgba::WHITE.alpha(200),
        overlay: Rgba::WHITE.alpha(225),
        overlay_strong: Rgba::WHITE.alpha(240),
        track: SURFACE0.alpha(200),
        camera_back: TEXT,

        text: TEXT,
        caption: SUBTEXT1,
        dim: SUBTEXT0.mix(TEXT, 30),

        good: green,
        warn: amber,
        bad: RED,
        not_real_text: orange,

        go_fill: green,
        go_ink: Rgba::WHITE,
        wait_fill: amber,
        wait_ink: Rgba::WHITE,
        stop_fill: ESTOP_RED,
        stop_fill_alt: ESTOP_RED_ALT,
        stop_ink: ESTOP_INK,
        not_real: PEACH,
        not_real_ink: catppuccin::mocha::CRUST,

        accent: BLUE,
        accent_ink: Rgba::WHITE,
        plan_casing: Rgba::WHITE.alpha(220),
        street_route: MAUVE,
        goal: green,
        picked: PINK.mix(Rgba::BLACK, 20),
        confirm: orange,
        confirm_ink: Rgba::WHITE,
        car_body: TEXT,
        marker_edge: Rgba::WHITE,
        selected_row: SURFACE0,
        key: Rgba::WHITE,
        key_command: SURFACE0,
        key_down: SURFACE2,
        grid: GridColours {
            free: Rgba::WHITE,
            occupied: TEXT,
            unknown: SURFACE1,
        },
        grid_over_streets: GridColours {
            free: BLUE.alpha(34),
            occupied: TEXT.alpha(200),
            unknown: BASE.alpha(0),
        },
        grid_line: TEXT.alpha(30),
        grid_line_over_streets: TEXT.alpha(22),
        streets: StreetColours {
            land: MANTLE,
            green: GREEN.mix(MANTLE, 80),
            campus: MAUVE.mix(MANTLE, 90),
            water: SKY.mix(MANTLE, 70),
            building: SURFACE0,
            waterway: SKY.mix(MANTLE, 40),
            casing: SURFACE1,
            label: TEXT,
            label_halo: BASE.alpha(230),
            path: SURFACE2,
            rail: OVERLAY0,
            service: Rgba::WHITE,
            minor: Rgba::WHITE,
            medium: Rgba::WHITE,
            major: Rgba::WHITE,
            highway: YELLOW.mix(Rgba::WHITE, 50),
        },
    }
};

/// `calm`: Ben's theme from his Carleton web work.
///
/// TODO(Ben): a placeholder, a copy of [`MOCHA`], until Ben gives the colours. Change
/// only this constant: the tests check its contrast the same way.
pub const CALM: Theme = MOCHA;

#[cfg(test)]
mod tests {
    use super::*;

    /// WCAG 2, AA: normal text.
    const TEXT_RATIO: f64 = 4.5;
    /// WCAG 2, AA: large text (the keyboard's letters) and shapes (the e-stop).
    const LARGE_RATIO: f64 = 3.0;

    fn check(theme: ThemeName, what: &str, fg: Rgba, back: Rgba, least: f64) -> Option<String> {
        let ratio = fg.over(back).contrast(back);
        (ratio < least).then(|| format!("{theme}: {what} is {ratio:.2} : 1, under {least}"))
    }

    /// Everything a panel's words sit on: the glass over the window's background (at
    /// both ends of its gradient).
    fn panel_backs(t: &Theme) -> [Rgba; 2] {
        [t.panel.over(t.background), t.panel.over(t.background_low)]
    }

    /// Everything the map's glass sits on: the land, each street colour, and Nav2's
    /// map over them; then the glass itself.
    fn overlay_backs(t: &Theme, glass: Rgba) -> Vec<Rgba> {
        let s = t.streets;
        let ground = [
            s.land,
            s.green,
            s.campus,
            s.water,
            s.building,
            s.waterway,
            s.path,
            s.rail,
            s.service,
            s.minor,
            s.medium,
            s.major,
            s.highway,
            t.grid.free,
            t.grid.occupied,
            t.grid.unknown,
        ];
        let over = t.grid_over_streets;
        ground
            .into_iter()
            .chain([over.free.over(s.land), over.occupied.over(s.land)])
            .map(|g| glass.over(g))
            .collect()
    }

    fn problems(name: ThemeName) -> Vec<String> {
        let t = name.theme();
        let mut out = Vec::new();
        let mut want = |what: &str, fg: Rgba, back: Rgba, least: f64| {
            out.extend(check(name, what, fg, back, least));
        };
        for back in panel_backs(t) {
            for (what, fg) in [
                ("text", t.text),
                ("caption", t.caption),
                ("dim", t.dim),
                ("good", t.good),
                ("warn", t.warn),
                ("bad", t.bad),
                ("not-real tag", t.not_real_text),
            ] {
                want(&format!("{what} on a panel"), fg, back, TEXT_RATIO);
            }
        }
        for glass in [t.overlay, t.overlay_strong] {
            for back in overlay_backs(t, glass) {
                for (what, fg) in [
                    ("text", t.text),
                    ("caption", t.caption),
                    ("dim", t.dim),
                    ("good", t.good),
                    ("warn", t.warn),
                ] {
                    want(&format!("{what} on the map's glass"), fg, back, TEXT_RATIO);
                }
            }
        }
        for (what, ink, fill) in [
            ("GO", t.go_ink, t.go_fill),
            ("WAIT", t.wait_ink, t.wait_fill),
            ("STOP", t.stop_ink, t.stop_fill),
            ("STOP, blinking", t.stop_ink, t.stop_fill_alt),
            ("SIMULATED", t.not_real_ink, t.not_real),
            ("Enter", t.accent_ink, t.accent),
            ("CONFIRM", t.confirm_ink, t.confirm),
        ] {
            want(&format!("{what}'s words"), ink, fill, TEXT_RATIO);
        }
        for (what, fill) in [
            ("the e-stop", t.stop_fill),
            ("the e-stop, pressed", t.stop_fill_alt),
            ("the GO panel", t.go_fill),
            ("the WAIT panel", t.wait_fill),
        ] {
            for back in [t.background, t.background_low] {
                want(&format!("{what} on the window"), fill, back, LARGE_RATIO);
            }
        }
        // The keyboard's keys: big letters, large text.
        let keyboard = t.overlay_strong.over(t.streets.land);
        for key in [t.key, t.key_command, t.key_down] {
            want("a key's letter", t.text, key.over(keyboard), LARGE_RATIO);
        }
        want(
            "a selected result",
            t.text,
            t.selected_row.over(keyboard),
            TEXT_RATIO,
        );
        // The map's marks on the street map.
        let land = t.streets.land;
        for (what, fg) in [
            ("the plan", t.accent),
            ("the goal", t.goal),
            ("the picked place", t.picked),
        ] {
            want(&format!("{what} on the land"), fg, land, LARGE_RATIO);
        }
        // The car: its edge on its body, and one of them on the land.
        want("the car's edge", t.marker_edge, t.car_body, LARGE_RATIO);
        let car = t.marker_edge.contrast(land).max(t.car_body.contrast(land));
        if car < LARGE_RATIO {
            out.push(format!("{name}: the car is {car:.2} : 1 on the land"));
        }
        out
    }

    #[test]
    fn every_theme_reads() {
        let all: Vec<String> = ThemeName::ALL.into_iter().flat_map(problems).collect();
        assert!(all.is_empty(), "{}", all.join("\n"));
    }

    #[test]
    fn red_amber_and_green_stay_apart() {
        // The status colours must be told apart by colour too, not only by their words:
        // red the reddest, green the greenest.
        for name in ThemeName::ALL {
            let t = name.theme();
            for (what, c) in [("bad", t.bad), ("stop", t.stop_fill)] {
                assert!(c.r > c.g && c.r > c.b, "{name}: {what} isn't red: {c:?}");
            }
            for (what, c) in [("good", t.good), ("go", t.go_fill)] {
                assert!(c.g > c.r && c.g > c.b, "{name}: {what} isn't green: {c:?}");
            }
            for (what, c) in [("warn", t.warn), ("wait", t.wait_fill)] {
                assert!(c.r > c.b && c.g > c.b, "{name}: {what} isn't amber: {c:?}");
            }
        }
    }

    #[test]
    fn contrast_matches_wcag() {
        assert!((Rgba::BLACK.contrast(Rgba::WHITE) - 21.0).abs() < 1e-9);
        assert!((Rgba::WHITE.contrast(Rgba::WHITE) - 1.0).abs() < 1e-9);
        // WebAIM's checker: #777777 on white is 4.48 : 1.
        assert!((Rgba::hex(0x777777).contrast(Rgba::WHITE) - 4.48).abs() < 0.01);
    }

    #[test]
    fn colours_mix_and_blend() {
        assert_eq!(
            Rgba::hex(0x123456),
            Rgba {
                r: 0x12,
                g: 0x34,
                b: 0x56,
                a: 255
            }
        );
        assert_eq!(Rgba::BLACK.mix(Rgba::WHITE, 50), Rgba::hex(0x808080));
        assert_eq!(Rgba::BLACK.mix(Rgba::WHITE, 0), Rgba::BLACK);
        assert_eq!(Rgba::BLACK.mix(Rgba::WHITE, 100), Rgba::WHITE);
        assert_eq!(Rgba::WHITE.alpha(0).over(Rgba::BLACK), Rgba::BLACK);
        assert_eq!(Rgba::WHITE.alpha(255).over(Rgba::BLACK), Rgba::WHITE);
    }

    #[test]
    fn names_read_and_round_trip() {
        for name in ThemeName::ALL {
            assert_eq!(name.as_str().parse::<ThemeName>(), Ok(name));
            assert_eq!(name.to_string(), name.as_str());
        }
        assert!("Mocha".parse::<ThemeName>().is_err());
        assert!("".parse::<ThemeName>().is_err());
        assert_eq!(ThemeName::default(), ThemeName::Mocha);
    }

    #[test]
    fn calm_is_mocha_until_ben_gives_its_colours() {
        assert_eq!(CALM, MOCHA);
    }
}
