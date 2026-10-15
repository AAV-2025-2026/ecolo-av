/// The HUD's back end over HTTP (aav_hud's web.py): the route, the e-stop and the camera.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../data/constants.dart';

/// The back end's answer: whether it did it, and what to tell the person.
class BackendReply {
  const BackendReply(this.ok, this.message);

  final bool ok;
  final String message;
}

/// One fetch of the camera: the picture (PNG), or null and the reason.
class CameraPicture {
  const CameraPicture(this.png, this.status);

  final Uint8List? png;
  final String status;
}

/// Requests to the back end. Each one answers, even when the back end is down.
class HudBackend {
  HudBackend({String? baseUrl, http.Client? client})
    : baseUrl = baseUrl ?? kBackendUrl,
      _client = client ?? http.Client();

  /// Where the back end listens, e.g. http://127.0.0.1:5000.
  final String baseUrl;
  final http.Client _client;

  /// How long to wait for an answer.
  static const timeout = Duration(seconds: 5);

  /// Drive this route, a JSON list of {'lat': .., 'lon': ..}: the back end gives it to Nav2.
  Future<BackendReply> sendRoute(String routeJson) =>
      _post('/receive', routeJson);

  /// Stop following the route (the map page's Unlock and Clear).
  Future<BackendReply> cancelRoute() => _post('/cancel');

  /// The e-stop: the back end publishes /safety/estop true. Nothing in the app can clear it.
  Future<BackendReply> estop() => _post('/estop');

  /// The newest camera picture, from /camera/latest.png.
  Future<CameraPicture> cameraPicture() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/camera/latest.png'))
          .timeout(timeout);
      if (response.statusCode == 200) {
        return CameraPicture(response.bodyBytes, 'live');
      }
      // 503 'no camera picture yet', 415 an encoding it can't show: plain text.
      final reason = response.body.trim();
      return CameraPicture(
        null,
        reason.isEmpty ? 'HTTP ${response.statusCode}' : reason,
      );
    } on Exception catch (e) {
      return CameraPicture(null, 'no answer from the back end ($e)');
    }
  }

  void close() => _client.close();

  Future<BackendReply> _post(String path, [String? json]) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl$path'),
            headers:
                json == null
                    ? null
                    : const {'Content-Type': 'application/json'},
            body: json,
          )
          .timeout(timeout);
      return BackendReply(response.statusCode == 200, _message(response));
    } on Exception catch (e) {
      // Timeout, refused connection: say so, so nobody believes it worked.
      return BackendReply(false, 'no answer from the back end ($e)');
    }
  }

  /// The back end answers {'status': .., 'message': ..}; show its message if any.
  static String _message(http.Response response) {
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['message'] is String) {
        return body['message'] as String;
      }
    } on FormatException {
      // Not JSON: fall through to the status code.
    }
    return response.statusCode == 200 ? 'done' : 'HTTP ${response.statusCode}';
  }
}
