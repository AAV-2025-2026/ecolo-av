# Provenance

Written for `aav` on 2026-10-09 and 10: a Rust rewrite of `src/sensors/yahboom_imu_cpp`,
which was copied from github.com/AAV-2025-2026/yahboom-IMU @ main (95469f1a63).

| Part | From the C++ driver |
|---|---|
| `crates/yahboom-protocol` | the frame layout, the units and the scale factors in `src/imu_node.cpp` |
| `crates/imu-node` | the node name, parameters, topics and covariances. Where it differs, on purpose, is listed at the top of `src/main.rs` |
| `test/compare_with_cpp.py` | checks both drivers against the C++ formulas, with the same bytes |

## Changes

- 2026-10-10: `test/compare_with_cpp.py` reads CPU time with `ps` where there's no `/proc`
  (macOS); `pixi run imu-compare` runs it.
- 2026-10-10: `test/compare_with_cpp.py` stops with the driver's own message if a driver
  exits at start-up, instead of waiting forever on its port. On a Mac the Rust driver
  can't open the script's fake port (macOS's baud-rate call fails on it), so the
  comparison runs on Linux. A real USB port should accept that call: untested on a Mac.
