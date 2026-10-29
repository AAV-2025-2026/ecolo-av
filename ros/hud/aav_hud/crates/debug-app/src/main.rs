//! debug_hud: the debug screen. One program: a raylib window, and the ROS node `debug_hud`.
//!
//! What the car sees and what it thinks (docs/designs/2026-10-29_debug-hud.md): the
//! lidar's cubes round the car in 3D, where each localizer puts the car (EKF local and
//! global, AMCL, Gazebo's truth), Nav2's plan, and a panel of every sensor and actuator
//! straight from its own topic.
//!
//! Subscribes  (names from config/debug_hud.yaml, or ROS parameters)
//!             lidar_topic           sensor_msgs/PointCloud2     reliable, keep last 1: the cubes
//!             local_odom_topic      nav_msgs/Odometry           odom: the car; places the cubes
//!             global_odom_topic     nav_msgs/Odometry           map: EKF global
//!             truth_topic           nav_msgs/Odometry           map: Gazebo's truth (sim)
//!             amcl_topic            geometry_msgs/PoseWithCovarianceStamped  map: AMCL
//!             plan_topic            nav_msgs/Path               Nav2's plan
//!             tf_topic, tf_static_topic  tf2_msgs/TFMessage     map -> odom; base_link -> lidar_link
//!             imu_topic             sensor_msgs/Imu             the panel
//!             gps_topic             sensor_msgs/NavSatFix       the panel
//!             wheels_topic          aav_interfaces/WheelSpeeds  the panel
//!             wheel_odom_topic      nav_msgs/Odometry           the panel
//!             vehicle_status_topic  aav_interfaces/VehicleStatus  the panel: mode, armed, steering
//!             track_status_topic    diagnostic_msgs/DiagnosticStatus  the panel: the trial tracker
//!             source_topic          aav_interfaces/DataSource   latched: the SIMULATED banner
//! Publishes   nothing. It never touches an actuator (the design's D3).
//! Parameters  the topics above; odom_frame, base_frame, map_frame; stale_after (s),
//!             cube_size (m), max_cubes, pose_window (s), ground_height (m)
//!
//! raylib owns the main thread (macOS needs that); rclrs spins on its own thread; clouds
//! go to a thread of their own through a newest-only slot (ros.rs). `--demo` swaps the
//! ROS node for pretend data. The maths is in debug-core.
//!
//! usage: debug_hud [--demo] [--fullscreen] [--monitor NAME|N] [--list-monitors]
//!                  [--config FILE] [--vehicle FILE] [--screenshot FILE [--after S]]
//!                  [--bench-cubes N] [--ros-args ...]

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
use debug_core::{config::DebugConfig, orbit::Orbit, state::DebugState};
use hud_app::window;
use hud_core::screen::Monitor;
use map_core::car::CarShape;
use raylib::prelude::*;

use crate::{
    demo::Demo,
    source::DataSource,
    ui::{Frame, Ui, PANEL_W},
};

const USAGE: &str = "\
usage: debug_hud [--demo] [--fullscreen] [--monitor NAME|N] [--list-monitors]
                 [--config FILE] [--vehicle FILE] [--screenshot FILE [--after S]]
                 [--bench-cubes N] [--ros-args ...]

  --demo             pretend data: no ROS, no car
  --fullscreen       fill the screen (F11 switches too)
  --monitor NAME|N   open on this monitor: its name exactly, or its number (0 = the first)
  --list-monitors    print the monitors' numbers, names and sizes, then quit
  --config FILE      topic names from FILE instead of the built-in config/debug_hud.yaml
  --vehicle FILE     the car's size from FILE instead of the built-in vehicle.yaml
  --screenshot FILE  save the window as a PNG after --after seconds (4), then quit
  --bench-cubes N    the drawing test (with --demo): N cubes; prints the frame rate over
                     10 s, then quits
  --ros-args ...     passed to ROS, e.g. --ros-args -p lidar_topic:=/x

keys: drag turn, right-drag (or shift-drag) move, wheel zoom, C chase / follow / free,
      R reset the camera, F11 full screen";

/// The drawing test: settle, then measure for this long.
const BENCH_SETTLE: Duration = Duration::from_secs(2);
const BENCH_MEASURE: Duration = Duration::from_secs(10);
/// One click of the mouse wheel.
const WHEEL_ZOOM: f32 = 1.12;

/// The command line, before `--ros-args`.
#[derive(Debug, Default)]
struct Options {
    demo: bool,
    fullscreen: bool,
    monitor: Option<Monitor>,
    list_monitors: bool,
    config: Option<PathBuf>,
    vehicle: Option<PathBuf>,
    screenshot: Option<PathBuf>,
    after: Option<f64>,
    bench_cubes: Option<usize>,
}

