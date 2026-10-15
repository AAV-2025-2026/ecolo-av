#!/usr/bin/env bash
# Download the place database, ottawa.db, into maps/places/ (the map window's place
# search reads it there), and put the same file where the 2025-26 Flutter app wants it,
# hud/flutter_pi/assets/databases/. Both stay out of git: GitHub warns at 50 MB.
#
# usage: tools/get_hud_map.sh      (or: pixi run get-hud-map)
#
# ottawa.db: 51 MB of SQLite, one table of 606,628 named places around Ottawa. The
# 2025-26 team made it from OpenStreetMap, so the data is © OpenStreetMap contributors,
# under the ODbL. It comes from their public repo (AAV-2025-2026/User-Interface), at the
# last commit that changed it. Downloaded once: the Flutter copy is a hard link (or a
# copy, across disks), and a file already in the Flutter folder is moved, not fetched.
set -euo pipefail
cd "$(dirname "$0")/.."
file=maps/places/ottawa.db
flutter=hud/flutter_pi/assets/databases/ottawa.db
mkdir -p "$(dirname "$file")" "$(dirname "$flutter")"
commit=ea5adc325f159965d11d7c39dc87594d62d5b7a0
url=https://raw.githubusercontent.com/AAV-2025-2026/User-Interface/$commit/flutter_pi/assets/databases/ottawa.db
sum=ff33dd2fc9301f6752b239cfa8c6ba3a7c5af539dff583e8a34eace3ee858fd5

sha256() {
  if command -v sha256sum >/dev/null; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

if [[ ! -f $file && -f $flutter ]]; then
  # Fetched before into the Flutter folder only: move it, no second download.
  mv "$flutter" "$file"
fi
if [[ ! -f $file ]]; then
  curl -fL --retry 3 -o "$file.part" "$url"
  mv "$file.part" "$file"
fi
if [[ $(sha256 "$file") != "$sum" ]]; then
  echo "$file isn't the expected download: delete it and run this again" >&2
  exit 1
fi
if [[ ! $file -ef $flutter ]]; then
  rm -f "$flutter"
  ln "$file" "$flutter" 2>/dev/null || cp "$file" "$flutter"
fi
echo "$file: ok (and $flutter)"
