//! Ben's layout, in egui. Left: the scene, over the console. Right: the debug view of what the
//! lidar sees from the car with NDT's state, the one map you click on, keys and algorithms.

use std::time::Instant;

use bevy::prelude::*;
use bevy_egui::{egui, EguiContexts, EguiTextureHandle};
use debug_core::{
    cubes::CubeScan,
    ndt::{MapCells, NdtStatus},
    orbit::Orbit,
};
use hud_core::{gate::Light, origin::Origins, vehicle::VehicleStatus};
use map_core::{
    geom::{Point, Pose},
    grid::{Grid, Palette},
    view::{PixelsPerMetre, ScreenPoint, View, Viewport as MapViewport},
};

use crate::{
    feed::{self, Heard, Level, Update},
    set_viewport, CubesCamera, PictureImage, Source,
};

/// Height of the status strip, in points.
const STRIP: f32 = 48.0;
/// The share of the window's width the left column takes.
const LEFT_SHARE: f32 = 0.58;
/// The share of the left column's height the scene takes.
const SCENE_SHARE: f32 = 0.68;
/// The right column, top to bottom: the cubes, then the map; the rest is keys.
const CUBES_SHARE: f32 = 0.34;
const MAP_SHARE: f32 = 0.44;
/// The driver's view at rest: a little down, as the lidar's eyes are level with a wall's top.
const LOOK_DOWN: [f32; 2] = [0.0, -0.18];
/// The view from the car, top to bottom, radians: wide, as Ben preferred. The wheel zooms.
pub const DRIVER_FOV: f32 = 1.15;
/// A map wider than this, metres, shows the car's surroundings, not all of itself.
/// Cubes lower than this are the ground's waves, kerbs and grass: not compared with NDT's map.
pub const WAVES_TOP: f32 = 0.45;
/// The most of NDT's cells drawn on the flat map at once.
const MAX_MAP_CELLS: usize = 8_000;
const BIG_MAP: f64 = 300.0;
const BIG_MAP_VIEW: f64 = 160.0;
/// Log lines kept for the console.
const CONSOLE_LINES: usize = 500;
/// The most cubes drawn on the map. A real scan has about 2,000; beyond that it's a blur.
const MAX_MAP_CUBES: usize = 4_000;
/// The map's colours: a dark floor and bright walls, with unknown nearly black.
const MAP_COLOURS: Palette = Palette {
    free: [32, 32, 36, 255],
    occupied: [205, 205, 210, 255],
    unknown: [12, 12, 14, 255],
};
/// The costmap's: see-through where free, into purple and magenta over the map.
const COST_COLOURS: Palette = Palette {
    free: [90, 70, 170, 0],
    occupied: [150, 40, 130, 120],
    unknown: [0, 0, 0, 0],
};

/// The cubes view's colours (Ben, 5 Nov): one set of cells, going dark to light purple.
pub const NDT_DARK_RGB: [u8; 3] = [54, 36, 92];
pub const NDT_LIT_RGB: [u8; 3] = [216, 160, 255];
pub const NEW_CUBE_RGB: [u8; 3] = [255, 158, 40];

/// What's drawn. The defaults are the quiet view Ben asked for.
#[derive(Clone, Copy, Debug)]
pub struct Layers {
    pub road: bool,
    pub nav2_cubes: bool,
    pub ndt_cubes: bool,
    pub costmap: bool,
    pub ndt_map: bool,
    pub scan: bool,
    pub plan: bool,
}

impl Default for Layers {
    fn default() -> Self {
        Self {
            road: true,
            nav2_cubes: false,
            ndt_cubes: true,
            costmap: true,
            ndt_map: true,
            scan: true,
            plan: true,
        }
    }
}

/// Where a click on the map has got to.
#[derive(Clone, Copy, Debug, PartialEq, Default)]
pub enum Goal {
    #[default]
    None,
    /// Clicked, waiting for DRIVE HERE.
    Picked(Point),
    /// DRIVE HERE pressed, waiting for CONFIRM.
    Armed(Point),
    /// Confirmed: pretend Nav2 is driving there.
    Driving(Point),
}

impl Goal {
    fn point(self) -> Option<Point> {
        match self {
            Self::None => None,
            Self::Picked(p) | Self::Armed(p) | Self::Driving(p) => Some(p),
        }
    }
}

/// The corner's two tabs.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Tab {
    #[default]
    Keys,
    Algorithms,
}

/// One grid, and its picture once it's been made into a texture.
#[derive(Default)]
struct GridLayer {
    grid: Option<Grid>,
    texture: Option<egui::TextureHandle>,
    fresh: bool,
}

