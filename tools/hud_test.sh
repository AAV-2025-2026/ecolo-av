#!/usr/bin/env bash
# The HUD app's checks, in hud/flutter_pi: flutter pub get, flutter analyze, flutter test.
# Needs the Flutter SDK in vendor/flutter (pixi run get-flutter). Uses no network.
#
# usage: tools/hud_test.sh      (or: pixi run hud-test)
#
# - pub get must leave pubspec.lock as it is, and takes the packages from the cache that
#   get-flutter filled. To change a dependency: pixi run flutter pub get, then commit
#   pubspec.lock.
# - analyze fails on errors only. The infos it lists, and the warning about
#   assets/databases/ (pixi run get-hud-map), come from the 2025-26 code (docs/hud.md).
set -euo pipefail
cd "$(dirname "$0")/../hud/flutter_pi"
../../tools/flutter.sh pub get --offline --enforce-lockfile
../../tools/flutter.sh analyze --no-fatal-infos --no-fatal-warnings
../../tools/flutter.sh test
