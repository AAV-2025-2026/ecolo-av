#!/usr/bin/env bash
# The HUD app's checks, in hud/flutter_pi: flutter pub get, flutter analyze, flutter test,
# then the app's own client code against the back end's real web server.
# Needs the Flutter SDK in vendor/flutter (pixi run get-flutter). Uses no network beyond
# this computer.
#
# usage: tools/hud_test.sh      (or: pixi run hud-test)
#
# - pub get must leave pubspec.lock as it is, and takes the packages from the cache that
#   get-flutter filled. To change a dependency: pixi run flutter pub get, then commit
#   pubspec.lock.
# - analyze fails on errors only. The infos it lists, and the warning about
#   assets/databases/ (pixi run get-hud-map), come from the 2025-26 code (docs/hud.md).
# - Last, test_bench against tools/hud_fake_backend.py: web.py with a fake car, on a free
#   port of 127.0.0.1. Real Socket.IO and HTTP on both sides, so an app and a back end
#   that can't talk fail here. Needs Flask-SocketIO and simple-websocket: pixi has them.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root/hud/flutter_pi"
../../tools/flutter.sh pub get --offline --enforce-lockfile
../../tools/flutter.sh analyze --no-fatal-infos --no-fatal-warnings
../../tools/flutter.sh test

echo "-- the app's client code against the back end's web server, with a fake car"
if ! python3 -c 'import flask_socketio, simple_websocket' 2> /dev/null; then
  echo "skipped: this python3 has no Flask-SocketIO or simple-websocket (use pixi run)"
  exit 0
fi
log=$(mktemp "${TMPDIR:-/tmp}/hud-fake-backend.XXXXXX")
python3 "$root/tools/hud_fake_backend.py" > "$log" 2>&1 &
server=$!
disown "$server"     # no "Terminated" line when the trap stops it
trap 'kill "$server" 2> /dev/null; rm -f "$log"' EXIT
port=
for _ in $(seq 1 100); do
  port=$(sed -n 's/^port \([0-9]*\)$/\1/p' "$log")
  if [[ -n $port ]] && curl -fsS "http://127.0.0.1:$port/" > /dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
if [[ -z $port ]]; then
  echo "the fake back end didn't start:" >&2
  cat "$log" >&2
  exit 1
fi
../../tools/flutter.sh test test_bench --dart-define=HUD_BACKEND="http://127.0.0.1:$port"
