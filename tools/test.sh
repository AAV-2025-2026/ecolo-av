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

echo "== the stand-ins stay on this computer"
# turtle, sim, bench and view must never meet a real car on the same network and domain.
python3 - <<'PY'
import re
import sys
tasks = dict(re.findall(r'^([\w-]+) = \{ cmd = "([^"]*)"', open('pixi.toml').read(), re.M))
bad = [t for t in ('turtle', 'sim', 'bench', 'bench-check', 'view')
       if not tasks.get(t, '').startswith('tools/ros.sh --local ')]
sys.exit(f'these pixi tasks need "tools/ros.sh --local": {bad}' if bad else None)
PY
if [[ -f install/setup.bash ]]; then
  got=$(env -u ROS_AUTOMATIC_DISCOVERY_RANGE ROS_STATIC_PEERS=192.0.2.1 tools/ros.sh --local \
        bash -c 'echo "$ROS_AUTOMATIC_DISCOVERY_RANGE ${ROS_STATIC_PEERS:-no-peers}"')
  [[ "$got" == "LOCALHOST no-peers" ]] || { echo "tools/ros.sh --local gave: $got"; exit 1; }
  got=$(ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET tools/ros.sh --local \
        bash -c 'echo "$ROS_AUTOMATIC_DISCOVERY_RANGE"')
  [[ "$got" == "SUBNET" ]] || { echo "tools/ros.sh --local overrode SUBNET: $got"; exit 1; }
fi
# The keyboard with --sim or --local stays here too (a stand-in ros2 prints what it got).
stub=$(mktemp -d)
trap 'rm -rf "$stub"' EXIT
printf '#!/usr/bin/env bash\necho "${ROS_AUTOMATIC_DISCOVERY_RANGE:-unset} ${ROS_STATIC_PEERS:-no-peers}"\n' \
  > "$stub/ros2"
chmod +x "$stub/ros2"
for flag in --sim --local; do
  got=$(env -u ROS_AUTOMATIC_DISCOVERY_RANGE ROS_STATIC_PEERS=192.0.2.1 PATH="$stub:$PATH" \
        tools/keyboard.sh $flag)
  [[ "$got" == "LOCALHOST no-peers" ]] || { echo "tools/keyboard.sh $flag gave: $got"; exit 1; }
done
echo "they do"

echo "== docs/interfaces.md"
python3 tools/gen_interfaces_md.py --check && echo "in sync"
