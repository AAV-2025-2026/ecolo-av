import 'package:flutter/material.dart';
import 'package:flutter_onscreen_keyboard/flutter_onscreen_keyboard.dart';
import 'package:flutter_pi/data/constants.dart';
import 'package:flutter_pi/screens/map_page.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  testWidgets('Clear cancels the route, and the map credits OpenStreetMap', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 480);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    final backend = FakeBackend(
      status: 409,
      message: 'no route is being followed',
    );
    await tester.pumpWidget(
      MaterialApp(
        // As main.dart: the map page's text fields need the on-screen keyboard.
        builder: OnscreenKeyboard.builder(
          layout: const DesktopKeyboardLayout(),
          aspectRatio: 6,
        ),
        home: MapPage(
          socketService: FakeSocketService(),
          backend: backend.backend,
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Map $kOsmCredit'), findsOneWidget);

    await tester.tap(find.text('Clear'));
    await tester.pump();
    await tester.pump();
    expect(backend.calls, ['POST /cancel']);
    expect(find.text('Cancel: no route is being followed'), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
    await tester.pump(
      const Duration(seconds: 10),
    ); // the location lookup gives up
  });
}