impl Options {
    /// Reads our own options; stops at `--ros-args`, which belongs to ROS.
    fn parse(args: &[String]) -> Result<Self> {
        let mut opts = Self::default();
        let mut it = args.iter().skip(1);
        while let Some(arg) = it.next() {
            let mut value = |what: &str| -> Result<String> {
                Ok(it
                    .next()
                    .with_context(|| format!("{what} needs a value"))?
                    .clone())
            };
            match arg.as_str() {
                "--ros-args" => break,
                "--demo" => opts.demo = true,
                "--fullscreen" => opts.fullscreen = true,
                "--list-monitors" => opts.list_monitors = true,
                "--monitor" => opts.monitor = Some(value("--monitor")?.parse()?),
                "--config" => opts.config = Some(value("--config")?.into()),
                "--vehicle" => opts.vehicle = Some(value("--vehicle")?.into()),
                "--screenshot" => opts.screenshot = Some(value("--screenshot")?.into()),
                "--after" => {
                    let s: f64 = value("--after")?
                        .parse()
                        .context("--after: seconds, such as 20")?;
                    if !(s.is_finite() && s >= 0.0) {
                        bail!("--after must be 0 or more seconds");
                    }
                    opts.after = Some(s);
                }
                "--bench-cubes" => {
                    let n: usize = value("--bench-cubes")?
                        .parse()
                        .context("--bench-cubes: a number of cubes, such as 20000")?;
                    if n == 0 {
                        bail!("--bench-cubes needs at least one cube");
                    }
                    opts.bench_cubes = Some(n);
                }
                "-h" | "--help" => {
                    println!("{USAGE}");
                    std::process::exit(0);
                }
                other => bail!("unknown option {other:?}\n{USAGE}"),
            }
        }
        if opts.bench_cubes.is_some() && !opts.demo {
            bail!("--bench-cubes needs --demo");
        }
        if opts.after.is_some() && opts.screenshot.is_none() {
            bail!("--after needs --screenshot");
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
    if opts.list_monitors {
        window::print_monitors();
        return Ok(());
    }
    let config = match &opts.config {
        Some(path) => DebugConfig::from_yaml(&read(path)?)
            .with_context(|| format!("in {}", path.display()))?,
        None => DebugConfig::default(),
    };
    let car = match &opts.vehicle {
        Some(path) => CarShape::from_vehicle_yaml(&read(path)?)
            .with_context(|| format!("in {}", path.display()))?,
        None => CarShape::default(),
    };
    let (source, config) = open_source(&opts, args, config)?;
    run(&opts, source, &config, car)
}

/// The demo, or the ROS node (which may rename topics from its parameters).
fn open_source(
    opts: &Options,
    args: Vec<String>,
    config: DebugConfig,
) -> Result<(Box<dyn DataSource>, DebugConfig)> {
    if opts.demo {
        let demo = Demo::new(Instant::now(), config.cube_settings(), opts.bench_cubes);
        return Ok((Box::new(demo), config));
    }
    #[cfg(feature = "ros")]
    {
        let (source, config) = ros::RosSource::start(args, config)?;
        Ok((Box::new(source), config))
    }
    #[cfg(not(feature = "ros"))]
    {
        let _ = (args, config);
        bail!("this debug_hud was built without ROS (--no-default-features): run it with --demo")
    }
}

/// The window's loop: news in, the mouse, one frame drawn.
fn run(
    opts: &Options,
    mut source: Box<dyn DataSource>,
    config: &DebugConfig,
    car: CarShape,
) -> Result<()> {
    let (mut rl, thread) = raylib::init()
        .size(1600, 900)
        .title("AAV debug HUD")
        .resizable()
        .msaa_4x()
        .highdpi()
        .log_level(TraceLogLevel::LOG_WARNING)
        .build();
    rl.set_exit_key(None);
    // The drawing test measures as fast as it can go; otherwise 60 is plenty.
    rl.set_target_fps(if opts.bench_cubes.is_some() { 0 } else { 60 });
    rl.set_window_min_size(1000, 600);
    window::place(&mut rl, opts.monitor.as_ref(), opts.fullscreen)?;
    let mut ui = Ui::new(&mut rl, &thread, car, config.cube_size as f32);
    let mut state = DebugState::new(config);
    let mut orbit = Orbit::default();
    let started = Instant::now();
    let screenshot_after = Duration::from_secs_f64(opts.after.unwrap_or(4.0));
    let mut bench = Bench::default();

    while !rl.window_should_close() && !source.has_stopped() {
        let now = Instant::now();
        for update in source.drain(now) {
            state.apply(update, now);
        }
        if let Some(scan) = source.take_scan() {
            state.set_scan(scan, now);
        }

        // The mouse, over the 3D view only.
        let view_w = rl.get_screen_width() as f32 - PANEL_W;
        let mouse = rl.get_mouse_position();
        let over_view = mouse.x < view_w;
        let shift = rl.is_key_down(KeyboardKey::KEY_LEFT_SHIFT)
            || rl.is_key_down(KeyboardKey::KEY_RIGHT_SHIFT);
        let delta = rl.get_mouse_delta();
        let left = rl.is_mouse_button_down(MouseButton::MOUSE_BUTTON_LEFT);
        let right = rl.is_mouse_button_down(MouseButton::MOUSE_BUTTON_RIGHT);
        if over_view && (right || (left && shift)) {
            orbit.pan(delta.x, delta.y);
        } else if over_view && left {
            orbit.rotate(delta.x, delta.y);
        }
        let wheel = rl.get_mouse_wheel_move();
        if over_view && wheel != 0.0 {
            orbit.zoom(WHEEL_ZOOM.powf(-wheel));
        }
        if rl.is_key_pressed(KeyboardKey::KEY_C) {
            orbit.switch_mode();
        }
        if rl.is_key_pressed(KeyboardKey::KEY_R) {
            orbit.reset();
        }
        if rl.is_key_pressed(KeyboardKey::KEY_F11) {
            window::toggle_fullscreen(&mut rl);
        }
        orbit.update(state.car());

        let fps = rl.get_fps();
        let label = source.label();
        let frame = Frame {
            now,
            label,
            orbit: &orbit,
            fps,
            bench: opts.bench_cubes,
        };
        let mut d = rl.begin_drawing(&thread);
        ui.draw(&mut d, &state, &frame);
        drop(d);

        if let Some(n) = opts.bench_cubes {
            if let Some(result) = bench.frame(now.duration_since(started)) {
                println!(
                    "debug_hud --bench-cubes {n}: {result:.1} fps over {} s (release build: {})",
                    BENCH_MEASURE.as_secs(),
                    !cfg!(debug_assertions)
                );
                break;
            }
        }
        if let Some(path) = &opts.screenshot {
            if now.duration_since(started) > screenshot_after {
                save_screenshot(&mut rl, &thread, path)?;
                break;
            }
        }
    }
    Ok(())
}

/// The drawing test's count: frames drawn after the settle time, over the measure time.
#[derive(Debug, Default)]
struct Bench {
    frames: u32,
    first: Option<Duration>,
}

impl Bench {
    /// One frame drawn at `t` since the start; the frame rate once it has measured.
    fn frame(&mut self, t: Duration) -> Option<f64> {
        if t < BENCH_SETTLE {
            return None;
        }
        let first = *self.first.get_or_insert(t);
        self.frames += 1;
        let span = t - first;
        (span >= BENCH_MEASURE).then(|| f64::from(self.frames - 1) / span.as_secs_f64())
    }
}

/// Saves what the window shows as a PNG.
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
        std::iter::once("debug_hud")
            .chain(list.iter().copied())
            .map(String::from)
            .collect()
    }

