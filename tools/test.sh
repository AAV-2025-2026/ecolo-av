#!/usr/bin/env bash
# Run every test that doesn't need ROS: our packages' Python unit tests, the Rust spine
# library, and the check that docs/interfaces.md matches docs/interfaces.yaml.
# Needs Python 3 with pytest and PyYAML, and Rust (cargo). Works on any OS.
#
# usage: tools/test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1

# Each package's tests import the package, so pytest runs from inside it.
# (aav_gazebo's test imports ROS messages, so only `colcon test` runs it.)
for pkg in src/ego/aav_ego src/backends/aav_spine src/backends/aav_legacy \
           src/drivers/aav_scripted src/aav_description; do
  echo "== $pkg"
  (cd "$pkg" && python3 -m pytest -q -p no:cacheprovider)
done

echo "== firmware/spine"
(cd firmware/spine && cargo test -q)

echo "== docs/interfaces.md"
python3 tools/gen_interfaces_md.py --check && echo "in sync"