impl GridLayer {
    /// Nav2 sends the whole grid again and again. An unchanged one costs nothing: making a
    /// picture of a campus takes long enough to freeze the window, and makes it flash.
    fn set(&mut self, grid: Grid) {
        if self.grid.as_ref() != Some(&grid) {
            self.grid = Some(grid);
            self.fresh = true;
        }
    }

    /// Paints the grid at its place on the map, making a new texture if it changed.
    fn paint(
        &mut self,
        ui: &egui::Ui,
        name: &str,
        palette: &Palette,
        painter: &egui::Painter,
        to: impl Fn(Point) -> egui::Pos2,
    ) {
        let Some(grid) = &self.grid else { return };
        if self.fresh || self.texture.is_none() {
            let image = egui::ColorImage::from_rgba_unmultiplied(
                [grid.info.width as usize, grid.info.height as usize],
                &grid.to_rgba(palette),
            );
            // The same texture, new contents: a new one would be blank for a frame.
            match &mut self.texture {
                Some(texture) => texture.set(image, egui::TextureOptions::NEAREST),
                None => {
                    self.texture = Some(ui.ctx().load_texture(
                        name,
                        image,
                        egui::TextureOptions::NEAREST,
                    ));
                }
            }
            self.fresh = false;
        }
        if let Some(texture) = &self.texture {
            let bounds = grid.info.bounds();
            let top_left = to(Point::new(bounds.min.x, bounds.max.y));
            let bottom_right = to(Point::new(bounds.max.x, bounds.min.y));
            painter.image(
                texture.id(),
                egui::Rect::from_min_max(top_left, bottom_right),
                egui::Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0)),
                egui::Color32::WHITE,
            );
        }
    }
}

/// Everything the feed has said.
#[derive(Default)]
pub struct WorldNews {
    pub cubes: CubeScan,
    pub road: CubeScan,
    pub car_odom: Pose,
    pub car_map: Pose,
    ndt_index: Option<feed::MapIndex>,
    pub ndt: Option<MapCells>,
    /// How the newest cubes sit on NDT's map.
    pub map_match: feed::MapMatch,
    ndt_status: Option<NdtStatus>,
    ndt_pose: Option<Pose>,
    pub picture_size: Option<[u32; 2]>,
    plan: Vec<Point>,
    map: GridLayer,
    costmap: GridLayer,
    origins: Origins,
    vehicle: Option<VehicleStatus>,
    gate: Heard,
    watchdog: Heard,
    console: Vec<(Level, String)>,
}

impl WorldNews {
    /// A line for the console, from the window itself.
    pub fn note(&mut self, line: String) {
        self.push_line(Level::Info, line);
    }

    fn push_line(&mut self, level: Level, line: String) {
        self.console.push((level, line));
        if self.console.len() > CONSOLE_LINES {
            let extra = self.console.len() - CONSOLE_LINES;
            self.console.drain(..extra);
        }
    }

    /// Moves the newest cubes onto the map and sees which NDT cells they light.
    fn match_cubes(&mut self) {
        let Some(cells) = &self.ndt else { return };
        // The cubes are in odom; the car's two newest poses say where odom is on the map.
        let (car_odom, car_map) = (self.car_odom, self.car_map);
        let cubes: Vec<[f32; 3]> = self
            .cubes
            .cubes
            .iter()
            .map(|c| {
                let p = feed::odom_to_map([c.centre[0], c.centre[1]], car_odom, car_map);
                [p.x as f32, p.y as f32, c.centre[2]]
            })
            .collect();
        let index = self
            .ndt_index
            .get_or_insert_with(|| feed::MapIndex::new(&cells.centres, cells.size));
        self.map_match = index.match_cubes(&cubes, WAVES_TOP);
    }

    /// One piece of news. The picture isn't here: it goes straight into its image.
    pub fn apply(&mut self, update: Update, now: Instant) {
        match update {
            Update::Cubes(scan) => {
                self.cubes = scan;
                self.match_cubes();
            }
            Update::Road(scan) => self.road = scan,
            Update::CarInOdom(pose) => self.car_odom = pose,
            Update::CarInMap(pose) => self.car_map = pose,
            Update::Picture(_) => {}
            Update::Log(level, line) => self.push_line(level, line),
            Update::Ndt(status) => self.ndt_status = Some(status),
            Update::NdtPose(pose) => self.ndt_pose = Some(pose),
            Update::Plan(points) => self.plan = points,
            Update::Map(grid) => self.map.set(grid),
            Update::Costmap(grid) => self.costmap.set(grid),
            Update::Origin(announcement) => self.origins.apply(announcement),
            Update::Vehicle(status) => self.vehicle = Some(status),
            Update::Gate(text) => self.gate.set(text, now),
            Update::Watchdog(text) => self.watchdog.set(text, now),
        }
    }
}

