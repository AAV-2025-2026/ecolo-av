#!/usr/bin/env bash
# Run the Flutter SDK in vendor/flutter (tools/get_flutter.sh), with its analytics off, and
# its state inside vendor/flutter where Flutter allows it, not in the home folder.
#
# usage: tools/flutter.sh <flutter arguments>      e.g. tools/flutter.sh doctor
#        pixi run flutter <arguments>              the same, run in hud/flutter_pi
#
# Works with or without Pixi. To build the app for Linux, run it outside Pixi: Pixi's
# compilers and pkg-config don't see the system's GTK.
#
# What it sets, for Flutter and the programs it starts:
#   FLUTTER_SUPPRESS_ANALYTICS        no analytics, without changing the user's settings
#                                     (`flutter config --no-analytics` would change them)
#   PUB_CACHE                         packages from pub.dev: vendor/flutter/.pub-cache,
#                                     not ~/.pub-cache
#   XDG_CONFIG_HOME                   Flutter's settings and tool state, not ~/.config/flutter
#   ANALYZER_STATE_LOCATION_OVERRIDE  the Dart analyzer's cache, not ~/.dartServer
# The last two go in vendor/flutter/bin/cache, which Flutter's own .gitignore ignores.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
sdk=$root/vendor/flutter
if [[ ! -x $sdk/bin/flutter ]]; then
  echo "No Flutter in vendor/flutter yet: run 'pixi run get-flutter' first." >&2
  exit 1
fi
export FLUTTER_SUPPRESS_ANALYTICS=true
export PUB_CACHE=$sdk/.pub-cache
export XDG_CONFIG_HOME=$sdk/bin/cache/aav-config
export ANALYZER_STATE_LOCATION_OVERRIDE=$sdk/bin/cache/aav-dartServer
mkdir -p "$PUB_CACHE" "$XDG_CONFIG_HOME" "$ANALYZER_STATE_LOCATION_OVERRIDE"
exec "$sdk/bin/flutter" "$@"
