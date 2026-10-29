//! The debug screen, drawn with raylib: the 3D view on the left, the panel on the right.
//!
//! ```text
//! +-------------------------------------------------+-----------------+
//! | LEGEND (localizers, offsets; cube heights)  fps | DEBUG HUD   SIM |
//! |                                                 | SENSORS         |
//! |        cubes, the car, the localizers,          |  IMU    OK 0.0s |
//! |        Nav2's plan, the trail                   |  ...            |
//! |                                                 | VEHICLE         |
//! |                                                 | TRACKER         |
//! | keys                                            | LIDAR           |
//! +-------------------------------------------------+-----------------+
//! ```
//!
//! The world is odom, z up. The cubes are drawn instanced: one cube mesh, one draw per
//! height band, a small shader that shades each face by its normal.

use std::time::Instant;

use debug_core::{
    cubes::{Band, CubeScan},
    orbit::Orbit,
    state::{DebugState, Localizer, Source},
};
use hud_core::{health::Health, vehicle::VehicleStatus};
use map_core::{
    car::CarShape,
    geom::{Point, Pose},
};
use raylib::prelude::*;

/// The panel's width, in window points.
pub const PANEL_W: f32 = 460.0;

const BACKGROUND: Color = Color::new(12, 14, 20, 255);
const PANEL: Color = Color::new(22, 25, 33, 255);
const SECTION: Color = Color::new(31, 35, 46, 255);
const CAPTION: Color = Color::new(140, 150, 170, 255);
const TEXT: Color = Color::new(240, 242, 246, 255);
const DIM: Color = Color::new(105, 110, 125, 255);
const GOOD: Color = Color::new(60, 200, 90, 255);
const WARN: Color = Color::new(245, 180, 40, 255);
const BAD: Color = Color::new(230, 60, 60, 255);
const NOT_REAL: Color = Color::new(255, 140, 0, 255);
const GRID: Color = Color::new(34, 39, 50, 255);
const GRID_MAJOR: Color = Color::new(50, 57, 72, 255);
const PLAN: Color = Color::new(255, 220, 60, 255);
const TRAIL: Color = Color::new(120, 125, 140, 255);

/// Each localizer's colour (the design's: local blue, global green, truth white, AMCL
/// orange).
pub fn localizer_colour(who: Localizer) -> Color {
    match who {
        Localizer::Local => Color::new(80, 130, 255, 255),
        Localizer::Global => Color::new(70, 225, 100, 255),
        Localizer::Truth => Color::new(245, 245, 245, 255),
        Localizer::Amcl => Color::new(255, 150, 40, 255),
    }
}

/// Each height band's colour: a cool ramp, dark ground to pale tops, so the
/// localizers' bright colours stand out on it.
pub fn band_colour(band: Band) -> Color {
    match band {
        Band::Ground => Color::new(48, 56, 70, 255),
        Band::Knee => Color::new(35, 98, 128, 255),
        Band::Waist => Color::new(38, 140, 160, 255),
        Band::Head => Color::new(70, 180, 190, 255),
        Band::High => Color::new(130, 210, 215, 255),
        Band::Above => Color::new(200, 238, 240, 255),
    }
}

/// Fonts tried in order; raylib's own small pixel font if none is there.
const FONT_FILES: [&str; 4] = [
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf", // macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   // macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", // Ubuntu, Raspberry Pi OS
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", // Fedora, AlmaLinux
];
const FONT_LOAD_SIZE: i32 = 96;

/// The cube shader: each instance's transform, a face shade from its normal.
const CUBE_VS: &str = r#"#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in mat4 instanceTransform;
uniform mat4 mvp;
out float shade;
void main() {
    vec3 n = normalize(vertexNormal);
    // Lit from above and a little to one side: tops brightest, sides apart.
    shade = 0.45 + 0.4 * max(n.z, 0.0) + 0.15 * abs(n.x) + 0.05 * abs(n.y);
    gl_Position = mvp * instanceTransform * vec4(vertexPosition, 1.0);
}
"#;
const CUBE_FS: &str = r#"#version 330
in float shade;
uniform vec4 colDiffuse;
out vec4 finalColor;
void main() {
    finalColor = vec4(colDiffuse.rgb * shade, colDiffuse.a);
}
"#;

