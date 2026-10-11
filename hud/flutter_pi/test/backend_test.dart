import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_pi/services/backend.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'fakes.dart';

void main() {
  test(
    'the e-stop is a POST to /estop, with nothing that could clear it',
    () async {
      final fake = FakeBackend();
      final reply = await fake.backend.estop();
      expect(reply.ok, isTrue);
      expect(fake.calls, ['POST /estop']);
      expect(fake.requests.single.body, isEmpty);
      expect(fake.requests.single.url.toString(), 'http://hud.test/estop');
    },
  );

  test('an e-stop the back end refused says why', () async {
    final reply =
        await FakeBackend(status: 503, message: 'no ROS').backend.estop();
    expect(reply.ok, isFalse);
    expect(reply.message, 'no ROS');
  });

  test('a back end that is down is an answer too', () async {
    final backend = HudBackend(
      baseUrl: 'http://hud.test',
      client: MockClient(
        (_) async => throw http.ClientException('Connection refused'),
      ),
    );
    final reply = await backend.estop();
    expect(reply.ok, isFalse);
    expect(reply.message, contains('no answer from the back end'));
  });

  test('the locked route goes to /receive as JSON', () async {
    final fake = FakeBackend();
    final route = jsonEncode([
      {'lat': 45.386, 'lon': -75.696},
    ]);
    expect((await fake.backend.sendRoute(route)).ok, isTrue);
    final request = fake.requests.single;
    expect(fake.calls, ['POST /receive']);
    expect(request.headers['content-type'], startsWith('application/json'));
    expect(request.body, route);
  });

  test('unlock and clear: POST /cancel', () async {
    final fake = FakeBackend(
      status: 409,
      message: 'no route is being followed',
    );
    final reply = await fake.backend.cancelRoute();
    expect(fake.calls, ['POST /cancel']);
    expect(reply.message, 'no route is being followed');
  });

  test('the camera picture, or why there is none', () async {
    final png = Uint8List.fromList([0x89, 0x50, 0x4e, 0x47]);
    var answer = http.Response.bytes(png, 200);
    final backend = HudBackend(
      baseUrl: 'http://hud.test',
      client: MockClient((request) async {
        expect(request.url.path, '/camera/latest.png');
        return answer;
      }),
    );
    final picture = await backend.cameraPicture();
    expect(picture.png, png);
    expect(picture.status, 'live');
    answer = http.Response(
      'no new camera picture: is the camera running?',
      503,
    );
    final none = await backend.cameraPicture();
    expect(none.png, isNull);
    expect(none.status, 'no new camera picture: is the camera running?');
  });
}