    #[test]
    fn options_stop_at_ros_args() {
        let o = Options::parse(&args(&["--demo", "--ros-args", "--bogus"])).expect("valid");
        assert!(o.demo);
    }

    #[test]
    fn options_check_their_values() {
        let o = Options::parse(&args(&["--demo", "--bench-cubes", "20000"])).expect("valid");
        assert_eq!(o.bench_cubes, Some(20_000));
        assert!(Options::parse(&args(&["--bench-cubes", "20000"])).is_err());
        assert!(Options::parse(&args(&["--demo", "--bench-cubes", "0"])).is_err());
        let o = Options::parse(&args(&["--screenshot", "a.png", "--after", "20"])).expect("valid");
        assert_eq!(o.after, Some(20.0));
        assert!(Options::parse(&args(&["--after", "2"])).is_err());
        assert!(Options::parse(&args(&["--bogus"])).is_err());
    }

    #[test]
    fn the_bench_counts_after_settling() {
        let mut b = Bench::default();
        assert_eq!(b.frame(Duration::from_secs(1)), None);
        for i in 0..=300 {
            let t = BENCH_SETTLE + Duration::from_millis(i * 1000 / 30);
            if let Some(fps) = b.frame(t) {
                assert!((fps - 30.0).abs() < 0.5, "{fps}");
                return;
            }
        }
        panic!("never finished");
    }
}
