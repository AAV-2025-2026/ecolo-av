//! The map window, drawn with raylib. The same dark look as the HUD (hud-app's ui.rs):
//! its colours and its font.
//!
//! ```text
//! +--------------------------------------------------+-----------------+
//! | [ SIMULATED band, when /system/source says so ]  | TRIP            |
//! | FOLLOWING THE CAR  [ / Search for a place ]  N   |   DRIVING       |
//! |                    [ results, or the place:  ]   |                 |
//! |                    [ DRIVE HERE / CONFIRM    ]   |                 |
//! |                                                  | DISTANCE LEFT   |
//! |         the streets (OpenStreetMap), and over    |   42 m          |
//! |         them Nav2's map, north up                |                 |
//! |         the plan (blue), the goal (green)        | TIME LEFT 15 s  |
//! |         the car (its outline and an arrow)       | SPEED   11 km/h |
//! | [ the sensor watchdog's verdict, unless OK ]     | TOPICS          |
//! | |----| 10 m          © OpenStreetMap contributors | keys            |
//! +--------------------------------------------------+-----------------+
//! ```
//!
//! The map part uses the window's pixels; the panel's sizes grow with the window, so a
//! 15" monitor and a laptop look alike.

use std::{sync::Arc, time::Instant};

use hud_core::{format, health::Health, watchdog::Alarm};
use map_core::{
    car::CarShape,
    config::Topic,
    destination::{Finder, Step},
    geom::{Metres, Point},
    grid::{Grid, Palette},
    places::{self, MIN_QUERY_CHARS},
    state::{MapState, Remaining},
    streets::TileShapes,
    trip::{time_left, Tone},
    view::{self, ScreenPoint, View, Viewport},
};
use raylib::prelude::*;

use crate::{
    search::Search,
    streets::{self, Status as StreetStatus, StreetMap},
};

// The HUD's colours (hud-app/src/ui.rs).
const BACKGROUND: Color = Color::new(12, 12, 16, 255);
const PANEL: Color = Color::new(30, 32, 40, 255);
const CAPTION: Color = Color::new(160, 165, 180, 255);
const TEXT: Color = Color::new(245, 245, 245, 255);
const DIM: Color = Color::new(110, 112, 120, 255);
const GOOD: Color = Color::new(60, 200, 90, 255);
const WARN: Color = Color::new(245, 180, 40, 255);
const BAD: Color = Color::new(230, 45, 45, 255);
/// The not-the-real-car banner.
const NOT_REAL: Color = Color::new(255, 140, 0, 255);

// The map's own colours. Free is light, occupied dark, unknown grey: the usual map
// colours, a little muted for a dark room.
const MAP_PALETTE: Palette = Palette {
    free: [196, 201, 210, 255],
    occupied: [26, 28, 34, 255],
    unknown: [74, 77, 88, 255],
};
/// Over the street map, Nav2's map is see-through: unknown shows the streets, free is a
/// faint blue tint (where Nav2 has looked), occupied a near-white (what's in the way).
const OVER_STREETS_PALETTE: Palette = Palette {
    free: [120, 160, 220, 46],
    occupied: [228, 230, 238, 215],
    unknown: [0, 0, 0, 0],
};
const GRID_LINE: Color = Color::new(0, 0, 0, 34);
/// Over the streets, the grid lines are light.
const GRID_LINE_OVER_STREETS: Color = Color::new(255, 255, 255, 18);
/// What the street map's data needs said wherever it's shown (ODbL), and where the tiles
/// were made.
const STREET_CREDIT: &str = "© OpenStreetMap contributors · Protomaps";
const PLAN: Color = Color::new(20, 115, 245, 255);
const PLAN_CASING: Color = Color::new(255, 255, 255, 200);
const GOAL: Color = Color::new(40, 175, 80, 255);
const CAR_BODY: Color = Color::new(24, 26, 32, 255);
const CAR_EDGE: Color = Color::new(255, 255, 255, 255);
/// The translucent backing of text drawn over the map.
const OVERLAY: Color = Color::new(12, 12, 16, 200);
/// The search box and its list: nearly solid, so the streets don't show through.
const SEARCH_BACK: Color = Color::new(22, 24, 30, 240);
const SEARCH_ROW_ON: Color = Color::new(48, 54, 70, 255);
/// The place picked in the search, on the map: a magenta pin, unlike the green goal.
const PICKED: Color = Color::new(215, 60, 200, 255);
/// CONFIRM: amber, to stop and read.
const CONFIRM: Color = Color::new(245, 160, 20, 255);