/// raylib's font handle: one loaded from a file, or its built-in one.
enum UiFont {
    File(Font),
    BuiltIn(WeakFont),
}

impl AsRef<raylib::ffi::Font> for UiFont {
    fn as_ref(&self) -> &raylib::ffi::Font {
        match self {
            Self::File(f) => f.as_ref(),
            Self::BuiltIn(f) => f.as_ref(),
        }
    }
}

impl UiFont {
    fn measure(&self, text: &str, size: f32) -> f32 {
        let spacing = size / 24.0;
        match self {
            Self::File(f) => f.measure_text(text, size, spacing).x,
            Self::BuiltIn(f) => f.measure_text(text, size, spacing).x,
        }
    }
}

/// One instanced draw per band: its material (the shader, the band's colour), and the
/// transforms gathered this frame.
struct BandBatch {
    band: Band,
    material: WeakMaterial,
    transforms: Vec<Matrix>,
}

/// What a frame needs besides the state.
pub struct Frame<'a> {
    pub now: Instant,
    pub label: &'a str,
    pub orbit: &'a Orbit,
    pub fps: u32,
    /// The drawing test: say so on screen.
    pub bench: Option<usize>,
}

/// The screen: its font, the cube mesh and shader.
pub struct Ui {
    font: UiFont,
    cube: Mesh,
    /// Kept alive while the materials point at it.
    _shader: Shader,
    batches: Vec<BandBatch>,
    /// The size the cube mesh was made for.
    cube_size: f32,
    car: CarShape,
}

impl Ui {
    /// Loads the font, the shader and the cube. Needs the window open.
    pub fn new(
        rl: &mut RaylibHandle,
        thread: &RaylibThread,
        car: CarShape,
        cube_size: f32,
    ) -> Self {
        let loaded = FONT_FILES
            .iter()
            .filter(|path| std::path::Path::new(path).exists())
            .find_map(|path| rl.load_font_ex(thread, path, FONT_LOAD_SIZE, None).ok());
        let font = match loaded {
            Some(f) => {
                f.texture()
                    .set_texture_filter(thread, TextureFilter::TEXTURE_FILTER_BILINEAR);
                UiFont::File(f)
            }
            None => UiFont::BuiltIn(rl.get_font_default()),
        };
        let shader = rl.load_shader_from_memory(thread, Some(CUBE_VS), Some(CUBE_FS));
        let batches = Band::ALL
            .iter()
            .map(|&band| {
                let mut material = rl.load_material_default(thread);
                // SAFETY: a copy of the shader's handle; `_shader` keeps it loaded for as
                // long as the materials (and so the window) live.
                *material.shader_mut() = unsafe { WeakShader::from_raw(*shader.as_ref()) };
                material.maps_mut()[MaterialMapIndex::MATERIAL_MAP_ALBEDO as usize].color =
                    band_colour(band);
                BandBatch {
                    band,
                    material,
                    transforms: Vec::new(),
                }
            })
            .collect();
        // A hair smaller than the grid, so neighbours show an edge between them.
        let edge = cube_size * 0.92;
        let cube = Mesh::gen_mesh_cube(thread, edge, edge, edge);
        Self {
            font,
            cube,
            _shader: shader,
            batches,
            cube_size,
            car,
        }
    }

    /// Draws one frame.
    pub fn draw(&mut self, d: &mut RaylibDrawHandle, state: &DebugState, f: &Frame<'_>) {
        d.clear_background(BACKGROUND);
        let (w, h) = (d.get_screen_width() as f32, d.get_screen_height() as f32);
        let view_w = (w - PANEL_W).max(200.0);
        self.gather(state.scan.as_ref());
        self.world(d, state, f.orbit, view_w, h);
        self.legend(d, state, f, view_w, h);
        self.panel(d, state, f, view_w, w, h);
    }