/// Whose eyes the main view has.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum Eyes {
    /// From the car, looking where it drives: what it sees.
    #[default]
    Driver,
    /// Behind the car and above it, through the debug HUD's `Orbit`.
    Orbit,
}

impl Eyes {
    fn label(self) -> &'static str {
        match self {
            Self::Driver => "FROM THE CAR",
            Self::Orbit => "FROM BEHIND",
        }
    }
}

/// All the window's own state.
#[derive(Resource)]
pub struct UiState {
    pub layers: Layers,
    pub orbit: Orbit,
    /// Whose eyes the main view has.
    pub camera: Eyes,
    /// Driver's view: how far the head is turned and tilted, radians.
    pub look: [f32; 2],
    pub driver_fov: f32,
    /// Where the lidar sits on the car, in base_link: the driver's eyes.
    pub eyes: [f32; 3],
    pub world: WorldNews,
    view: View,
    /// The size the map was last fitted to; `None` once a person has moved or zoomed it.
    fitted_to: Option<egui::Vec2>,
    goal: Goal,
    tab: Tab,
    console_floor: Level,
    styled: bool,
    picks: [usize; ALGORITHMS.len()],
}

impl Default for UiState {
    fn default() -> Self {
        Self {
            layers: Layers::default(),
            orbit: Orbit::default(),
            camera: Eyes::default(),
            look: LOOK_DOWN,
            driver_fov: DRIVER_FOV,
            eyes: [0.0, 0.0, 1.5],
            world: WorldNews::default(),
            view: View::default(),
            fitted_to: Some(egui::Vec2::ZERO),
            goal: Goal::default(),
            tab: Tab::default(),
            console_floor: Level::Info,
            styled: false,
            picks: [0; ALGORITHMS.len()],
        }
    }
}

/// The swap list's rows: today's real choices (`docs/designs/2026-11-04_one-car.md`).
const ALGORITHMS: [(&str, &[&str]); 5] = [
    (
        "Planner",
        &[
            "lattice",
            "hybrid",
            "smac2d",
            "navfn",
            "theta*",
            "diffusion",
        ],
    ),
    (
        "Follower",
        &[
            "mppi",
            "rpp",
            "pure_pursuit",
            "stanley",
            "lqr",
            "mpc",
            "mpc_full",
        ],
    ),
    (
        "Where am I",
        &["ekf", "ndt", "amcl", "both", "ndt_ekf", "kiss_ekf", "kiss"],
    ),
    ("Obstacles", &["flat scan", "cubes"]),
    ("Speed loop", &["open", "pi", "smooth", "lqi"]),
];

/// The whole window, once a frame.
pub fn draw(
    mut contexts: EguiContexts,
    mut source: ResMut<Source>,
    picture: Res<PictureImage>,
    mut state: ResMut<UiState>,
    window: Single<&Window>,
    mut camera: Single<&mut Camera, With<CubesCamera>>,
) -> Result {
    let picture_id = contexts.add_image(EguiTextureHandle::Weak(picture.0.id()));
    let ctx = contexts.ctx_mut()?.clone();
    let state = &mut *state;

    if !state.styled {
        apply_style(&ctx);
        state.styled = true;
    }
    read_keys(&ctx, state);

    let whole = ctx.viewport_rect();
    let body = egui::Rect::from_min_max(whole.min + egui::vec2(0.0, STRIP), whole.max);
    let left_width = body.width() * LEFT_SHARE;
    let left = egui::Rect::from_min_size(body.min, egui::vec2(left_width, body.height()));
    let right = egui::Rect::from_min_max(egui::pos2(left.right(), body.top()), body.max);

    let picture_rect = egui::Rect::from_min_size(
        left.min,
        egui::vec2(left.width(), left.height() * SCENE_SHARE),
    );
    let console_rect = egui::Rect::from_min_max(picture_rect.left_bottom(), left.max);
    let cubes_rect = egui::Rect::from_min_size(
        right.min,
        egui::vec2(right.width(), right.height() * CUBES_SHARE),
    );
    let map_rect = egui::Rect::from_min_size(
        cubes_rect.left_bottom(),
        egui::vec2(right.width(), right.height() * MAP_SHARE),
    );
    let corner_rect = egui::Rect::from_min_max(map_rect.left_bottom(), right.max);

    let mut root = egui::Ui::new(
        ctx.clone(),
        "window".into(),
        egui::UiBuilder::new()
            .layer_id(egui::LayerId::background())
            .max_rect(whole),
    );

    let strip_rect = egui::Rect::from_min_size(whole.min, egui::vec2(whole.width(), STRIP));
    let feed = source.0.as_mut();
    panel(&mut root, strip_rect, |ui| status_strip(ui, state, feed));
    panel(&mut root, picture_rect, |ui| {
        picture_panel(ui, picture_id, state.world.picture_size);
    });
    panel(&mut root, console_rect, |ui| console_panel(ui, state));
    cubes_panel(&mut root, cubes_rect, state);
    ndt_line(&root, cubes_rect, &state.world);
    panel(&mut root, map_rect, |ui| map_panel(ui, state, feed));
    panel(&mut root, corner_rect, |ui| corner_panel(ui, state));

    let scale = window.scale_factor();
    let inner = cubes_rect.shrink(1.0);
    set_viewport(
        &mut camera,
        UVec2::new((inner.left() * scale) as u32, (inner.top() * scale) as u32),
        UVec2::new(
            (inner.width() * scale) as u32,
            (inner.height() * scale) as u32,
        ),
    );
    Ok(())
}

