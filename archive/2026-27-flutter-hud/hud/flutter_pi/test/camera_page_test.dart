import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_pi/screens/camera_page.dart';
import 'package:flutter_pi/services/backend.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A 1 x 1 grey PNG.
final onePixel = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNoAAAAggCBd81ytgAAAABJRU5ErkJggg==',
);

void main() {
  testWidgets('it shows /camera/latest.png, and says when it is not live', (
    tester,
  ) async {
    var answer = http.Response.bytes(onePixel, 200);
    final asked = <String>[];
    final backend = HudBackend(
      baseUrl: 'http://hud.test',
      client: MockClient((request) async {
        asked.add(request.url.toString());
        return answer;
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CameraPage(backend: backend, period: const Duration(seconds: 1)),
      ),
    );
    await tester.pump();
    expect(asked, ['http://hud.test/camera/latest.png']);
    expect(find.byType(Image), findsOneWidget);
    expect(find.textContaining('Not live'), findsNothing);

    // The camera stops: the old picture stays, marked.
    answer = http.Response(
      'no new camera picture: is the camera running?',
      503,
    );
    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
    expect(asked, hasLength(2));
    expect(find.byType(Image), findsOneWidget);
    expect(
      find.text('Not live: no new camera picture: is the camera running?'),
      findsOneWidget,
    );

    // Closing the page stops the fetches.
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('before the first picture it says why there is none', (
    tester,
  ) async {
    final backend = HudBackend(
      baseUrl: 'http://hud.test',
      client: MockClient(
        (_) async => http.Response('no new camera picture', 503),
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CameraPage(backend: backend, period: const Duration(seconds: 1)),
      ),
    );
    await tester.pump();
    expect(find.byType(Image), findsNothing);
    expect(find.text('no new camera picture'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