    /// This frame's cube transforms, by band.
    fn gather(&mut self, scan: Option<&CubeScan>) {
        for b in &mut self.batches {
            b.transforms.clear();
        }
        let Some(scan) = scan else { return };
        let k = if self.cube_size > 0.0 {
            scan.size / self.cube_size
        } else {
            1.0
        };
        for c in &scan.cubes {
            let [x, y, z] = c.centre;
            let m = if (k - 1.0).abs() < 1e-3 {
                Matrix::translate(x, y, z)
            } else {
                Matrix::scale(k, k, k) * Matrix::translate(x, y, z)
            };
            if let Some(b) = self.batches.iter_mut().find(|b| b.band == c.band) {
                b.transforms.push(m);
            }
        }
    }

    /// The 3D view, in the left part of the window.
    fn world(
        &self,
        d: &mut RaylibDrawHandle,
        state: &DebugState,
        orbit: &Orbit,
        view_w: f32,
        h: f32,
    ) {
        let [px, py, pz] = orbit.position();
        let [tx, ty, tz] = orbit.target;
        let camera = Camera3D::perspective(
            Vector3::new(px, py, pz),
            Vector3::new(tx, ty, tz),
            Vector3::new(0.0, 0.0, 1.0),
            50.0,
        );
        // The framebuffer's pixels per window point (2 on a Retina screen). raylib keeps
        // the render size up to date on a resize; rlgl's own framebuffer size it doesn't.
        let (fb_w, fb_h) = (d.get_render_width(), d.get_render_height());
        let k = fb_w as f32 / d.get_screen_width().max(1) as f32;
        let mut d3 = d.begin_mode3D(camera);
        viewport(view_w * k, h * k, 50.0);

        ground_grid(&mut d3, orbit.target, orbit.distance);
        for b in &self.batches {
            if !b.transforms.is_empty() {
                d3.draw_mesh_instanced(&self.cube, b.material.clone(), &b.transforms);
            }
        }
        // The trail, then the plan, on the ground.
        let trail: Vec<Point> = state.trail().collect();
        for pair in trail.windows(2) {
            d3.draw_line3D(v3(pair[0], 0.03), v3(pair[1], 0.03), TRAIL);
        }
        // Nav2's points are ~5 cm apart: one tube per 0.5 m is plenty.
        let plan = thin(state.plan_in_odom(), 0.5);
        for pair in plan.windows(2) {
            d3.draw_cylinder_ex(v3(pair[0], 0.06), v3(pair[1], 0.06), 0.07, 0.07, 6, PLAN);
        }
        // The localizers: map-frame ones first, so the local EKF's car sits on top.
        for (i, who) in [Localizer::Truth, Localizer::Amcl, Localizer::Global]
            .into_iter()
            .enumerate()
        {
            if let Some(pose) = state.pose_in_odom(who) {
                marker(
                    &mut d3,
                    &self.car,
                    pose,
                    localizer_colour(who),
                    0.04 + 0.02 * i as f32,
                );
            }
        }
        if let Some(pose) = state.car() {
            car_body(&mut d3, &self.car, pose, localizer_colour(Localizer::Local));
        }
        drop(d3);
        // Back to the whole window for the 2D parts.
        // SAFETY: an rlgl state call on the drawing thread, after the 3D part.
        unsafe { raylib::ffi::rlViewport(0, 0, fb_w, fb_h) };
    }