/// Fonts tried in order, as the HUD; raylib's own small pixel font if none is there.
const FONT_FILES: [&str; 4] = [
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf", // macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   // macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", // Ubuntu, Raspberry Pi OS
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", // Fedora, AlmaLinux
];
const FONT_LOAD_SIZE: i32 = 128;
/// The letters loaded from the font: ASCII, the street map's credit (© ·), and the
/// accents of Ottawa's French street names (rue Élisabeth-Bruyère, chemin de la Côte...).
const FONT_GLYPHS: &str = concat!(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`",
    "abcdefghijklmnopqrstuvwxyz{|}~",
    "©·–—’éèêëàâäçôöîïùûüÉÈÊÀÂÇÔÎœŒ°"
);

/// The panel's width at the reference size (1600 x 900); it grows with the window.
const PANEL_W: f32 = 400.0;
/// Below this many pixels long, the car is drawn as a plain arrow, so it never vanishes.
const CAR_MIN_PX: f32 = 22.0;

/// raylib's font handle: one loaded from a file, or its built-in one.
enum MapFont {
    File(Font),
    BuiltIn(WeakFont),
}

impl MapFont {
    fn measure(&self, text: &str, size: f32) -> f32 {
        let spacing = size / 20.0;
        match self {
            Self::File(f) => f.measure_text(text, size, spacing).x,
            Self::BuiltIn(f) => f.measure_text(text, size, spacing).x,
        }
    }
}

impl AsRef<raylib::ffi::Font> for MapFont {
    fn as_ref(&self) -> &raylib::ffi::Font {
        match self {
            Self::File(f) => f.as_ref(),
            Self::BuiltIn(f) => f.as_ref(),
        }
    }
}

/// The map's picture on the graphics card.
struct MapTexture {
    texture: Texture2D,
    width: u32,
    height: u32,
}

/// The window's font and the map's texture.
pub struct Ui {
    font: MapFont,
    map: Option<MapTexture>,
}

/// Where things are in the window this frame.
#[derive(Clone, Copy)]
pub struct Layout {
    /// The panel's scale: 1 at 1600 x 900.
    u: f32,
    pub map: Viewport,
    panel: Rectangle,
    /// The SIMULATED band above the map, when there is one.
    band: Option<Rectangle>,
}

impl Layout {
    /// `banner`: a SIMULATED / BENCH / REPLAY band goes above the map, not over it, so
    /// the whole map still fits below it.
    pub fn new(window_w: i32, window_h: i32, banner: bool) -> Self {
        let (w, h) = (window_w as f32, window_h as f32);
        let u = (w / 1600.0).min(h / 900.0).clamp(0.6, 3.0);
        let pw = PANEL_W * u;
        let band = banner.then(|| Rectangle::new(0.0, 0.0, (w - pw).max(1.0), 56.0 * u));
        let top = band.map_or(0.0, |b| b.height);
        Self {
            u,
            map: Viewport {
                x: 0.0,
                y: f64::from(top),
                width: f64::from((w - pw).max(1.0)),
                height: f64::from((h - top).max(1.0)),
            },
            panel: Rectangle::new(w - pw, 0.0, pw, h),
            band,
        }
    }
}

impl Ui {
    /// Loads the font. Needs the window open.
    pub fn new(rl: &mut RaylibHandle, thread: &RaylibThread) -> Self {
        let loaded = FONT_FILES
            .iter()
            .filter(|path| std::path::Path::new(path).exists())
            .find_map(|path| {
                rl.load_font_ex(thread, path, FONT_LOAD_SIZE, Some(FONT_GLYPHS))
                    .ok()
            });
        let font = match loaded {
            Some(f) => {
                f.texture()
                    .set_texture_filter(thread, TextureFilter::TEXTURE_FILTER_BILINEAR);
                MapFont::File(f)
            }
            None => MapFont::BuiltIn(rl.get_font_default()),
        };
        Self { font, map: None }
    }

    /// Puts a new map on the graphics card.
    pub fn upload(
        &mut self,
        rl: &mut RaylibHandle,
        thread: &RaylibThread,
        grid: &Grid,
        over_streets: bool,
    ) -> anyhow::Result<()> {
        let (gw, gh) = (grid.info.width, grid.info.height);
        let same_size = self
            .map
            .as_ref()
            .is_some_and(|m| m.width == gw && m.height == gh);
        if !same_size {
            let (w, h) = (i32::try_from(gw)?, i32::try_from(gh)?);
            // gen_image_color makes RGBA8 pixels, the layout to_rgba gives.
            let image = Image::gen_image_color(w, h, Color::BLACK);
            let texture = rl.load_texture_from_image(thread, &image)?;
            // Sharp cells when zoomed in: each is a square, not a blur.
            texture.set_texture_filter(thread, TextureFilter::TEXTURE_FILTER_POINT);
            self.map = Some(MapTexture {
                texture,
                width: gw,
                height: gh,
            });
        }
        if let Some(m) = self.map.as_mut() {
            let palette = if over_streets {
                &OVER_STREETS_PALETTE
            } else {
                &MAP_PALETTE
            };
            m.texture.update_texture(&grid.to_rgba(palette))?;
        }
        Ok(())
    }

    /// Draws one frame. `tiles`: the street map's, from [`StreetMap::frame`].
    #[allow(clippy::too_many_arguments)]
    pub fn draw(
        &self,
        d: &mut RaylibDrawHandle,
        state: &MapState,
        view: &View,
        car: &CarShape,
        now: Instant,
        source: &str,
        streets: &StreetMap,
        tiles: &[Arc<TileShapes>],
        search: &Search,
    ) {
        let banner = state.origins.banner();
        let layout = Layout::new(
            d.get_screen_width(),
            d.get_screen_height(),
            banner.is_some(),
        );
        d.clear_background(BACKGROUND);
        {
            let vp = layout.map;
            let mut s =
                d.begin_scissor_mode(vp.x as i32, vp.y as i32, vp.width as i32, vp.height as i32);
            let mut p = Painter {
                d: &mut s,
                font: &self.font,
                u: layout.u,
            };
            let on_streets = streets.visible();
            if on_streets {
                let font = &self.font;
                streets::draw(
                    p.d,
                    font,
                    |text, size| font.measure(text, size),
                    tiles,
                    view,
                    &vp,
                    p.u,
                );
            }
            self.draw_map(&mut p, state, view, &vp, car, now, on_streets);
            if let Some(place) = search.finder.picked() {
                picked_marker(&mut p, screen(view, search.on_map(place), &vp));
            }
            street_notes(&mut p, &vp, streets);
            watchdog_banner(&mut p, &vp, state, now);
        }
        let mut p = Painter {
            d,
            font: &self.font,
            u: layout.u,
        };
        if let (Some(band), Some(words)) = (layout.band, &banner) {
            p.d.draw_rectangle_rec(band, NOT_REAL);
            let cx = band.x + band.width / 2.0;
            p.centred(cx, band.y + 8.0 * p.u, 40.0, words, Color::BLACK);
        }
        panel(&mut p, &layout, state, now, source);
        draw_search(
            &mut p,
            &SearchLayout::new(&layout, &search.finder),
            search,
            state,
            now,
        );
    }

    #[allow(clippy::too_many_arguments)]
    fn draw_map(
        &self,
        p: &mut Painter<impl RaylibDraw>,
        state: &MapState,
        view: &View,
        vp: &Viewport,
        car: &CarShape,
        now: Instant,
        on_streets: bool,
    ) {
        let at = |pt: Point| screen(view, pt, vp);
        // The map's picture, turned as the grid is.
        if let (Some(grid), Some(tex)) = (&state.grid, &self.map) {
            let info = grid.info;
            let (w_m, h_m) = info.size();
            let top_left = at(info.origin.transform(Point::new(0.0, h_m)));
            let k = view.scale.0 as f32;
            let dest = Rectangle::new(top_left.x, top_left.y, w_m as f32 * k, h_m as f32 * k);
            let src = Rectangle::new(0.0, 0.0, tex.width as f32, tex.height as f32);
            let turn = -(info.origin.yaw.to_degrees() as f32);
            p.d.draw_texture_pro(&tex.texture, src, dest, Vector2::zero(), turn, Color::WHITE);
            let line = if on_streets {
                GRID_LINE_OVER_STREETS
            } else {
                GRID_LINE
            };
            grid_lines(p, view, vp, grid, line);
        }

        // The plan: a white casing under a blue line, so it shows on any colour.
        let route: Vec<Vector2> = state.route.points().iter().map(|&q| at(q)).collect();
        if route.len() >= 2 {
            p.d.draw_spline_linear(&route, 9.0 * p.u, PLAN_CASING);
            p.d.draw_spline_linear(&route, 5.0 * p.u, PLAN);
        }
        if let Some(goal) = state.goal() {
            goal_marker(p, at(goal));
        }
        if let Some(c) = &state.car {
            let fresh = state.health(Topic::Odom, now).is_ok();
            car_marker(p, view, vp, car, c.pose, fresh);
        }

        // On top: the banner, the view's mode, north, the scale bar, and any problem.
        let top = vp.y as f32 + 12.0 * p.u;
        p.chip(vp.x as f32 + 14.0 * p.u, top, view.mode.label(), TEXT);
        north(
            p,
            vp.x as f32 + vp.width as f32 - 34.0 * p.u,
            top + 4.0 * p.u,
        );
        scale_bar(p, view, vp);
        let mut problems = state.frame_problems();
        problems.extend(state.map_problem.clone());
        if state.grid.is_none() {
            let topic = state.config.topic(Topic::Map);
            let c = vp.centre();
            let msg = format!("NO MAP YET: waiting for {topic}");
            p.centred(c.x as f32, c.y as f32 - 80.0 * p.u, 30.0, &msg, WARN);
        }
        for (i, why) in problems.iter().enumerate() {
            let y = vp.y as f32 + vp.height as f32 - (96.0 + 36.0 * i as f32) * p.u;
            p.chip(vp.x as f32 + 14.0 * p.u, y, why, WARN);
        }
    }
}

fn screen(view: &View, p: Point, vp: &Viewport) -> Vector2 {
    let s = view.to_screen(p, vp);
    Vector2::new(s.x as f32, s.y as f32)
}

/// Thin lines every round number of metres, over the map only.
fn grid_lines(
    p: &mut Painter<impl RaylibDraw>,
    view: &View,
    vp: &Viewport,
    grid: &Grid,
    colour: Color,
) {
    let step = view::grid_step(view.scale, 70.0 * f64::from(p.u));
    let seen = view.visible(vp);
    let map = grid.info.bounds();
    let (x0, x1) = (seen.min.x.max(map.min.x), seen.max.x.min(map.max.x));
    let (y0, y1) = (seen.min.y.max(map.min.y), seen.max.y.min(map.max.y));
    if x0 >= x1 || y0 >= y1 {
        return;
    }
    for x in view::grid_lines(x0, x1, step) {
        let (a, b) = (
            screen(view, Point::new(x, y0), vp),
            screen(view, Point::new(x, y1), vp),
        );
        p.d.draw_line_ex(a, b, 1.0, colour);
    }
    for y in view::grid_lines(y0, y1, step) {
        let (a, b) = (
            screen(view, Point::new(x0, y), vp),
            screen(view, Point::new(x1, y), vp),
        );
        p.d.draw_line_ex(a, b, 1.0, colour);
    }
}

/// Bottom right of the map: the street map's credit when it's shown, or why it isn't.
/// The sensor watchdog's verdict, as on the HUD: red while it holds Nav2 (STOP, or the
/// watchdog silent), amber for a warning. Across the bottom of the map, over the scale.
fn watchdog_banner(
    p: &mut Painter<impl RaylibDraw>,
    vp: &Viewport,
    state: &MapState,
    now: Instant,
) {
    let Some(alarm) = state.sensor_alarm(now) else {
        return;
    };
    let (text, colour) = match &alarm {
        Alarm::Stop(t) => (t, BAD),
        Alarm::Warn(t) => (t, WARN),
    };
    let margin = 14.0 * p.u;
    let h = 44.0 * p.u;
    let r = Rectangle::new(
        vp.x as f32 + margin,
        (vp.y + vp.height) as f32 - 96.0 * p.u - h,
        (vp.width as f32 - 2.0 * margin).max(1.0),
        h,
    );
    p.d.draw_rectangle_rounded(r, 0.2, 8, colour);
    p.fitted(
        r.x + 12.0 * p.u,
        r.y + 9.0 * p.u,
        24.0,
        r.width - 24.0 * p.u,
        text,
        Color::BLACK,
    );
}

fn street_notes(p: &mut Painter<impl RaylibDraw>, vp: &Viewport, streets: &StreetMap) {
    let right = (vp.x + vp.width) as f32 - 14.0 * p.u;
    let bottom = (vp.y + vp.height) as f32 - 12.0 * p.u;
    if streets.visible() {
        let size = 15.0;
        let w = p.width(STREET_CREDIT, size);
        let r = Rectangle::new(
            right - w - 16.0 * p.u,
            bottom - 26.0 * p.u,
            w + 16.0 * p.u,
            26.0 * p.u,
        );
        p.d.draw_rectangle_rounded(r, 0.4, 8, OVERLAY);
        p.text(
            r.x + 8.0 * p.u,
            r.y + 5.0 * p.u,
            size,
            STREET_CREDIT,
            CAPTION,
        );
        return;
    }
    let note = match &streets.status {
        _ if !streets.shown => "STREETS OFF (S)".to_owned(),
        StreetStatus::Missing(_) => "No street map: pixi run get-street-map".to_owned(),
        StreetStatus::Failed(why) => format!("No street map: {why}"),
        StreetStatus::Loading | StreetStatus::Ready => return,
    };
    let w = p.width(&note, 17.0) + 24.0 * p.u;
    p.chip(right - w, bottom - 32.0 * p.u, &note, CAPTION);
}

/// The picked place: a magenta pin, its point at the place.
fn picked_marker(p: &mut Painter<impl RaylibDraw>, at: Vector2) {
    let r = 12.0 * p.u;
    let head = at - Vector2::new(0.0, 30.0 * p.u);
    p.d.draw_line_ex(at, head, 4.0 * p.u, CAR_EDGE);
    p.d.draw_circle_v(at, 4.0 * p.u, CAR_EDGE);
    p.d.draw_circle_v(head, r + 3.0 * p.u, CAR_EDGE);
    p.d.draw_circle_v(head, r, PICKED);
}

/// What a click on the search box hit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Click {
    /// The box itself: open it.
    Field,
    /// One of the results.
    Result(usize),
    /// DRIVE HERE, or CONFIRM.
    Button,
    /// Cancel, next to CONFIRM.
    Cancel,
}

/// Where the search box's parts are this frame: for drawing, and for clicks.
pub struct SearchLayout {
    u: f32,
    field: Rectangle,
    /// Under the box: the results (typing) or the picked place's card.
    under: Option<Rectangle>,
    rows: Vec<Rectangle>,
    button: Option<Rectangle>,
    cancel: Option<Rectangle>,
}

const ROW_H: f32 = 62.0;
const FOOTER_H: f32 = 34.0;
const CARD_H: f32 = 180.0;

impl SearchLayout {
    pub fn new(layout: &Layout, finder: &Finder) -> Self {
        let u = layout.u;
        let vp = layout.map;
        let w = (620.0 * u).min(vp.width as f32 - 40.0 * u).max(100.0);
        let x = vp.x as f32 + (vp.width as f32 - w) / 2.0;
        let field = Rectangle::new(x, vp.y as f32 + 12.0 * u, w, 46.0 * u);
        let top = field.y + field.height + 6.0 * u;
        let mut boxes = Self {
            u,
            field,
            under: None,
            rows: Vec::new(),
            button: None,
            cancel: None,
        };
        match finder.step() {
            Step::Closed => {}
            Step::Typing => {
                let n = finder.results().len();
                boxes.rows = (0..n)
                    .map(|i| Rectangle::new(x, top + i as f32 * ROW_H * u, w, ROW_H * u))
                    .collect();
                let body = if n == 0 {
                    46.0 * u
                } else {
                    n as f32 * ROW_H * u
                };
                boxes.under = Some(Rectangle::new(x, top, w, body + FOOTER_H * u));
            }
            Step::Picked | Step::Confirming => {
                let card = Rectangle::new(x, top, w, CARD_H * u);
                let by = card.y + 112.0 * u;
                let bh = 52.0 * u;
                if finder.step() == Step::Confirming {
                    let cw = 150.0 * u;
                    boxes.button = Some(Rectangle::new(x + 16.0 * u, by, w - cw - 44.0 * u, bh));
                    boxes.cancel = Some(Rectangle::new(x + w - cw - 16.0 * u, by, cw, bh));
                } else {
                    boxes.button = Some(Rectangle::new(x + 16.0 * u, by, w - 32.0 * u, bh));
                }
                boxes.under = Some(card);
            }
        }
        boxes
    }

    /// Whether the mouse is over the box or what's under it (not the map).
    pub fn contains(&self, at: ScreenPoint) -> bool {
        let v = Vector2::new(at.x as f32, at.y as f32);
        std::iter::once(self.field)
            .chain(self.under)
            .any(|r| r.check_collision_point_rec(v))
    }

    /// What a click at `at` hits.
    pub fn click(&self, at: ScreenPoint) -> Option<Click> {
        let v = Vector2::new(at.x as f32, at.y as f32);
        let hit = |r: &Rectangle| r.check_collision_point_rec(v);
        if hit(&self.field) {
            return Some(Click::Field);
        }
        if let Some(i) = self.rows.iter().position(hit) {
            return Some(Click::Result(i));
        }
        if self.cancel.as_ref().is_some_and(hit) {
            return Some(Click::Cancel);
        }
        self.button
            .as_ref()
            .filter(|r| hit(r))
            .map(|_| Click::Button)
    }
}

/// The search box, and under it the results or the picked place.
fn draw_search(
    p: &mut Painter<impl RaylibDraw>,
    boxes: &SearchLayout,
    search: &Search,
    state: &MapState,
    now: Instant,
) {
    let u = boxes.u;
    let finder = &search.finder;
    let f = boxes.field;
    let typing = finder.is_typing();
    p.d.draw_rectangle_rounded(f, 0.3, 8, SEARCH_BACK);
    let (edge, thick) = if typing { (PLAN, 3.0) } else { (DIM, 1.5) };
    p.d.draw_rectangle_rounded_lines_ex(f, 0.3, 8, thick * u, edge);
    let tx = f.x + 18.0 * u;
    let ty = f.y + 11.0 * u;
    let tw = f.width - 36.0 * u;
    if finder.query().is_empty() {
        let hint = if typing {
            "Type a place or an address"
        } else {
            "/   Search for a place"
        };
        p.fitted(tx, ty, 21.0, tw, hint, CAPTION);
    } else {
        let shown = if typing {
            format!("{}|", finder.query())
        } else {
            finder.query().to_owned()
        };
        p.fitted(tx, ty, 21.0, tw, &shown, TEXT);
    }

    let Some(under) = boxes.under else {
        if let Some(n) = search.notice(now) {
            let colour = if n.good { GOOD } else { WARN };
            p.chip(f.x, f.y + f.height + 8.0 * u, &n.text, colour);
        }
        return;
    };
    p.d.draw_rectangle_rounded(under, 0.06, 8, SEARCH_BACK);
    match finder.step() {
        Step::Typing => draw_results(p, boxes, search, state, under),
        Step::Picked | Step::Confirming => draw_picked(p, boxes, search, state, under),
        Step::Closed => {}
    }
}

fn draw_results(
    p: &mut Painter<impl RaylibDraw>,
    boxes: &SearchLayout,
    search: &Search,
    state: &MapState,
    under: Rectangle,
) {
    let u = boxes.u;
    let finder = &search.finder;
    let inner = under.width - 36.0 * u;
    for (i, (place, row)) in finder.results().iter().zip(&boxes.rows).enumerate() {
        if i == finder.selected() {
            p.d.draw_rectangle_rounded(*row, 0.12, 8, SEARCH_ROW_ON);
        }
        let x = row.x + 18.0 * u;
        let far = search
            .distance_from_car(place, state)
            .map(distance)
            .unwrap_or_default();
        let far_w = p.width(&far, 18.0);
        p.right(
            row.x + row.width - 18.0 * u,
            row.y + 10.0 * u,
            18.0,
            &far,
            CAPTION,
        );
        let title_w = inner - far_w - 16.0 * u;
        p.fitted(x, row.y + 8.0 * u, 21.0, title_w, &place.title, TEXT);
        p.fitted(x, row.y + 36.0 * u, 15.0, inner, &place.detail(), CAPTION);
    }
    let x = under.x + 18.0 * u;
    if finder.results().is_empty() {
        let (msg, colour) = match finder.problem() {
            Some(why) => (why.to_owned(), WARN),
            None if finder.query().chars().count() < MIN_QUERY_CHARS => {
                (format!("Type {MIN_QUERY_CHARS} letters or more"), CAPTION)
            }
            None => ("No places found".to_owned(), CAPTION),
        };
        p.fitted(x, under.y + 12.0 * u, 18.0, inner, &msg, colour);
    }
    let fy = under.y + under.height - FOOTER_H * u + 8.0 * u;
    p.text(x, fy, 14.0, places::CREDIT, DIM);
    p.right(
        under.x + under.width - 18.0 * u,
        fy,
        14.0,
        "Up Down  Enter pick  Esc close",
        DIM,
    );
}

fn draw_picked(
    p: &mut Painter<impl RaylibDraw>,
    boxes: &SearchLayout,
    search: &Search,
    state: &MapState,
    card: Rectangle,
) {
    let u = boxes.u;
    let Some(place) = search.finder.picked() else {
        return;
    };
    let x = card.x + 18.0 * u;
    let inner = card.width - 36.0 * u;
    p.fitted(x, card.y + 14.0 * u, 26.0, inner, &place.title, TEXT);
    let far = search
        .distance_from_car(place, state)
        .map(|d| format!("  ·  {} from the car", distance(d)))
        .unwrap_or_default();
    p.fitted(
        x,
        card.y + 52.0 * u,
        17.0,
        inner,
        &format!("{}{far}", place.detail()),
        CAPTION,
    );
    p.text(x, card.y + 80.0 * u, 14.0, places::CREDIT, DIM);
    let confirming = search.finder.step() == Step::Confirming;
    let goal = search.picked_goal(state);
    match (goal, boxes.button) {
        (Some(Ok(_)), Some(b)) => {
            let (colour, words) = if confirming {
                (CONFIRM, "CONFIRM: send goal  (Enter)")
            } else {
                (GOOD, "DRIVE HERE  (Enter)")
            };
            p.d.draw_rectangle_rounded(b, 0.3, 8, colour);
            p.centred(
                b.x + b.width / 2.0,
                b.y + 13.0 * u,
                23.0,
                words,
                Color::BLACK,
            );
        }
        (Some(Err(why)), Some(b)) => {
            p.d.draw_rectangle_rounded_lines_ex(b, 0.3, 8, 2.0 * u, WARN);
            p.fitted(
                b.x + 16.0 * u,
                b.y + 14.0 * u,
                21.0,
                b.width - 32.0 * u,
                &why.to_string(),
                WARN,
            );
        }
        _ => {}
    }
    if let Some(c) = boxes.cancel {
        p.d.draw_rectangle_rounded_lines_ex(c, 0.3, 8, 2.0 * u, CAPTION);
        p.centred(
            c.x + c.width / 2.0,
            c.y + 14.0 * u,
            20.0,
            "Esc cancel",
            TEXT,
        );
    }
    let hint = if confirming {
        "Enter sends Nav2 this goal"
    } else {
        "Esc back to the list"
    };
    p.right(
        card.x + card.width - 18.0 * u,
        card.y + 80.0 * u,
        14.0,
        hint,
        DIM,
    );
}

/// The goal: a green ring with a white edge and a white middle.
fn goal_marker(p: &mut Painter<impl RaylibDraw>, at: Vector2) {
    let r = 13.0 * p.u;
    p.d.draw_circle_v(at, r + 3.0 * p.u, CAR_EDGE);
    p.d.draw_circle_v(at, r, GOAL);
    p.d.draw_circle_v(at, r * 0.38, CAR_EDGE);
}

/// The car: its outline to scale, with an arrow; or, when that would be tiny, an arrow
/// of a fixed size. Grey when its position is old.
fn car_marker(
    p: &mut Painter<impl RaylibDraw>,
    view: &View,
    vp: &Viewport,
    shape: &CarShape,
    pose: map_core::geom::Pose,
    fresh: bool,
) {
    let body = if fresh { CAR_BODY } else { DIM };
    let at = |q: Point| screen(view, q, vp);
    let length_px = (shape.length * view.scale.0) as f32;
    if length_px >= CAR_MIN_PX {
        let o = shape.outline(pose).map(at);
        fill_quad(p, o, body);
        for i in 0..4 {
            p.d.draw_line_ex(o[i], o[(i + 1) % 4], 2.0 * p.u, CAR_EDGE);
        }
        let a = shape.arrow(pose).map(at);
        fill_triangle(p, a, CAR_EDGE);
    } else {
        // A fixed arrow, CAR_MIN_PX long, at the car's middle.
        let centre = at(shape.centre(pose));
        let (s, c) = (pose.yaw as f32).sin_cos();
        let (fwd, left) = (Vector2::new(c, -s), Vector2::new(-s, -c));
        let len = CAR_MIN_PX * p.u;
        let tip = centre + fwd * (len * 0.6);
        let back_l = centre - fwd * (len * 0.4) + left * (len * 0.4);
        let back_r = centre - fwd * (len * 0.4) - left * (len * 0.4);
        let edge = 3.0 * p.u;
        fill_triangle(
            p,
            [
                tip + fwd * edge,
                back_l + (left - fwd) * edge,
                back_r - (left + fwd) * edge,
            ],
            CAR_EDGE,
        );
        fill_triangle(p, [tip, back_l, back_r], body);
    }
}

/// raylib fills a triangle only when its corners go one way round; draw both ways.
fn fill_triangle(p: &mut Painter<impl RaylibDraw>, [a, b, c]: [Vector2; 3], colour: Color) {
    p.d.draw_triangle(a, b, c, colour);
    p.d.draw_triangle(a, c, b, colour);
}

fn fill_quad(p: &mut Painter<impl RaylibDraw>, [a, b, c, d]: [Vector2; 4], colour: Color) {
    fill_triangle(p, [a, b, c], colour);
    fill_triangle(p, [a, c, d], colour);
}

/// North is always up: a small arrow and an N, top right.
fn north(p: &mut Painter<impl RaylibDraw>, x: f32, y: f32) {
    let r = 20.0 * p.u;
    let c = Vector2::new(x, y + r);
    p.d.draw_circle_v(c, r, OVERLAY);
    let tip = Vector2::new(x, y + 5.0 * p.u);
    fill_triangle(
        p,
        [
            tip,
            Vector2::new(x - 6.0 * p.u, y + 16.0 * p.u),
            Vector2::new(x + 6.0 * p.u, y + 16.0 * p.u),
        ],
        TEXT,
    );
    p.centred(x, y + 17.0 * p.u, 18.0, "N", TEXT);
}

/// A bar of a round number of metres, bottom left.
fn scale_bar(p: &mut Painter<impl RaylibDraw>, view: &View, vp: &Viewport) {
    let Some((metres, px)) = view::scale_bar(view.scale, f64::from(180.0 * p.u)) else {
        return;
    };
    let px = px as f32;
    let label = if metres >= 1.0 {
        format!("{metres:.0} m")
    } else {
        format::metres(metres)
    };
    let x = vp.x as f32 + 18.0 * p.u;
    let y = vp.y as f32 + vp.height as f32 - 46.0 * p.u;
    let text_w = p.width(&label, 20.0);
    let back = Rectangle::new(
        x - 10.0 * p.u,
        y - 10.0 * p.u,
        px + text_w + 34.0 * p.u,
        38.0 * p.u,
    );
    p.d.draw_rectangle_rounded(back, 0.4, 8, OVERLAY);
    let bar_y = y + 9.0 * p.u;
    let t = 3.0 * p.u;
    p.d.draw_line_ex(Vector2::new(x, bar_y), Vector2::new(x + px, bar_y), t, TEXT);
    for end in [x, x + px] {
        p.d.draw_line_ex(
            Vector2::new(end, bar_y - 7.0 * p.u),
            Vector2::new(end, bar_y + 7.0 * p.u),
            t,
            TEXT,
        );
    }
    p.text(x + px + 12.0 * p.u, y - 2.0 * p.u, 20.0, &label, TEXT);
}

/// The panel: the trip, the distance and time left, the speed, the topics, the keys.
fn panel(
    p: &mut Painter<impl RaylibDraw>,
    layout: &Layout,
    state: &MapState,
    now: Instant,
    source: &str,
) {
    let u = p.u;
    let r = layout.panel;
    let m = 12.0 * u;
    let (x, w) = (r.x + m, r.width - 2.0 * m);
    let inner = x + 16.0 * u;
    let inner_w = w - 32.0 * u;
    let mut y = r.y + m;

    // TRIP: the word, big, and what it means.
    let trip = state.trip(now);
    let colour = match trip.tone() {
        Tone::Quiet => CAPTION,
        Tone::Good => GOOD,
        Tone::Warn => WARN,
        Tone::Bad => BAD,
    };
    let h = 132.0 * u;
    p.card(x, y, w, h, "TRIP");
    p.fitted(inner, y + 42.0 * u, 46.0, inner_w, trip.label(), colour);
    p.fitted(inner, y + 98.0 * u, 18.0, inner_w, trip.hint(), CAPTION);
    y += h + m;

    // DISTANCE LEFT: along the plan from the car.
    let h = 150.0 * u;
    p.card(x, y, w, h, "DISTANCE LEFT");
    let remaining = state.remaining();
    let (big, note) = match remaining {
        Some(Remaining::AlongPlan(d)) => (distance(d), "along Nav2's plan"),
        Some(Remaining::StraightLine(d)) => (distance(d), "in a straight line: no plan yet"),
        None if state.goal().is_some() => ("--".to_owned(), "the car's position is unknown"),
        None => ("--".to_owned(), "no goal"),
    };
    let fresh_car = state.health(Topic::Odom, now).is_ok();
    let big_colour = if remaining.is_some() && fresh_car {
        TEXT
    } else {
        DIM
    };
    p.fitted(inner, y + 38.0 * u, 64.0, inner_w, &big, big_colour);
    p.fitted(inner, y + 116.0 * u, 18.0, inner_w, note, CAPTION);
    y += h + m;

    // TIME LEFT and SPEED, side by side.
    let h = 104.0 * u;
    let half = (w - m) / 2.0;
    let speed = state.car.as_ref().map(|c| c.speed);
    p.card(x, y, half, h, "TIME LEFT");
    let eta = match (remaining, speed) {
        (Some(rem), Some(v)) if !matches!(trip, map_core::trip::Trip::Arrived) => {
            time_left(rem.metres(), f64::from(v.0)).map(format::age)
        }
        (Some(_), _) if matches!(trip, map_core::trip::Trip::Arrived) => Some("0 s".to_owned()),
        _ => None,
    };
    let (eta_text, eta_colour) = eta.map_or(("--".to_owned(), DIM), |t| (t, TEXT));
    p.fitted(
        inner,
        y + 40.0 * u,
        40.0,
        half - 32.0 * u,
        &eta_text,
        eta_colour,
    );
    let sx = x + half + m;
    p.card(sx, y, half, h, "SPEED");
    let (speed_text, speed_colour) = match speed {
        Some(v) => (
            format!("{} km/h", format::speed_km_per_hour(v)),
            if fresh_car { TEXT } else { DIM },
        ),
        None => ("--".to_owned(), DIM),
    };
    p.fitted(
        sx + 16.0 * u,
        y + 40.0 * u,
        40.0,
        half - 32.0 * u,
        &speed_text,
        speed_colour,
    );
    y += h + m;

    // TOPICS: what's been heard.
    let keys_h = 156.0 * u;
    let row_h = 32.0 * u;
    let wanted = 44.0 * u + Topic::ALL.len() as f32 * row_h + 8.0 * u;
    let h = (r.y + r.height - m - keys_h - m - y).clamp(60.0 * u, wanted);
    p.card(x, y, w, h, "TOPICS");
    let rows = ((h - 44.0 * u) / row_h).floor().max(0.0) as usize;
    for (i, t) in Topic::ALL.into_iter().take(rows).enumerate() {
        let ty = y + 42.0 * u + i as f32 * row_h;
        let health = state.health(t, now);
        let status = match (t, health) {
            // Latched or sent once: when it came means little; that it came, a lot.
            (Topic::Map | Topic::Goal | Topic::Source, Health::Ok(_)) => "HEARD".to_owned(),
            _ => format::health(health),
        };
        let colour = match health {
            Health::Ok(_) => GOOD,
            Health::Stale(_) => WARN,
            // No goal and no plan is normal; nothing announcing the source is too, and no
            // sensor watchdog (the turtle runs none).
            Health::Never
                if matches!(
                    t,
                    Topic::Plan | Topic::Goal | Topic::Source | Topic::Watchdog
                ) =>
            {
                DIM
            }
            Health::Never => BAD,
        };
        let sw = p.width(&status, 18.0);
        p.text(inner + inner_w - sw, ty, 18.0, &status, colour);
        p.fitted(
            inner,
            ty,
            18.0,
            inner_w - sw - 12.0 * u,
            state.config.topic(t),
            TEXT,
        );
    }

    // The keys, and where the data comes from: at the bottom.
    let y = (r.y + r.height - m - keys_h).max(y + h + m);
    p.card(x, y, w, keys_h, "KEYS");
    p.fitted(
        inner,
        y + 38.0 * u,
        17.0,
        inner_w,
        "F  follow the car / whole map",
        CAPTION,
    );
    p.fitted(
        inner,
        y + 64.0 * u,
        17.0,
        inner_w,
        "wheel, + -  zoom    drag  move",
        CAPTION,
    );
    p.fitted(
        inner,
        y + 90.0 * u,
        17.0,
        inner_w,
        "S  streets on / off",
        CAPTION,
    );
    p.fitted(
        inner,
        y + 116.0 * u,
        17.0,
        inner_w,
        "/  search for a place",
        CAPTION,
    );
    p.right(x + w - 16.0 * u, y + 10.0 * u, 18.0, source, CAPTION);
}

/// "42 m", "1.2 km".
fn distance(d: Metres) -> String {
    if d.0 >= 1000.0 {
        format!("{:.1} km", d.0 / 1000.0)
    } else {
        format::metres(d.0)
    }
}

/// Drawing with the font, sizes in points at the reference size.
struct Painter<'a, D: RaylibDraw> {
    d: &'a mut D,
    font: &'a MapFont,
    u: f32,
}

impl<D: RaylibDraw> Painter<'_, D> {
    fn width(&self, text: &str, size: f32) -> f32 {
        self.font.measure(text, size * self.u)
    }

    fn text(&mut self, x: f32, y: f32, size: f32, text: &str, colour: Color) {
        let px = size * self.u;
        self.d
            .draw_text_ex(self.font, text, Vector2::new(x, y), px, px / 20.0, colour);
    }

    fn centred(&mut self, cx: f32, y: f32, size: f32, text: &str, colour: Color) {
        let w = self.width(text, size);
        self.text(cx - w / 2.0, y, size, text, colour);
    }

    fn right(&mut self, x_right: f32, y: f32, size: f32, text: &str, colour: Color) {
        let w = self.width(text, size);
        self.text(x_right - w, y, size, text, colour);
    }

    /// Text that fits in `max_w`: shrinks it, down to 10 points.
    fn fitted(&mut self, x: f32, y: f32, size: f32, max_w: f32, text: &str, colour: Color) {
        let mut s = size;
        while s > 10.0 && self.width(text, s) > max_w {
            s -= 1.0;
        }
        self.text(x, y, s, text, colour);
    }

    /// A panel card: its background and its caption.
    fn card(&mut self, x: f32, y: f32, w: f32, h: f32, caption: &str) {
        let r = Rectangle::new(x, y, w, h);
        self.d.draw_rectangle_rounded(r, 0.08, 8, PANEL);
        self.text(x + 16.0 * self.u, y + 10.0 * self.u, 16.0, caption, CAPTION);
    }

    /// A label on a dark pill, over the map.
    fn chip(&mut self, x: f32, y: f32, text: &str, colour: Color) {
        let size = 17.0;
        let w = self.width(text, size);
        let r = Rectangle::new(x, y, w + 24.0 * self.u, 32.0 * self.u);
        self.d.draw_rectangle_rounded(r, 0.5, 8, OVERLAY);
        self.text(x + 12.0 * self.u, y + 7.0 * self.u, size, text, colour);
    }
}