fn apply_style(ctx: &egui::Context) {
    ctx.set_visuals(egui::Visuals::dark());
    ctx.all_styles_mut(|style| {
        // Big, plain words: the docs' rule for a dyslexic reader holds on screens too.
        for (text, size) in [
            (egui::TextStyle::Body, 16.0),
            (egui::TextStyle::Button, 16.0),
            (egui::TextStyle::Monospace, 14.0),
            (egui::TextStyle::Heading, 19.0),
            (egui::TextStyle::Small, 13.0),
        ] {
            if let Some(font) = style.text_styles.get_mut(&text) {
                font.size = size;
            }
        }
    });
}

fn read_keys(ctx: &egui::Context, state: &mut UiState) {
    if ctx.egui_wants_keyboard_input() {
        return;
    }
    ctx.input(|input| {
        let layers = &mut state.layers;
        for (key, layer) in [
            (egui::Key::G, &mut layers.road),
            (egui::Key::V, &mut layers.nav2_cubes),
            (egui::Key::N, &mut layers.ndt_cubes),
            (egui::Key::O, &mut layers.costmap),
            (egui::Key::M, &mut layers.ndt_map),
            (egui::Key::S, &mut layers.scan),
            (egui::Key::P, &mut layers.plan),
        ] {
            if input.key_pressed(key) {
                *layer = !*layer;
            }
        }
        if input.key_pressed(egui::Key::C) {
            state.camera = match state.camera {
                Eyes::Driver => Eyes::Orbit,
                Eyes::Orbit => Eyes::Driver,
            };
        }
        if input.key_pressed(egui::Key::R) {
            state.orbit.reset();
            state.look = LOOK_DOWN;
            state.driver_fov = DRIVER_FOV;
        }
    });
}

/// A panel: its own rectangle, a dark background and a thin edge.
fn panel(root: &mut egui::Ui, rect: egui::Rect, add: impl FnOnce(&mut egui::Ui)) {
    root.painter()
        .rect_filled(rect, 0.0, egui::Color32::from_gray(14));
    root.painter().rect_stroke(
        rect,
        0.0,
        egui::Stroke::new(1.0, egui::Color32::from_gray(50)),
        egui::StrokeKind::Inside,
    );
    let mut ui = root.new_child(egui::UiBuilder::new().max_rect(rect.shrink(8.0)));
    ui.set_clip_rect(rect);
    add(&mut ui);
}

fn status_strip(ui: &mut egui::Ui, state: &mut UiState, feed: &mut dyn feed::Feed) {
    let world = &mut state.world;
    let estop_on = world.vehicle.is_some_and(|v| v.estop_active);
    let verdict = feed::verdict(estop_on, &world.gate, &world.watchdog, Instant::now());
    let allowed = feed::command_allowed(feed.may_command(), &world.origins);
    let mut press = false;
    ui.horizontal_centered(|ui| {
        if let Some(banner) = world.origins.banner() {
            pill(
                ui,
                &banner,
                egui::Color32::from_rgb(255, 140, 30),
                egui::Color32::BLACK,
            );
        }
        let light = match verdict.light {
            Light::Go => egui::Color32::from_rgb(45, 210, 110),
            Light::Wait => egui::Color32::from_rgb(240, 190, 70),
            Light::Stop => egui::Color32::from_rgb(235, 70, 70),
            Light::Unknown => egui::Color32::from_gray(150),
        };
        pill(ui, verdict.headline, light, egui::Color32::BLACK);
        ui.label(&verdict.reason);
        ui.label(egui::RichText::new(verdict.hint).color(egui::Color32::from_gray(150)));
        ui.separator();
        ui.label(if estop_on { "e-stop ON" } else { "e-stop off" });
        ui.separator();
        ui.label(feed.label());
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            let stop = egui::Button::new(
                egui::RichText::new("  E-STOP  ")
                    .strong()
                    .color(egui::Color32::WHITE),
            )
            .fill(egui::Color32::from_rgb(210, 30, 40));
            // It only ever sets the e-stop: clearing is pixi run clear estop.
            let response = ui.add_enabled(allowed.is_ok(), stop);
            press = response.clicked();
            if let Err(why) = &allowed {
                response.on_disabled_hover_text(why);
            }
        });
    });
    if press {
        if let Err(why) = feed.press_estop() {
            world.push_line(Level::Error, format!("e-stop not sent: {why}"));
        }
    }
}

