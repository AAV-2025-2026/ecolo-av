# flutter_pi

The 2025-26 team's touchscreen app for the car, in Flutter (Dart). It shows the car's
state, a big e-stop button, a map to pick a destination, and the front camera. It is
the front end of the HUD: the back end is `ros/hud/aav_hud`.

**Decided (Ben, 15 Oct): the raylib HUD replaces it** (Q29, `ros/hud/aav_hud_raylib`).
The app stays until the new one matches it. More in `docs/hud.md`, "The Flutter app".

## Overview

One program opens two windows, one per screen (800x480 each):

```
flutter_pi            the dashboard (home page), on the first display
  └─ starts itself again with --Map
flutter_pi --Map      the map page, on the second (the camera page lies on top)
```

| Talks to | How | Address |
|---|---|---|
| the back end (`aav_hud`'s `hud_server`) | Socket.IO over WebSocket, and HTTP | `http://127.0.0.1:5000` (`kBackendUrl`) |
| OSRM, the router | HTTP `/route/v1/driving/...` | `http://localhost:5001` (`kOsrmBaseUrl`) |
| a tile server | HTTP `/styles/basic-preview/{z}/{x}/{y}.png` | `http://localhost:8080` |
| the computer's location service | `geolocator`: one fix at start (if the socket gave none), then a stream after Lock | the operating system |

OSRM and the tile server are not in git. (`map_page.dart` also names a Photon geocoder
on port 2322, but never calls it: place search reads `ottawa.db`.) In 2025-26 they ran
on the UI Pi (see `hud/scripts/`).

One folder covers it all: `lib/` (the app), `linux/` (Flutter's Linux runner), `web/`,
`test/` and `test_bench/`.

## Interface

**Screens** (`lib/screens/`)

| File | Shows |
|---|---|
| `home_page.dart` | `MyHomePage`: speed, stop-sign alert, status strip, battery, the e-stop button |
| `map_page.dart` | `MapPage`: the map, place search, an OSRM route, Lock/Unlock/Clear; **Simulate Trace** (paste CSV lat/lon, then play, pause, step or stop a fake position along it); `MapPageController` swaps in the camera |
| `camera_page.dart` | `CameraPage`: the back end's `/camera/latest.png`, 5 times a second; marks a picture that isn't live |

**Parts**

| File | Item | Does |
|---|---|---|
| `lib/components/sockets/socket_services.dart` | `SocketService` | the Socket.IO link; one optional callback per event |
| `lib/components/sockets/hud_events.dart` | `HudEvents` | the event names (below) |
| `lib/services/backend.dart` | `HudBackend`, `BackendReply`, `CameraPicture` | the HTTP routes; each call answers, even when the back end is down (5 s timeout) |
| `lib/models/vehicle_status.dart` | `VehicleStatus`, `BatteryReading` | read the `vehicle_status` and `battery` events |
| `lib/components/estop_button.dart` | `EstopButton` | big, red, one tap |
| `lib/components/vehicle_status_strip.dart` | `VehicleStatusStrip` | e-stop, armed, mode, gear, battery, faults; nothing while disconnected |
| `lib/services/database_service.dart` | `DatabaseService` | place search in `ottawa.db` (SQLite) |
| `lib/util/ipc.dart` | `sendCommand`, `readAndClearCommand` | the two windows talk through one temp file |
| `lib/data/constants.dart` | `kBackendUrl`, `kOsrmBaseUrl`, `kOsmCredit`, `kWindowConfig`, `kAppTitle`, `kColorSchemeSeed` | settings |

**Socket.IO events it reads** (names must match `ros/hud/aav_hud/aav_hud/events.py`)

| Event | Payload |
|---|---|
| `speed` | `speed`: m/s, negative in reverse |
| `position` | `latitude`, `longitude`: degrees |
| `stop_sign` | `detected`: bool, `message` |
| `nav_state` | `distance`: m, `status` |
| `vehicle_status` | `mode`, `armed`, `estop`, `gear`, `faults` |
| `battery` | `voltage`: V, `percentage`: 0-100, `current`: A (each may be null) |

**HTTP routes it calls** (`ros/hud/aav_hud/aav_hud/web.py`)

| Route | When |
|---|---|
| `POST /receive` | Lock: a JSON list of `{lat, lon}`, for Nav2 |
| `POST /cancel` | Unlock and Clear |
| `POST /estop` | the e-stop button: the back end publishes `/safety/estop` true |
| `GET /camera/latest.png` | the camera page |

**Settings at build or run time**

- `--dart-define=HUD_BACKEND=http://127.0.0.1:5123`: another back end.
- `--Map`: be the map window (the app passes it to itself).

## Invariants

- The app only ever **sets** the e-stop. Clearing it is a person's act, from a laptop.
- If `POST /estop` fails, the screen says so in red and tells the person to press the
  car's red e-stop button. Nobody may believe a failed press worked.
- When the socket drops, the status and battery are wiped: old values could say the car
  is stopped when it isn't.
- `VehicleStatus.fromEvent` throws without `armed` or `estop`: no guessing.
- Event names live in `hud_events.dart` and `events.py`. Rename both at once: the back
  end's `test_events.py` reads this file and checks them.
- WebSocket transport only: on Linux and macOS, `socket_io_client` 2.0.3 has no polling.
  The back end needs `simple-websocket` (Pixi has it).
- Map tiles and places are OpenStreetMap data: show `kOsmCredit` with them (ODbL).
- `pubspec.lock` was made with Flutter 3.35: use `pixi run get-flutter` (3.35.7).
- Inherited code: every change goes in `PROVENANCE.md`.

## Side Effects

- Network: Socket.IO and HTTP to the back end; HTTP to OSRM and the tile server.
- Location: asks the operating system for location permission, and reads fixes from
  its location service (`geolocator`).
- `POST /receive` moves the car (Nav2 drives the route). `POST /estop` brakes it.
- Starts a second copy of itself (`--Map`), detached.
- Goes full screen, and moves each window to its display.
- Files: writes `<temp>/flutter_pi_command` (the windows' messages); copies
  `assets/databases/ottawa.db` into the SQLite folder, each start; saves each OSRM
  answer as `osrm_route.json` in Downloads (else Documents).
- `assets/databases/ottawa.db` is not in git: `pixi run get-hud-map` links it in.

## Verification

```sh
pixi run get-flutter      # once: Flutter 3.35.7 into vendor/flutter (about 4.3 GB)
pixi run hud-test         # pub get (offline), analyze, test, then test_bench
```

- `hud-test` runs `test_bench/` against `tools/hud_fake_backend.py`: the real web
  server with a fake car, on 127.0.0.1. `test_bench` presses the e-stop: never point it
  at a real car.
- `pixi run test` (via `tools/test.sh`) runs `hud-test` when `vendor/flutter` exists.
- On the bench: `pixi run bench hud:=true hud_port:=5123`, then
  `pixi run flutter test test_bench --dart-define=HUD_BACKEND=http://127.0.0.1:5123`.
- Run the app on Linux x64 with GTK: `tools/flutter.sh run -d linux`, outside Pixi.
  Untested. There is no macOS runner yet (`docs/hud.md`).

## Flutter help

From Flutter's template:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)
- [Flutter's documentation](https://docs.flutter.dev/)
