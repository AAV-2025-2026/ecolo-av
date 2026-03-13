// ignore: library_prefixes
import 'package:socket_io_client/socket_io_client.dart' as IO;

class SocketService {
  IO.Socket? socket;

  late Function(double) onSpeedUpdate;
  late Function(double, double) onGpsUpdate;
  late Function(bool, String) onStopSignAlert;

  void initSocketConnection({
    required String serverUrl,
    required Function(double) onSpeedUpdate,
    required Function(double, double) onGpsUpdate,
    required Function(bool, String) onStopSignAlert,
  }) {
    this.onSpeedUpdate = onSpeedUpdate;
    this.onGpsUpdate = onGpsUpdate;
    this.onStopSignAlert = onStopSignAlert;

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

    socket!.on('mock_speed_update', (data) {
      final speed = (data['speed'] as num).toDouble();
      onSpeedUpdate(speed);
    });

    socket!.on('mock_gps_update', (data) {
      final latitude = (data['latitude'] as num).toDouble();
      final longitude = (data['longitude'] as num).toDouble();
      onGpsUpdate(latitude, longitude);
    });

    socket!.on('stop_sign_alert', (data) {
      final detected = data['detected'] ?? false;
      final message = data['message'] ?? 'STOP';
      onStopSignAlert(detected, message);
    });
  }

  void dispose() {
    socket?.dispose();
  }
}