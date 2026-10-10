# vendor/: other people's source, to look things up

Not ours, and not in git. Only this README and the lists are committed.
`pixi run vendor` downloads what the lists name, at the exact commits.

| List | Lands in | What's in it | Size |
|---|---|---|---|
| `ros2-src.repos` | `vendor/ros2-src/` | ROS 2 Jazzy's own source (`core/`), and the stock packages we use (`ecosystem/`): Nav2, robot_localization, ros_gz, twist_mux and more | about 550 MB |
| `ros2-rust.repos` | `vendor/ros2-rust/` | rclrs (ROS in Rust), its examples, and its build tools | about 13 MB |

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
| `python3 tools/vendor.py --check` | says what's there, what's missing, and what's at another commit |
| `python3 tools/vendor.py --freeze ros2-src` | pins what's checked out now, to update a list |