fn pill(ui: &mut egui::Ui, words: &str, fill: egui::Color32, text: egui::Color32) {
    egui::Frame::new()
        .fill(fill)
        .corner_radius(4.0)
        .inner_margin(egui::vec2(10.0, 4.0))
        .show(ui, |ui| {
            ui.label(egui::RichText::new(words).strong().color(text));
        });
}

fn title(ui: &mut egui::Ui, words: &str) {
    ui.label(
        egui::RichText::new(words)
            .strong()
            .color(egui::Color32::from_gray(190)),
    );
}

fn picture_panel(ui: &mut egui::Ui, picture_id: egui::TextureId, size: Option<[u32; 2]>) {
    title(ui, "THE SCENE");
    let Some([width, height]) = size else {
        ui.centered_and_justified(|ui| {
            ui.label("no picture yet: is the chase camera on? (chase_camera:=true)");
        });
        return;
    };
    let room = ui.available_size();
    let aspect = width as f32 / height.max(1) as f32;
    let size = if room.x / room.y > aspect {
        egui::vec2(room.y * aspect, room.y)
    } else {
        egui::vec2(room.x, room.x / aspect)
    };
    ui.centered_and_justified(|ui| {
        ui.image(egui::load::SizedTexture::new(picture_id, size));
    });
}

fn console_panel(ui: &mut egui::Ui, state: &mut UiState) {
    ui.horizontal(|ui| {
        title(ui, "CONSOLE");
        ui.selectable_value(&mut state.console_floor, Level::Info, "All");
        ui.selectable_value(&mut state.console_floor, Level::Warn, "Warnings");
        ui.selectable_value(&mut state.console_floor, Level::Error, "Errors");
    });
    egui::ScrollArea::vertical()
        .auto_shrink(false)
        .stick_to_bottom(true)
        .show(ui, |ui| {
            for (level, line) in state
                .world
                .console
                .iter()
                .filter(|(l, _)| *l >= state.console_floor)
            {
                let colour = match level {
                    Level::Info => egui::Color32::from_gray(190),
                    Level::Warn => egui::Color32::from_rgb(240, 190, 70),
                    Level::Error => egui::Color32::from_rgb(255, 95, 95),
                };
                ui.label(egui::RichText::new(line).monospace().color(colour));
            }
        });
}

/// The cubes' panel draws no background: Bevy's 3D camera shows through.
fn cubes_panel(root: &mut egui::Ui, rect: egui::Rect, state: &mut UiState) {
    let response = root.allocate_rect(rect, egui::Sense::click_and_drag());
    let drag = response.drag_delta();
    if response.dragged_by(egui::PointerButton::Primary) {
        match state.camera {
            Eyes::Driver => {
                state.look[0] -= drag.x * 0.005;
                state.look[1] = (state.look[1] - drag.y * 0.005).clamp(-1.2, 1.2);
            }
            Eyes::Orbit => state.orbit.rotate(drag.x * 0.01, drag.y * 0.01),
        }
    }
    if state.camera == Eyes::Orbit && response.dragged_by(egui::PointerButton::Secondary) {
        state.orbit.pan(drag.x * 0.05, drag.y * 0.05);
    }
    if response.hovered() {
        let scroll = root.input(|input| input.smooth_scroll_delta.y);
        if scroll != 0.0 {
            let by = (1.0 - scroll * 0.002).clamp(0.5, 1.5);
            match state.camera {
                Eyes::Driver => state.driver_fov = (state.driver_fov * by).clamp(0.15, 1.4),
                Eyes::Orbit => state.orbit.zoom(by),
            }
        }
    }
    root.painter().rect_stroke(
        rect,
        0.0,
        egui::Stroke::new(1.0, egui::Color32::from_gray(50)),
        egui::StrokeKind::Inside,
    );
    root.painter().text(
        rect.left_top() + egui::vec2(8.0, 6.0),
        egui::Align2::LEFT_TOP,
        format!("WHAT THE LIDAR SEES   {}", state.camera.label()),
        egui::FontId::proportional(16.0),
        egui::Color32::from_gray(210),
    );
}