    /// Over the 3D view: what each colour means, the camera, the keys.
    fn legend(
        &self,
        d: &mut RaylibDrawHandle,
        state: &DebugState,
        f: &Frame<'_>,
        view_w: f32,
        h: f32,
    ) {
        let x = 16.0;
        let mut y = 16.0;
        let box_h = 34.0 + 30.0 * 4.0 + 12.0 + 26.0 * 3.0;
        d.draw_rectangle_rounded(
            Rectangle::new(x - 6.0, y - 6.0, 330.0, box_h),
            0.06,
            8,
            Color::new(16, 18, 26, 215),
        );
        self.text(d, "WHERE THE CAR IS", x + 6.0, y, 18.0, CAPTION);
        y += 30.0;
        for who in Localizer::ALL {
            let colour = localizer_colour(who);
            let seen = state.pose_in_odom(who).is_some();
            d.draw_rectangle_rounded(Rectangle::new(x + 6.0, y + 3.0, 20.0, 20.0), 0.3, 4, colour);
            let words = if !seen {
                format!("{}  -", who.label())
            } else if who == Localizer::Local {
                who.label().to_owned()
            } else {
                match state.offset_from_local(who) {
                    Some(m) => format!("{}  {m:.2} m off", who.label()),
                    None => who.label().to_owned(),
                }
            };
            self.text(d, &words, x + 36.0, y, 22.0, if seen { TEXT } else { DIM });
            y += 30.0;
        }
        y += 8.0;
        self.text(
            d,
            "CUBES: HEIGHT ABOVE THE GROUND",
            x + 6.0,
            y,
            16.0,
            CAPTION,
        );
        y += 24.0;
        for (i, band) in Band::ALL.into_iter().enumerate() {
            let col = i % 3;
            let row = i / 3;
            let bx = x + 6.0 + col as f32 * 104.0;
            let by = y + row as f32 * 26.0;
            d.draw_rectangle_rounded(
                Rectangle::new(bx, by + 3.0, 16.0, 16.0),
                0.2,
                4,
                band_colour(band),
            );
            self.text(d, band.label(), bx + 22.0, by, 16.0, TEXT);
        }

        // Top right of the view: the frame rate, and the camera's mode.
        let fps = format!("{} fps   {}", f.fps, f.orbit.mode.label());
        let fw = self.font.measure(&fps, 20.0);
        self.text(d, &fps, view_w - fw - 16.0, 16.0, 20.0, CAPTION);
        if let Some(n) = f.bench {
            let s = format!("DRAWING TEST: {n} cubes");
            let sw = self.font.measure(&s, 26.0);
            self.text(d, &s, (view_w - sw) / 2.0, 16.0, 26.0, WARN);
        }

        // Bottom: the keys.
        let keys = "drag: turn    right-drag: move    wheel: zoom    C: camera    R: reset    F11: full screen";
        self.text(d, keys, 16.0, h - 34.0, 18.0, DIM);
    }

