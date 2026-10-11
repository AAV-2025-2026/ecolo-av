#!/usr/bin/env bash
# Download the HUD app's place database into hud/flutter_pi/assets/databases/. It stays
# out of git: GitHub warns at 50 MB.
#
# usage: tools/get_hud_map.sh      (or: pixi run get-hud-map)
#
# ottawa.db: 51 MB of SQLite, one table of 606,628 named places around Ottawa, for the
# app's destination search. The 2025-26 team made it from OpenStreetMap, so the data is
# © OpenStreetMap contributors, under the ODbL. It comes from their public repo
# (AAV-2025-2026/User-Interface), at the last commit that changed it.
set -euo pipefail
cd "$(dirname "$0")/.."
dir=hud/flutter_pi/assets/databases
mkdir -p "$dir"
file=$dir/ottawa.db
commit=ea5adc325f159965d11d7c39dc87594d62d5b7a0
url=https://raw.githubusercontent.com/AAV-2025-2026/User-Interface/$commit/flutter_pi/assets/databases/ottawa.db
sum=ff33dd2fc9301f6752b239cfa8c6ba3a7c5af539dff583e8a34eace3ee858fd5
if [[ ! -f $file ]]; then
  curl -fL --retry 3 -o "$file.part" "$url"
  mv "$file.part" "$file"
fi
if command -v sha256sum >/dev/null; then
  got=$(sha256sum "$file" | cut -d' ' -f1)
else
  got=$(shasum -a 256 "$file" | cut -d' ' -f1)
fi
if [[ $got != "$sum" ]]; then
  echo "$file isn't the expected download: delete it and run this again" >&2
  exit 1
fi
echo "$file: ok"
