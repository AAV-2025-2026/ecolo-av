import 'package:flutter/material.dart';
import 'package:flutter_pi/components/sockets/hud_events.dart';
import 'package:flutter_pi/screens/home_page.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

/// The home screen on the car's 800 x 480 screen, with a fake socket and back end.
Future<FakeSocketService> pumpHome(
  WidgetTester tester,
  FakeBackend backend,
) async {
  tester.view.physicalSize = const Size(800, 480);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  final socket = FakeSocketService();
  await tester.pumpWidget(
    MaterialApp(
      home: MyHomePage(
        title: 'UI Dashboard',
        socketService: socket,
        backend: backend.backend,
      ),
    ),
  );
  return socket;
}

void main() {
  testWidgets('the e-stop button asks the back end for /estop', (tester) async {
    final backend = FakeBackend();
    await pumpHome(tester, backend);
    await tester.tap(find.byKey(const Key('estop')));
    await tester.pump(); // the request
    await tester.pump(); // its answer
    expect(backend.calls, ['POST /estop']);
    expect(find.textContaining('E-stop sent'), findsOneWidget);
    await tester.pumpAndSettle(const Duration(seconds: 5)); // the message goes
  });

  testWidgets('an e-stop that was not sent says so, loudly', (tester) async {
    final backend = FakeBackend(status: 503, message: 'no ROS');
    await pumpHome(tester, backend);
    await tester.tap(find.byKey(const Key('estop')));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('E-STOP NOT SENT: no ROS'), findsOneWidget);
    expect(find.textContaining("car's red e-stop button"), findsOneWidget);
    await tester.pumpAndSettle(const Duration(seconds: 11));
  });

  testWidgets('the status strip shows what vehicle_status and battery say', (
    tester,
  ) async {
    final socket = await pumpHome(tester, FakeBackend());
    expect(find.text('No back end'), findsOneWidget);

    socket.onConnection!(true);
    await tester.pump();
    expect(find.text('Waiting for the car'), findsOneWidget);

    socket.handle(HudEvents.vehicleStatus, {
      'mode': 'computer',
      'armed': true,
      'estop': true,
      'gear': 'P',
      'faults': ['cmd_timeout', 'steering_driver'],
    });
    socket.handle(HudEvents.battery, {
      'voltage': 49.52,
      'percentage': 75.4,
      'current': null,
    });
    await tester.pump();
    expect(find.text('E-STOP ON'), findsOneWidget);
    expect(find.text('Armed'), findsOneWidget);
    expect(find.text('Mode: computer'), findsOneWidget);
    expect(find.text('Gear P'), findsOneWidget);
    expect(find.text('Battery: 75 % · 49.5 V'), findsOneWidget);
    expect(find.text('Faults: cmd_timeout, steering_driver'), findsOneWidget);

    socket.handle(HudEvents.vehicleStatus, {
      'mode': 'manual',
      'armed': false,
      'estop': false,
      'gear': 'P',
      'faults': <String>[],
    });
    await tester.pump();
    expect(find.text('E-stop off'), findsOneWidget);
    expect(find.text('Not armed'), findsOneWidget);
    expect(find.text('No faults'), findsOneWidget);

    // Lost the back end: no old values left on the screen.
    socket.onConnection!(false);
    await tester.pump();
    expect(find.text('No back end'), findsOneWidget);
    expect(find.text('E-stop off'), findsNothing);
  });

  testWidgets('speed, position and the stop sign, by their new names', (
    tester,
  ) async {
    final socket = await pumpHome(tester, FakeBackend());
    socket.handle(HudEvents.speed, {'speed': 1.5});
    socket.handle(HudEvents.position, {
      'latitude': 45.38601,
      'longitude': -75.69602,
    });
    socket.handle(HudEvents.stopSign, {'detected': true, 'message': 'STOP'});
    await tester.pump();
    expect(find.text('Speed: 1.50 m/s'), findsOneWidget);
    expect(find.text('Latitude: 45.38601'), findsOneWidget);
    expect(find.text('Longitude: -75.69602'), findsOneWidget);
    expect(find.text('STOP'), findsOneWidget);
  });
}