    /// The panel: every sensor from its own topic, the vehicle, the tracker, the lidar.
    fn panel(
        &self,
        d: &mut RaylibDrawHandle,
        state: &DebugState,
        f: &Frame<'_>,
        x0: f32,
        w: f32,
        h: f32,
    ) {
        d.draw_rectangle_rec(Rectangle::new(x0, 0.0, w - x0, h), PANEL);
        let x = x0 + 18.0;
        let right = w - 18.0;
        let mut y = 14.0;
        self.text(d, "DEBUG HUD", x, y, 32.0, TEXT);
        let label_w = self.font.measure(f.label, 22.0);
        let tag = Rectangle::new(right - label_w - 20.0, y + 4.0, label_w + 20.0, 32.0);
        d.draw_rectangle_rounded(tag, 0.3, 6, SECTION);
        self.text(d, f.label, tag.x + 10.0, y + 8.0, 22.0, CAPTION);
        y += 48.0;
        if let Some(banner) = state.origins.banner() {
            let r = Rectangle::new(x0 + 10.0, y, w - x0 - 20.0, 34.0);
            d.draw_rectangle_rounded(r, 0.25, 6, NOT_REAL);
            self.text(d, &banner, x + 4.0, y + 6.0, 20.0, Color::BLACK);
            y += 44.0;
        }

        y = self.section(d, "SENSORS AND ESTIMATES", x0, y, w);
        for source in Source::PANEL {
            let health = state.health(source, f.now);
            self.text(d, source.label(), x, y, 21.0, TEXT);
            let (word, colour) = health_word(health);
            let pill = Rectangle::new(x + 148.0, y + 1.0, 78.0, 26.0);
            d.draw_rectangle_rounded(pill, 0.4, 6, colour);
            let ww = self.font.measure(word, 17.0);
            self.text(
                d,
                word,
                pill.x + (pill.width - ww) / 2.0,
                y + 4.0,
                17.0,
                Color::BLACK,
            );
            let detail = match (health.age(), state.detail(source)) {
                (_, Some(text)) if health.is_ok() => text.to_owned(),
                (Some(age), _) => format!("{:.1} s ago", age.as_secs_f32()),
                (None, _) => String::new(),
            };
            let detail = fit(&self.font, &detail, right - (x + 240.0), 18.0);
            self.text(
                d,
                &detail,
                x + 240.0,
                y + 3.0,
                18.0,
                if health.is_ok() { CAPTION } else { DIM },
            );
            y += 31.0;
        }

        y = self.section(d, "VEHICLE", x0, y + 4.0, w);
        let vehicle_ok = state.health(Source::Vehicle, f.now).is_ok();
        match state.vehicle {
            Some(v) => y = self.vehicle(d, &v, x, right, y, vehicle_ok),
            None => {
                self.text(d, "no /vehicle/status yet", x, y, 20.0, DIM);
                y += 32.0;
            }
        }

        y = self.section(d, "TRACKER", x0, y + 4.0, w);
        match &state.track {
            Some(t) => {
                let colour = if state.health(Source::Track, f.now).is_ok() {
                    TEXT
                } else {
                    DIM
                };
                self.text(d, &t.tracker, x, y, 24.0, colour);
                let mut parts = Vec::new();
                if let Some(e) = t.cross_track {
                    parts.push(format!("{e:+.2} m off the path"));
                }
                if let Some(ms) = t.loop_ms {
                    parts.push(format!("{ms:.1} ms"));
                }
                let s = parts.join("   ");
                self.text(d, &s, x + 160.0, y + 4.0, 18.0, CAPTION);
                y += 34.0;
            }
            None => {
                self.text(d, "none (Nav2's own controller)", x, y, 20.0, DIM);
                y += 32.0;
            }
        }

        y = self.section(d, "LIDAR CUBES", x0, y + 4.0, w);
        match &state.scan {
            Some(scan) => {
                let rate = state
                    .scan_rate()
                    .map_or_else(String::new, |hz| format!("   {hz:.0} Hz"));
                let s = format!(
                    "{} cubes from {} points{rate}",
                    scan.cubes.len(),
                    scan.points
                );
                self.text(d, &s, x, y, 20.0, TEXT);
                y += 28.0;
                if scan.cut > 0 {
                    let s = format!("{} far cubes cut (max_cubes)", scan.cut);
                    self.text(d, &s, x, y, 18.0, WARN);
                    y += 26.0;
                }
            }
            None => {
                self.text(d, "no scan yet", x, y, 20.0, DIM);
                y += 28.0;
            }
        }
        for problem in [&state.scan_problem, &state.frame_problem]
            .into_iter()
            .flatten()
        {
            let s = fit(&self.font, problem, right - x, 17.0);
            self.text(d, &s, x, y, 17.0, WARN);
            y += 24.0;
        }
        let note = "heights above base_link (a 2D EKF)";
        self.text(d, note, x, h - 30.0, 15.0, DIM);
    }

