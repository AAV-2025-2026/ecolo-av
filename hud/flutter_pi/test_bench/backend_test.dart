/// The app's own client code against a running back end: the same SocketService and
/// HudBackend as the screens, with no fakes. It presses the e-stop the way the home
/// screen's button does.
///
/// `pixi run hud-test` runs it against the back end's web server with a fake car
/// (tools/hud_fake_backend.py). On the bench, with the whole car graph:
///
///   pixi run bench hud:=true hud_port:=5123
///   pixi run flutter test test_bench --dart-define=HUD_BACKEND=http://127.0.0.1:5123
///
/// Never point it at a real car: it sets the e-stop.
library;

// It prints what it saw: that is its point.
// ignore_for_file: avoid_print

import 'dart:async';

import 'package:flutter_pi/components/sockets/socket_services.dart';
import 'package:flutter_pi/data/constants.dart';
import 'package:flutter_pi/models/vehicle_status.dart';
import 'package:flutter_pi/services/backend.dart';
import 'package:flutter_test/flutter_test.dart';

const configured = bool.hasEnvironment('HUD_BACKEND');

void main() {
  test(
    'vehicle_status, the battery, the camera and the e-stop, live',
    () async {
      final statuses = StreamController<VehicleStatus>.broadcast();
      BatteryReading? battery;
      final socket = SocketService()
        ..initSocketConnection(
          serverUrl: kBackendUrl,
          onVehicleStatus: statuses.add,
          onBattery: (reading) => battery = reading,
        );
      final backend = HudBackend();
      addTearDown(() {
        socket.dispose();
        backend.close();
        statuses.close();
      });

      final first = await statuses.stream.first.timeout(
        const Duration(seconds: 30),
      );
      print(
        'vehicle_status: mode ${first.mode}, armed ${first.armed}, '
        'e-stop ${first.estop}, gear ${first.gear}, faults ${first.faults}',
      );
      final picture = await backend.cameraPicture();
      print('camera: ${picture.png?.length ?? 0} bytes of PNG (${picture.status})');

      final pressed = DateTime.now();
      final stopped = statuses.stream.firstWhere((s) => s.estop);
      final reply = await backend.estop();
      print('POST /estop: ok ${reply.ok}, ${reply.message}');
      expect(reply.ok, isTrue);
      final after = await stopped.timeout(const Duration(seconds: 5));
      final ms = DateTime.now().difference(pressed).inMilliseconds;
      print('vehicle_status says e-stop on $ms ms after the press (gear ${after.gear})');
      print('battery: ${battery?.label ?? 'no reading yet'}');
    },
    skip: configured
        ? false
        : 'needs a back end: --dart-define=HUD_BACKEND=http://127.0.0.1:<port>',
  );
}
