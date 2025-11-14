// ignore: library_prefixes
import 'package:socket_io_client/socket_io_client.dart' as IO;

class SocketService {
  IO.Socket? socket;
  late Function(double) onSpeedUpdate;
  late Function(double, double) onGpsUpdate;

  void initSocketConnection({
    required String serverUrl,
    required Function(double) onSpeedUpdate,
    required Function(double, double) onGpsUpdate,
  }) {
    this.onSpeedUpdate = onSpeedUpdate;
    this.onGpsUpdate = onGpsUpdate;

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
  }

  void dispose() {
    socket?.dispose();
  }
}