    fn vehicle(
        &self,
        d: &mut RaylibDrawHandle,
        v: &VehicleStatus,
        x: f32,
        right: f32,
        y: f32,
        fresh: bool,
    ) -> f32 {
        let mode = v.mode.to_string();
        self.text(d, &mode, x, y, 24.0, if fresh { TEXT } else { DIM });
        let mw = self.font.measure(&mode, 24.0);
        let (armed, armed_colour) = if v.armed {
            ("ARMED", GOOD)
        } else {
            ("DISARMED", DIM)
        };
        let mut cx = x + mw + 16.0;
        for (word, colour) in [
            (armed, armed_colour),
            ("E-STOP", if v.estop_active { BAD } else { SECTION }),
        ] {
            let ww = self.font.measure(word, 17.0);
            let r = Rectangle::new(cx, y + 1.0, ww + 18.0, 28.0);
            d.draw_rectangle_rounded(r, 0.4, 6, colour);
            let text_colour = if colour == SECTION { DIM } else { Color::BLACK };
            self.text(d, word, cx + 9.0, y + 5.0, 17.0, text_colour);
            cx += ww + 26.0;
        }
        let y = y + 36.0;
        let s = format!(
            "steer {:+.1} deg    {:.1} m/s    gear {}",
            v.steering_angle.to_degrees(),
            v.speed.0,
            v.gear().letter()
        );
        let s = fit(&self.font, &s, right - x, 19.0);
        self.text(d, &s, x, y, 19.0, if fresh { CAPTION } else { DIM });
        let y = y + 28.0;
        if !v.faults.is_empty() {
            let s = fit(
                &self.font,
                &format!("faults: {}", v.faults),
                right - x,
                18.0,
            );
            self.text(d, &s, x, y, 18.0, BAD);
            return y + 26.0;
        }
        y
    }

    /// A section's band and caption; returns where its rows start.
    fn section(&self, d: &mut RaylibDrawHandle, title: &str, x0: f32, y: f32, w: f32) -> f32 {
        d.draw_rectangle_rec(Rectangle::new(x0, y, w - x0, 30.0), SECTION);
        self.text(d, title, x0 + 18.0, y + 6.0, 17.0, CAPTION);
        y + 40.0
    }

    fn text(&self, d: &mut RaylibDrawHandle, s: &str, x: f32, y: f32, size: f32, colour: Color) {
        d.draw_text_ex(&self.font, s, Vector2::new(x, y), size, size / 24.0, colour);
    }
}

/// The 3D view's viewport and projection: the left `w` x `h` pixels, 50 degrees high.
/// raylib's own begin_mode3D sizes them for the whole window.
fn viewport(w: f32, h: f32, fovy_deg: f32) {
    let (near, far) = (0.1_f64, 2000.0_f64);
    let top = near * (f64::from(fovy_deg).to_radians() / 2.0).tan();
    let right = top * f64::from(w) / f64::from(h.max(1.0));
    // SAFETY: rlgl state calls on the drawing thread, inside begin_mode3D (which has
    // pushed the projection; end_mode3D pops it).
    unsafe {
        raylib::ffi::rlViewport(0, 0, w as i32, h as i32);
        raylib::ffi::rlMatrixMode(raylib::ffi::RL_PROJECTION as i32);
        raylib::ffi::rlLoadIdentity();
        raylib::ffi::rlFrustum(-right, right, -top, top, near, far);
        raylib::ffi::rlMatrixMode(raylib::ffi::RL_MODELVIEW as i32);
    }
}

/// The points at least `step` metres apart, the last one kept.
fn thin(points: Vec<Point>, step: f64) -> Vec<Point> {
    let last = points.last().copied();
    let mut out: Vec<Point> = Vec::with_capacity(points.len());
    for p in points {
        if out.last().is_none_or(|q| q.distance(p).0 >= step) {
            out.push(p);
        }
    }
    if let (Some(l), Some(&end)) = (last, out.last()) {
        if end != l {
            out.push(l);
        }
    }
    out
}

fn v3(p: Point, z: f32) -> Vector3 {
    Vector3::new(p.x as f32, p.y as f32, z)
}

