# Provenance

Copied on 2026-10-09 from github.com/AAV-2025-2026/User-Interface @ main (e6e6b1e565), flutter_pi.

Files, unchanged unless listed under Changes:

- `.gitignore`
- `.metadata`
- `README.md`
- `analysis_options.yaml`
- `lib/components/sockets/socket_services.dart`
- `lib/data/constants.dart`
- `lib/main.dart`
- `lib/models/place.dart`
- `lib/screens/camera_page.dart`
- `lib/screens/home_page.dart`
- `lib/screens/map_page.dart`
- `lib/services/database_service.dart`
- `lib/util/ipc.dart`
- `linux/.gitignore`
- `linux/CMakeLists.txt`
- `linux/flutter/CMakeLists.txt`
- `linux/runner/CMakeLists.txt`
- `linux/runner/main.cc`
- `linux/runner/my_application.cc`
- `linux/runner/my_application.h`
- `pubspec.lock`
- `pubspec.yaml`
- `test/widget_test.dart` (deleted, 2026-10-11: see Changes)
- `web/index.html`
- `web/manifest.json`

## Changes

- `lib/components/sockets/socket_services.dart`: transports `['polling', 'websocket']`,
  not just `'websocket'` (2026-10-10). Ubuntu 24.04 has no `python3-simple-websocket`,
  so maincar's server can only offer polling there.
- 2026-10-11, the changes in docs/hud.md ("What changed in the app"):
  - `lib/screens/home_page.dart`: an e-stop button (`POST /estop`), and a strip on top
    for the vehicle status and the battery. The old "Reading ROS2 Mock Data" line is
    gone; `withOpacity` became `withValues`. Tests can give it a fake socket and back end.
  - `lib/components/sockets/socket_services.dart`: the events' real names
    (`hud_events.dart`), the `vehicle_status` and `battery` events, and whether the back
    end is connected. Each callback is optional. `debugPrint`, not `print`; the prefix
    `IO` became `io` (Dart's style).
  - `lib/screens/map_page.dart`: Unlock and Clear send `POST /cancel`. `sendRouteToFlask`
    lost its two 3 s debug delays and its debug messages, and says whether the car took
    the route. "© OpenStreetMap contributors" under the map and under the search
    results. The back end's address is `kBackendUrl`.
  - `lib/screens/camera_page.dart`: rewritten. It shows the back end's
    `/camera/latest.png`, 5 times a second, and marks a picture that isn't live. It
    played WebRTC from a fixed address (192.168.1.118, MediaMTX).
  - `lib/main.dart`: no `WebRTC.initialize()`.
  - `lib/data/constants.dart`: `kBackendUrl` (default `http://127.0.0.1:5000`, or
    `--dart-define=HUD_BACKEND=...`) and `kOsmCredit`.
  - `pubspec.yaml`, `pubspec.lock`: dropped `flutter_webrtc`, and with it `dart_webrtc`
    and `webrtc_interface`. No package was added.
  - `.gitignore`: the plugin registrant files that every `flutter pub get` makes again.
  - `test/widget_test.dart`: deleted. It was Flutter's template test for a counter the
    app doesn't have, so it could never pass.

## New files (2026-27, not inherited)

| File | What it is |
|---|---|
| `lib/components/estop_button.dart` | the e-stop button |
| `lib/components/vehicle_status_strip.dart` | the status strip on the home screen |
| `lib/components/sockets/hud_events.dart` | the event names; the back end's tests check them |
| `lib/models/vehicle_status.dart` | the `vehicle_status` and `battery` events, read |
| `lib/services/backend.dart` | the back end's HTTP routes: route, cancel, e-stop, camera |
| `test/*.dart` | the app's tests (`pixi run hud-test`) |
| `test_bench/backend_test.dart` | the app's own client code against the bench's back end |
