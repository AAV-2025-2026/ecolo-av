import 'package:socket_io_client/socket_io_client.dart' as IO;

class SocketService {
  IO.Socket? socket;

  late Function(double) onSpeedUpdate;
  late Function(double, double) onGpsUpdate;
  late Function(bool, String) onStopSignAlert;
  Function(double, String)? onNavState; // nullable

  /// Initialize the socket connection.
  void initSocketConnection({
    required String serverUrl,
    required Function(double) onSpeedUpdate,
    required Function(double, double) onGpsUpdate,
    required Function(bool, String) onStopSignAlert,
    Function(double, String)? onNavState,
  }) {
    this.onSpeedUpdate = onSpeedUpdate;
    this.onGpsUpdate = onGpsUpdate;
    this.onStopSignAlert = onStopSignAlert;
    this.onNavState = onNavState;

    socket = IO.io(
      serverUrl,
      IO.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .build(),
    );

    socket!.connect();

    socket!.onConnect((_) {
      print("✅ Connected to Flask Socket.IO server");
    });

    socket!.onConnectError((err) {
      print("❌ Connection error: $err");
    });

    socket!.onDisconnect((_) {
      print("⚠️ Disconnected from Flask server");
    });

    // Existing listeners
    socket!.on('mock_stop_sign_alert', (data) {
      try {
        final detected = (data['mock_sign_detected'] as bool?) ?? false;
        final message = data['message'] ?? 'STOP';
        onStopSignAlert(detected, message);
      } catch (e) {
        print('mock_stop_sign_alert parse error: $e');
      }
    });

    socket!.on('mock_speed_update', (data) {
      try {
        final speed = (data['mock_speed'] as num).toDouble();
        onSpeedUpdate(speed);
      } catch (e) {
        print('mock_speed_update parse error: $e');
      }
    });

    socket!.on('mock_gps_update', (data) {
      try {
        final latitude = (data['mock_latitude'] as num).toDouble();
        final longitude = (data['mock_longitude'] as num).toDouble();
        onGpsUpdate(latitude, longitude);
      } catch (e) {
        print('mock_gps_update parse error: $e');
      }
    });

    socket!.on('nav_state', (data) {
      try {
        final distance = (data['distance'] as num).toDouble();
        final status = (data['status'] as String?) ?? '';
        onNavState?.call(distance, status); // safe call
      } catch (e) {
        print('nav_state parse error: $e');
      }
    });
  }

  void dispose() {
    socket?.dispose();
  }
}