/// Lines every metre near the target, every 5 m brighter; reaching farther as the camera
/// backs off.
fn ground_grid(d: &mut impl RaylibDraw3D, target: [f32; 3], distance: f32) {
    let step = if distance > 80.0 { 5.0 } else { 1.0 };
    let reach = (distance * 2.5).clamp(30.0, 400.0);
    let n = (reach / step) as i32;
    let (cx, cy) = (
        (target[0] / step).round() * step,
        (target[1] / step).round() * step,
    );
    for i in -n..=n {
        let o = i as f32 * step;
        let major = ((cx + o) / 5.0).round() * 5.0 == (cx + o);
        let colour = if major { GRID_MAJOR } else { GRID };
        d.draw_line3D(
            Vector3::new(cx + o, cy - reach, 0.0),
            Vector3::new(cx + o, cy + reach, 0.0),
            colour,
        );
        let major = ((cy + o) / 5.0).round() * 5.0 == (cy + o);
        let colour = if major { GRID_MAJOR } else { GRID };
        d.draw_line3D(
            Vector3::new(cx - reach, cy + o, 0.0),
            Vector3::new(cx + reach, cy + o, 0.0),
            colour,
        );
    }
}

/// A filled triangle seen from both sides.
fn triangle(d: &mut impl RaylibDraw3D, a: Vector3, b: Vector3, c: Vector3, colour: Color) {
    d.draw_triangle3D(a, b, c, colour);
    d.draw_triangle3D(a, c, b, colour);
}

/// The local EKF's car: its outline from vehicle.yaml as a box (1.2 m high), filled
/// arrow on the roof.
fn car_body(d: &mut impl RaylibDraw3D, car: &CarShape, pose: Pose, colour: Color) {
    let outline = car.outline(pose);
    let (low, high) = (0.05, 1.2);
    let roof = Color::new(colour.r, colour.g, colour.b, 90);
    let r = outline.map(|p| v3(p, high));
    triangle(d, r[0], r[1], r[2], roof);
    triangle(d, r[0], r[2], r[3], roof);
    for i in 0..4 {
        let (a, b) = (outline[i], outline[(i + 1) % 4]);
        d.draw_line3D(v3(a, low), v3(b, low), colour);
        d.draw_line3D(v3(a, high), v3(b, high), colour);
        d.draw_line3D(v3(a, low), v3(a, high), colour);
    }
    let arrow = car.arrow(pose).map(|p| v3(p, high + 0.02));
    triangle(d, arrow[0], arrow[1], arrow[2], colour);
    pole(d, pose, colour);
}

/// Another localizer's guess: the car's outline on the ground, a filled arrow, a pole.
fn marker(d: &mut impl RaylibDraw3D, car: &CarShape, pose: Pose, colour: Color, z: f32) {
    let outline = car.outline(pose);
    for i in 0..4 {
        let (a, b) = (outline[i], outline[(i + 1) % 4]);
        d.draw_line3D(v3(a, z), v3(b, z), colour);
        d.draw_line3D(v3(a, z + 0.3), v3(b, z + 0.3), colour);
    }
    let arrow = car.arrow(pose).map(|p| v3(p, z));
    triangle(d, arrow[0], arrow[1], arrow[2], colour);
    pole(d, pose, colour);
}

/// A thin pole with a ball on top over base_link: seen from far off.
fn pole(d: &mut impl RaylibDraw3D, pose: Pose, colour: Color) {
    let p = pose.position;
    d.draw_cylinder_ex(v3(p, 0.0), v3(p, 2.4), 0.04, 0.04, 6, colour);
    d.draw_sphere(v3(p, 2.5), 0.18, colour);
}

fn health_word(h: Health) -> (&'static str, Color) {
    match h {
        Health::Ok(_) => ("OK", GOOD),
        Health::Stale(_) => ("STALE", WARN),
        Health::Never => ("NEVER", DIM),
    }
}

/// `s`, cut with "..." to fit `width` at `size`.
fn fit(font: &UiFont, s: &str, width: f32, size: f32) -> String {
    if font.measure(s, size) <= width {
        return s.to_owned();
    }
    let mut out: String = s.to_owned();
    while !out.is_empty() && font.measure(&format!("{out}..."), size) > width {
        out.pop();
    }
    format!("{out}...")
}