/// What the colours mean, so nobody has to guess.
fn legend(root: &egui::Ui, rect: egui::Rect, world: &WorldNews) {
    let rows: &[([u8; 3], &str)] = if world.ndt.is_some() {
        &[
            (NDT_DARK_RGB, "NDT's map"),
            (NDT_LIT_RGB, "lidar sees it too"),
            (NEW_CUBE_RGB, "lidar only: not on the map"),
        ]
    } else {
        &[([150, 225, 205], "lidar's cubes (no NDT map)")]
    };
    let mut x = rect.left() + 8.0;
    let y = rect.top() + 50.0;
    for ([r, g, b], words) in rows {
        let square = egui::Rect::from_min_size(egui::pos2(x, y + 2.0), egui::vec2(12.0, 12.0));
        root.painter()
            .rect_filled(square, 2.0, egui::Color32::from_rgb(*r, *g, *b));
        let end = root.painter().text(
            egui::pos2(x + 17.0, y),
            egui::Align2::LEFT_TOP,
            *words,
            egui::FontId::proportional(14.0),
            egui::Color32::from_gray(200),
        );
        x = end.right() + 16.0;
    }
}

/// NDT's state over the cubes: is localization holding, and how far from the EKF?
fn ndt_line(root: &egui::Ui, rect: egui::Rect, world: &WorldNews) {
    let mut line = feed::ndt_line(world.ndt_status.as_ref(), world.ndt_pose, world.car_map);
    if let Some(share) = world.map_match.share_on_map(world.cubes.cubes.len()) {
        line.words
            .push_str(&format!("   {:.0}% of cubes on the map", share * 100.0));
    }
    let colour = match line.state {
        feed::NdtLight::Good => egui::Color32::from_rgb(45, 210, 110),
        feed::NdtLight::Poor => egui::Color32::from_rgb(240, 190, 70),
        feed::NdtLight::Lost => egui::Color32::from_rgb(255, 95, 95),
        feed::NdtLight::Off => egui::Color32::from_gray(170),
    };
    root.painter().text(
        rect.left_top() + egui::vec2(8.0, 28.0),
        egui::Align2::LEFT_TOP,
        line.words,
        egui::FontId::proportional(16.0),
        colour,
    );
    legend(root, rect, world);
    if world.cubes.cubes.is_empty() {
        root.painter().text(
            rect.center(),
            egui::Align2::CENTER_CENTER,
            "no cubes yet: run with screen_cubes:=true or voxels:=true",
            egui::FontId::proportional(16.0),
            egui::Color32::from_gray(170),
        );
    }
}

fn screen(p: ScreenPoint) -> egui::Pos2 {
    egui::pos2(p.x as f32, p.y as f32)
}

