//! The window's place: which monitor, and full screen. Shared by `hud` and `map`, which
//! go on different screens of the same computer (the car's dash).
//!
//! The choice itself (a name or a number, exact matches only) is `hud_core::screen`, and
//! tested there. This is the raylib (GLFW) side.

use std::ffi::CStr;

use anyhow::{Context as _, Result};
use hud_core::screen::{Monitor, MonitorInfo};
use raylib::{core::window as w, prelude::*};

/// Every monitor raylib sees, in its order: the numbers `--monitor` takes.
///
/// Needs an open window (raylib starts GLFW with it).
pub fn monitors() -> Vec<MonitorInfo> {
    (0..w::get_monitor_count())
        .map(|i| {
            let at = w::get_monitor_position(i);
            MonitorInfo {
                name: monitor_name(i),
                width: w::get_monitor_width(i),
                height: w::get_monitor_height(i),
                x: at.x as i32,
                y: at.y as i32,
            }
        })
        .collect()
}

/// A monitor's name. Not raylib-rs's `get_monitor_name`: it takes ownership of GLFW's own
/// string and frees it (raylib 6.0.0), which corrupts the heap.
fn monitor_name(i: i32) -> String {
    // SAFETY: GetMonitorName returns GLFW's string for a monitor in range (or "" when out
    // of range), valid until the monitor is unplugged; it is copied out at once.
    let name = unsafe { raylib::ffi::GetMonitorName(i) };
    if name.is_null() {
        return String::new();
    }
    // SAFETY: non-null, NUL-terminated, owned by GLFW and not freed here.
    unsafe { CStr::from_ptr(name) }
        .to_string_lossy()
        .into_owned()
}

/// Puts the window on `monitor` (if given), then full screen there (if asked).
///
/// The window first moves to that monitor while it's still a window (X11, macOS), so
/// full screen fills the right one. Wayland can't move windows, and a window manager may
/// not have moved it yet: then full screen is asked for on that monitor directly.
pub fn place(rl: &mut RaylibHandle, monitor: Option<&Monitor>, fullscreen: bool) -> Result<()> {
    let target = match monitor {
        Some(m) => {
            let names: Vec<String> = monitors().into_iter().map(|m| m.name).collect();
            let index = m.find(&names)?;
            Some(i32::try_from(index).context("monitor number")?)
        }
        None => None,
    };
    if let Some(i) = target {
        rl.set_window_monitor(i);
    }
    if fullscreen {
        toggle_fullscreen(rl);
        if let Some(i) = target {
            if w::get_current_monitor() != i {
                rl.set_window_monitor(i);
            }
        }
    }
    Ok(())
}

/// Full screen at the monitor's own size, or back to a window.
pub fn toggle_fullscreen(rl: &mut RaylibHandle) {
    if !rl.is_window_fullscreen() {
        let m = w::get_current_monitor();
        rl.set_window_size(w::get_monitor_width(m), w::get_monitor_height(m));
    }
    rl.toggle_fullscreen();
}

/// `--list-monitors`: opens a hidden window (GLFW needs one), prints every monitor.
pub fn print_monitors() {
    let (_rl, _thread) = raylib::init()
        .size(320, 200)
        .hidden()
        .title("AAV monitors")
        .log_level(TraceLogLevel::LOG_WARNING)
        .build();
    print!("{}", hud_core::screen::listing(&monitors()));
}
