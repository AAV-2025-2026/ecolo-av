//! map: the big screen's map window. One program: a raylib window, and the ROS node `map`.
//!
//! Subscribes  (names from config/map.yaml, or ROS parameters)
//!             map_topic     nav_msgs/OccupancyGrid       latched: Nav2's map, drawn north up
//!             odom_topic    nav_msgs/Odometry            the car, in the map frame, and its speed
//!             plan_topic    nav_msgs/Path                Nav2's plan: the line, the distance left
//!             goal_topic    geometry_msgs/PoseStamped    RViz's goal, until Nav2 plans for it
//!             source_topic  aav_interfaces/DataSource    latched: the SIMULATED banner
//! Publishes   nothing
//! Parameters  the topics above, stale_after, plan_stale_after (s), arrive_within (m)
//!
//! raylib owns the main thread (macOS needs that); rclrs spins on its own thread and
//! sends news over a channel (ros.rs). `--demo` swaps the ROS node for pretend data.
//! The maths (map to screen, the distance left) is in map-core.
//!
//! usage: map [--demo] [--fullscreen] [--whole-map] [--config FILE] [--vehicle FILE] [--screenshot FILE]
//!            [--ros-args ...]

mod demo;
#[cfg(feature = "ros")]
mod ros;
mod source;
mod ui;

