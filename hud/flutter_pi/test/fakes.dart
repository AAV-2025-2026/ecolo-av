import 'dart:convert';

import 'package:flutter_pi/components/sockets/socket_services.dart';
import 'package:flutter_pi/services/backend.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A SocketService with no socket: tests push events in with [handle].
class FakeSocketService extends SocketService {
  String? serverUrl;
  void Function(bool connected)? onConnection;

  @override
  void connect(String serverUrl, void Function(bool connected)? onConnection) {
    this.serverUrl = serverUrl;
    this.onConnection = onConnection;
  }
}

/// A back end that answers like aav_hud's web.py, and notes every request.
class FakeBackend {
  FakeBackend({this.status = 200, this.message});

  final int status;
  final String? message;
  final List<http.Request> requests = [];

  late final HudBackend backend = HudBackend(
    baseUrl: 'http://hud.test',
    client: MockClient((request) async {
      requests.add(request);
      final body =
          status == 200
              ? {'status': 'success'}
              : {'status': 'error', 'message': message ?? 'no'};
      return http.Response(jsonEncode(body), status);
    }),
  );

  /// The paths asked for, e.g. ['POST /estop'].
  List<String> get calls => [
    for (final r in requests) '${r.method} ${r.url.path}',
  ];
}