fn map_panel(ui: &mut egui::Ui, state: &mut UiState, feed: &mut dyn feed::Feed) {
    ui.horizontal(|ui| {
        title(ui, "THE MAP: click to pick a goal");
        let layers = &mut state.layers;
        ui.toggle_value(&mut layers.costmap, "Costmap");
        ui.toggle_value(&mut layers.ndt_map, "NDT");
        ui.toggle_value(&mut layers.scan, "Cubes");
        ui.toggle_value(&mut layers.plan, "Plan");
    });

    let rect = ui.available_rect_before_wrap();
    let viewport = MapViewport {
        x: f64::from(rect.left()),
        y: f64::from(rect.top()),
        width: f64::from(rect.width()),
        height: f64::from(rect.height()),
    };
    // The window's size can change in its first frames, and when dragged: fit again, until
    // a person has chosen a view of their own.
    let fit_to = state.world.map.grid.as_ref().map(|grid| grid.info.bounds());
    let car = state.world.car_map.position;
    if let (Some(bounds), true) = (fit_to, state.fitted_to.is_some()) {
        let (width, height) = bounds.size();
        // A whole campus would make the car a dot: follow the car, until a person moves.
        if width.max(height) > BIG_MAP {
            state.view.centre = car;
            state.view.set_scale(PixelsPerMetre(
                viewport.width.min(viewport.height) / BIG_MAP_VIEW,
            ));
            state.fitted_to = Some(rect.size());
        }
    }
    if let (Some(bounds), true) = (
        fit_to,
        state.fitted_to.is_some_and(|size| size != rect.size()),
    ) {
        let (width, height) = bounds.size();
        state.view.centre = bounds.centre();
        state.view.set_scale(PixelsPerMetre(
            (viewport.width / width.max(1.0)).min(viewport.height / height.max(1.0)) * 0.97,
        ));
        state.fitted_to = Some(rect.size());
    }

    let response = ui.allocate_rect(rect, egui::Sense::click_and_drag());
    if response.clicked() {
        if let Some(at) = response.interact_pointer_pos() {
            let on_map = state.view.to_map(
                ScreenPoint::new(f64::from(at.x), f64::from(at.y)),
                &viewport,
            );
            match feed::refusal(on_map, state.world.map.grid.as_ref()) {
                None => state.goal = Goal::Picked(on_map),
                Some(why) => state
                    .world
                    .push_line(Level::Warn, format!("no goal: {why}")),
            }
        }
    }
    if response.dragged_by(egui::PointerButton::Secondary) {
        let drag = response.drag_delta();
        let k = state.view.scale.0;
        state.fitted_to = None;
        state.view.centre = Point::new(
            state.view.centre.x - f64::from(drag.x) / k,
            state.view.centre.y + f64::from(drag.y) / k,
        );
    }
    if response.hovered() {
        let scroll = ui.input(|input| input.smooth_scroll_delta.y);
        if scroll != 0.0 {
            let k = state.view.scale.0 * f64::from(1.0 + scroll * 0.002);
            state.fitted_to = None;
            state.view.set_scale(PixelsPerMetre(k));
        }
    }

    let painter = ui.painter_at(rect);
    let view = state.view;
    let to = |p: Point| screen(view.to_screen(p, &viewport));
    let k = view.scale.0 as f32;
    let layers = state.layers;
    let world = &mut state.world;

    if world.map.grid.is_none() {
        painter.text(
            rect.center(),
            egui::Align2::CENTER_CENTER,
            "waiting for Nav2's map",
            egui::FontId::proportional(16.0),
            egui::Color32::from_gray(170),
        );
    }
    world.map.paint(ui, "map", &MAP_COLOURS, &painter, to);
    if layers.costmap {
        world
            .costmap
            .paint(ui, "costmap", &COST_COLOURS, &painter, to);
    }
    if layers.ndt_map {
        if let Some(cells) = &world.ndt {
            // A campus has far too many for one frame: only those on screen, and not all of
            // those when zoomed far out.
            let on_screen = cells
                .footprint
                .points
                .iter()
                .map(|[x, y]| to(Point::new(f64::from(*x), f64::from(*y))))
                .filter(|at| rect.contains(*at))
                .take(MAX_MAP_CELLS);
            // Squares, not circles: thousands of circles cost more than the rest of the frame.
            for at in on_screen {
                painter.rect_filled(
                    egui::Rect::from_center_size(at, egui::vec2(2.0, 2.0)),
                    0.0,
                    egui::Color32::from_rgb(205, 165, 245),
                );
            }
        }
    }
    let car = world.car_map;
    if layers.scan {
        for cube in world.cubes.cubes.iter().take(MAX_MAP_CUBES) {
            let p = feed::odom_to_map([cube.centre[0], cube.centre[1]], world.car_odom, car);
            painter.circle_filled(to(p), 1.5, egui::Color32::from_rgb(40, 220, 110));
        }
    }
    if layers.plan && world.plan.len() >= 2 {
        let line: Vec<_> = world.plan.iter().map(|p| to(*p)).collect();
        painter.add(egui::Shape::line(
            line,
            egui::Stroke::new(2.5, egui::Color32::from_rgb(90, 200, 255)),
        ));
    }
    if let Some(goal) = state.goal.point() {
        painter.circle_stroke(to(goal), 7.0, egui::Stroke::new(2.5, egui::Color32::YELLOW));
    }
    // The car as an arrow, big enough to find whatever the zoom.
    let (sin, cos) = car.yaw.sin_cos();
    let reach = f64::from(10.0 / k).max(1.5);
    let nose = Point::new(car.position.x + reach * cos, car.position.y + reach * sin);
    let side = |d: f64| {
        Point::new(
            car.position.x - reach * 0.6 * cos - d * sin,
            car.position.y - reach * 0.6 * sin + d * cos,
        )
    };
    painter.add(egui::Shape::convex_polygon(
        vec![to(nose), to(side(reach * 0.6)), to(side(-reach * 0.6))],
        egui::Color32::from_rgb(140, 190, 255),
        egui::Stroke::new(1.5, egui::Color32::WHITE),
    ));

    goal_buttons(ui, rect, state, feed);
}