use std::{
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

use anyhow::{bail, Context as _, Result};
use map_core::{
    car::CarShape,
    config::MapConfig,
    state::MapState,
    view::{ScreenPoint, View},
};
use raylib::prelude::*;

use crate::{
    demo::Demo,
    source::DataSource,
    ui::{Layout, Ui},
};

const USAGE: &str = "\
usage: map [--demo] [--fullscreen] [--whole-map] [--config FILE] [--vehicle FILE] [--screenshot FILE]
           [--ros-args ...]

  --demo             pretend data: no ROS, no car
  --fullscreen       fill the screen (F11 switches too)
  --whole-map        start showing the whole map, not following the car (F switches)
  --config FILE      topic names from FILE instead of the built-in config/map.yaml
  --vehicle FILE     the car's size from FILE instead of the built-in vehicle.yaml
  --screenshot FILE  save the window as a PNG after 4 s, then quit (for the docs)
  --ros-args ...     passed to ROS, e.g. --ros-args -p plan_topic:=/plan

keys: F follow the car / whole map, + - or the wheel zoom, drag to move, F11 full screen";

/// When --screenshot saves its picture: once the data has had time to arrive.
const SCREENSHOT_AFTER: Duration = Duration::from_secs(4);
/// One click of the mouse wheel, or one press of + or -.
const WHEEL_ZOOM: f64 = 1.15;
const KEY_ZOOM: f64 = 1.25;

/// The command line, before `--ros-args`.
#[derive(Debug, Default)]
struct Options {
    demo: bool,
    fullscreen: bool,
    whole_map: bool,
    config: Option<PathBuf>,
    vehicle: Option<PathBuf>,
    screenshot: Option<PathBuf>,
}

impl Options {
    /// Reads our own options; stops at `--ros-args`, which belongs to ROS.
    fn parse(args: &[String]) -> Result<Self> {
        let mut opts = Self::default();
        let mut it = args.iter().skip(1);
        while let Some(arg) = it.next() {
            let mut file = |what: &str| -> Result<PathBuf> {
                Ok(it
                    .next()
                    .with_context(|| format!("{what} needs a file"))?
                    .into())
            };
            match arg.as_str() {
                "--ros-args" => break,
                "--demo" => opts.demo = true,
                "--fullscreen" => opts.fullscreen = true,
                "--whole-map" => opts.whole_map = true,
                "--config" => opts.config = Some(file("--config")?),
                "--vehicle" => opts.vehicle = Some(file("--vehicle")?),
                "--screenshot" => opts.screenshot = Some(file("--screenshot")?),
                "-h" | "--help" => {
                    println!("{USAGE}");
                    std::process::exit(0);
                }
                other => bail!("unknown option {other:?}\n{USAGE}"),
            }
        }
        Ok(opts)
    }
}

fn read(path: &Path) -> Result<String> {
    std::fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let opts = Options::parse(&args)?;
    let config = match &opts.config {
        Some(path) => {
            MapConfig::from_yaml(&read(path)?).with_context(|| format!("in {}", path.display()))?
        }
        None => MapConfig::default(),
    };
    let car = match &opts.vehicle {
        Some(path) => CarShape::from_vehicle_yaml(&read(path)?)
            .with_context(|| format!("in {}", path.display()))?,
        None => CarShape::default(),
    };
    let (source, config) = open_source(&opts, args, config)?;
    run(&opts, source, config, car)
}

/// The demo, or the ROS node (which may rename topics from its parameters).
fn open_source(
    opts: &Options,
    args: Vec<String>,
    config: MapConfig,
) -> Result<(Box<dyn DataSource>, MapConfig)> {
    if opts.demo {
        return Ok((Box::new(Demo::new(Instant::now())), config));
    }
    #[cfg(feature = "ros")]
    {
        let (source, config) = ros::RosSource::start(args, config)?;
        Ok((Box::new(source), config))
    }
    #[cfg(not(feature = "ros"))]
    {
        let _ = (args, config);
        bail!("this map was built without ROS (--no-default-features): run it with --demo")
    }
}

/// The window's loop: news in, keys and mouse, one frame drawn.
fn run(
    opts: &Options,
    mut source: Box<dyn DataSource>,
    config: MapConfig,
    car: CarShape,
) -> Result<()> {
    let (mut rl, thread) = raylib::init()
        .size(1600, 900)
        .title("AAV map")
        .resizable()
        .msaa_4x()
        .highdpi()
        .log_level(TraceLogLevel::LOG_WARNING)
        .build();
    // Escape would close the map by accident; the window's close button still does.
    rl.set_exit_key(None);
    rl.set_target_fps(30);
    rl.set_window_min_size(800, 450);
    if opts.fullscreen {
        toggle_fullscreen(&mut rl);
    }
    let mut ui = Ui::new(&mut rl, &thread);
    let mut state = MapState::new(config);
    let mut view = View::default();
    if opts.whole_map {
        view.toggle_follow();
    }
    let mut dragging = false;
    let started = Instant::now();

    while !rl.window_should_close() && !source.has_stopped() {
        let now = Instant::now();
        for update in source.drain(now) {
            state.apply(update, now);
        }
        if state.take_grid_change() {
            if let Some(grid) = &state.grid {
                if let Err(e) = ui.upload(&mut rl, &thread, grid) {
                    state.map_problem = Some(format!("can't show the map: {e}"));
                }
            }
        }

        let banner = state.origins.banner().is_some();
        let layout = Layout::new(rl.get_screen_width(), rl.get_screen_height(), banner);
        let vp = layout.map;
        let mouse = rl.get_mouse_position();
        let mouse = ScreenPoint::new(f64::from(mouse.x), f64::from(mouse.y));
        let over_map = vp.contains(mouse);
        if rl.is_key_pressed(KeyboardKey::KEY_F11) {
            toggle_fullscreen(&mut rl);
        }
        if rl.is_key_pressed(KeyboardKey::KEY_F) {
            view.toggle_follow();
        }
        let wheel = rl.get_mouse_wheel_move();
        if wheel != 0.0 && over_map {
            view.zoom(WHEEL_ZOOM.powf(f64::from(wheel)), Some(mouse), &vp);
        }
        let zoom_in = [KeyboardKey::KEY_EQUAL, KeyboardKey::KEY_KP_ADD];
        let zoom_out = [KeyboardKey::KEY_MINUS, KeyboardKey::KEY_KP_SUBTRACT];
        if zoom_in.into_iter().any(|k| rl.is_key_pressed(k)) {
            view.zoom(KEY_ZOOM, None, &vp);
        }
        if zoom_out.into_iter().any(|k| rl.is_key_pressed(k)) {
            view.zoom(1.0 / KEY_ZOOM, None, &vp);
        }
        // Drag to move: only a drag that starts on the map.
        if rl.is_mouse_button_pressed(MouseButton::MOUSE_BUTTON_LEFT) {
            dragging = over_map;
        }
        if !rl.is_mouse_button_down(MouseButton::MOUSE_BUTTON_LEFT) {
            dragging = false;
        }
        if dragging {
            let d = rl.get_mouse_delta();
            view.pan(f64::from(d.x), f64::from(d.y));
        }
        let car_centre = state.car.as_ref().map(|c| car.centre(c.pose));
        let map_bounds = state.grid.as_ref().map(|g| g.info.bounds());
        view.update(car_centre, map_bounds, &vp);

        let label = source.label();
        let mut d = rl.begin_drawing(&thread);
        ui.draw(&mut d, &state, &view, &car, now, label);
        drop(d);

        if let Some(path) = &opts.screenshot {
            if now.duration_since(started) > SCREENSHOT_AFTER {
                save_screenshot(&mut rl, &thread, path)?;
                break;
            }
        }
    }
    Ok(())
}

/// Full screen at the monitor's own size, or back to a window.
fn toggle_fullscreen(rl: &mut RaylibHandle) {
    if !rl.is_window_fullscreen() {
        let m = raylib::core::window::get_current_monitor();
        let (w, h) = (
            raylib::core::window::get_monitor_width(m),
            raylib::core::window::get_monitor_height(m),
        );
        rl.set_window_size(w, h);
    }
    rl.toggle_fullscreen();
}

/// Saves what the window shows as a PNG. (raylib's own take_screenshot only writes into
/// the folder the program started in.)
fn save_screenshot(rl: &mut RaylibHandle, thread: &RaylibThread, path: &Path) -> Result<()> {
    let path = std::path::absolute(path)?;
    let name = path
        .to_str()
        .context("--screenshot: the path must be UTF-8")?;
    rl.load_image_from_screen(thread).export_image(name);
    if !path.exists() {
        bail!("raylib couldn't write {name}");
    }
    println!("saved {name}");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(list: &[&str]) -> Vec<String> {
        std::iter::once("map")
            .chain(list.iter().copied())
            .map(String::from)
            .collect()
    }

    #[test]
    fn options_stop_at_ros_args() {
        let o = Options::parse(&args(&["--demo", "--ros-args", "--whatever"])).expect("valid");
        assert!(o.demo);
        assert!(!o.fullscreen);
    }

    #[test]
    fn options_take_files() {
        let o = Options::parse(&args(&["--vehicle", "v.yaml", "--screenshot", "a.png"]))
            .expect("valid");
        assert_eq!(o.vehicle, Some(PathBuf::from("v.yaml")));
        assert_eq!(o.screenshot, Some(PathBuf::from("a.png")));
        assert!(Options::parse(&args(&["--config"])).is_err());
        assert!(Options::parse(&args(&["--bogus"])).is_err());
    }
}
