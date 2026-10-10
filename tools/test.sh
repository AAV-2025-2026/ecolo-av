#!/usr/bin/env bash
# Run every test that doesn't need ROS: our packages' Python unit tests, the Rust spine
# library, and the check that docs/interfaces.md matches docs/interfaces.yaml.
# Needs Python 3 with pytest and PyYAML; Rust (cargo) for the spine. Works on any OS.
#
# usage: tools/test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1

# Each package's tests import the package, so pytest runs from inside it.
# (aav_gazebo's test imports ROS messages, so only `colcon test` runs it.)
for pkg in src/ego/aav_ego src/backends/aav_spine src/backends/aav_legacy \
           src/drivers/aav_scripted src/aav_description src/perception/aav_yolo \
           src/bench/aav_bench src/hud/aav_hud; do
  echo "== $pkg"
  (cd "$pkg" && python3 -m pytest -q -p no:cacheprovider)
done

echo "== firmware/spine"
if command -v cargo >/dev/null; then
  (cd firmware/spine && cargo test -q)
  # Every firmware crate must build without the standard library, for the Pico 2's chip.
  if [[ -d "$(rustc --print target-libdir --target thumbv8m.main-none-eabihf 2>/dev/null)" ]]; then
    echo "== firmware/spine, no_std, for the Pico 2 (thumbv8m.main-none-eabihf)"
    (cd firmware/spine && cargo build -q --target thumbv8m.main-none-eabihf -p spine-core \
       -p aav-inputs -p jrk-g2 -p ad5311 -p pca9555 -p ibus -p spine-board && echo "builds")
  fi
else
  echo "skipped: no cargo here (pixi run test has it; or install Rust with rustup)"
fi

echo "== docs/interfaces.md"
python3 tools/gen_interfaces_md.py --check && echo "in sync"