/// The two presses a goal needs, over the map's bottom edge. The gates are checked at the
/// last press, against what's true then.
fn goal_buttons(
    ui: &mut egui::Ui,
    map: egui::Rect,
    state: &mut UiState,
    feed: &mut dyn feed::Feed,
) {
    let row = egui::Rect::from_min_max(
        egui::pos2(map.left() + 6.0, map.bottom() - 34.0),
        egui::pos2(map.right() - 6.0, map.bottom() - 4.0),
    );
    ui.scope_builder(egui::UiBuilder::new().max_rect(row), |ui| {
        ui.horizontal(|ui| match state.goal {
            Goal::None => {
                ui.label("no goal");
            }
            Goal::Picked(goal) => {
                if ui.button("DRIVE HERE").clicked() {
                    state.goal = Goal::Armed(goal);
                }
                if ui.button("Cancel").clicked() {
                    state.goal = Goal::None;
                }
            }
            Goal::Armed(goal) => {
                if ui.button("CONFIRM").clicked() {
                    state.goal = confirm(state, feed, goal);
                }
                if ui.button("Cancel").clicked() {
                    state.goal = Goal::None;
                }
            }
            Goal::Driving(_) => {
                if ui.button("Clear the marker").clicked() {
                    state.goal = Goal::None;
                }
                ui.label("cancelling Nav2's goal isn't built yet");
            }
        });
    });
}

/// A click and the two presses at once, for `--click-goal`.
pub fn click_and_confirm(state: &mut UiState, feed: &mut dyn feed::Feed, at: Point) {
    match feed::refusal(at, state.world.map.grid.as_ref()) {
        None => state.goal = confirm(state, feed, at),
        Some(why) => state
            .world
            .push_line(Level::Warn, format!("no goal: {why}")),
    }
}

/// The last press: every gate, then the goal.
fn confirm(state: &mut UiState, feed: &mut dyn feed::Feed, at: Point) -> Goal {
    let world = &mut state.world;
    let sent = feed::command_allowed(feed.may_command(), &world.origins)
        .and_then(|()| feed.send_goal(feed::goal_pose(world.car_map, at)));
    match sent {
        Ok(()) => {
            world.note(format!("goal sent: x {:.1}, y {:.1}", at.x, at.y));
            Goal::Driving(at)
        }
        Err(why) => {
            world.push_line(Level::Error, format!("goal not sent: {why}"));
            Goal::None
        }
    }
}

fn corner_panel(ui: &mut egui::Ui, state: &mut UiState) {
    ui.horizontal(|ui| {
        ui.selectable_value(&mut state.tab, Tab::Keys, "KEYS");
        ui.selectable_value(&mut state.tab, Tab::Algorithms, "ALGORITHMS");
    });
    ui.separator();
    egui::ScrollArea::vertical()
        .auto_shrink(false)
        .show(ui, |ui| match state.tab {
            Tab::Keys => keys_tab(ui, state),
            Tab::Algorithms => algorithms_tab(ui, state),
        });
}

fn keys_tab(ui: &mut egui::Ui, state: &UiState) {
    let on = |value: bool| if value { "on" } else { "off" };
    let layers = state.layers;
    let rows = [
        ("G", "road cubes", on(layers.road)),
        ("V", "outline every live cube", on(layers.nav2_cubes)),
        (
            "N",
            "NDT's cells: dark, light when the lidar agrees (off: raw cubes)",
            on(layers.ndt_cubes),
        ),
        ("O", "costmap", on(layers.costmap)),
        ("M", "NDT's map", on(layers.ndt_map)),
        ("S", "cubes on the map", on(layers.scan)),
        ("P", "plan", on(layers.plan)),
        ("C", "camera", state.camera.label()),
        ("R", "reset the camera", ""),
    ];
    egui::Grid::new("keys")
        .num_columns(3)
        .striped(true)
        .show(ui, |ui| {
            for (key, what, value) in rows {
                ui.label(egui::RichText::new(key).strong());
                ui.label(what);
                ui.label(value);
                ui.end_row();
            }
        });
}

fn algorithms_tab(ui: &mut egui::Ui, state: &mut UiState) {
    egui::Grid::new("algorithms").num_columns(2).show(ui, |ui| {
        for (row, (name, choices)) in ALGORITHMS.iter().enumerate() {
            ui.label(*name);
            egui::ComboBox::from_id_salt(name).show_index(
                ui,
                &mut state.picks[row],
                choices.len(),
                |i| choices.get(i).copied().unwrap_or(""),
            );
            ui.end_row();
        }
    });
    ui.add_enabled(false, egui::Button::new("SWAP (not built yet)"));
}
