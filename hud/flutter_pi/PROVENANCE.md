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
- `test/widget_test.dart`
- `web/index.html`
- `web/manifest.json`

## Changes

- `lib/components/sockets/socket_services.dart`: transports `['polling', 'websocket']`,
  not just `'websocket'` (2026-10-10). Ubuntu 24.04 has no `python3-simple-websocket`,
  so maincar's server can only offer polling there.
