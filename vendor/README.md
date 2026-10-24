# vendor/: other people's source, to look things up

Not ours, and not in git. Only this README and the lists are committed.
`pixi run vendor` downloads what the lists name, at the exact commits.

| List | Lands in | What's in it | Size |
|---|---|---|---|
| `ros2-src.repos` | `vendor/ros2-src/` | ROS 2 Jazzy's own source (`core/`), and the stock packages we use (`ecosystem/`): Nav2, robot_localization, ros_gz, twist_mux and more | about 550 MB |
| `ros2-rust.repos` | `vendor/ros2-rust/` | rclrs (ROS in Rust), its examples, and its build tools | about 13 MB |

PlatformIO keeps its downloads here too, in `vendor/platformio/` (about 1.5 GB): the
compilers and framework for today's C++ boards. `pixi run -e firmware legacy-esp32`
fills it.

Flutter lives here too, in `vendor/flutter/` (about 4.3 GB): Flutter 3.35.7, the SDK for
the HUD app (`hud/flutter_pi`). Its engine files are in `bin/cache/` (3.3 GB), and the
app's packages in `.pub-cache/` (0.24 GB). `pixi run get-flutter` fills it, checked by
the SHA-256 that Flutter publishes (docs/hud.md).

Espressif's QEMU lives here too, in `vendor/qemu/` (about 22 MB): the ESP32 emulator
(GPL-2.0, a tool only, never linked into our code) and its libgcrypt (LGPL-2.1+, from
conda-forge). `pixi run esp-qemu-tools` fills it, checked by the published SHA-256s; macOS
on Apple silicon only so far. `pixi run esp-qemu-check` uses it (docs/esp32-bench.md).

## Rules

- **Look, don't touch.** Never edit, build or commit anything in here. Our code lives in
  `src/`, `firmware/` and `tools/`.
- **colcon never builds it:** `vendor/COLCON_IGNORE` keeps it out of `pixi run build`.
- **git never tracks it:** `.gitignore` keeps only this README, the lists and
  `COLCON_IGNORE`.
- **Searching it:** most search tools skip folders that git ignores. Use
  `grep -r <word> vendor/`, or `rg -u <word> vendor/`.

## Commands

| Command | Does |
|---|---|
| `pixi run vendor` | downloads what's missing, at the pinned commits; leaves the rest alone |
| `pixi run get-flutter` | downloads Flutter 3.35.7 into `vendor/flutter/`, if it isn't there |
| `pixi run esp-qemu-tools` | downloads Espressif's QEMU and its libgcrypt into `vendor/qemu/` |
| `python3 tools/vendor.py --check` | says what's there, what's missing, and what's at another commit |
| `python3 tools/vendor.py --freeze ros2-src` | pins what's checked out now, to update a list |
