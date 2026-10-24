// ignore: library_prefixes
import 'package:socket_io_client/socket_io_client.dart' as IO;

class SocketService {
  IO.Socket? _socket;

  final void Function(double speed) onSpeedUpdate;
  final void Function(double lat, double lon) onGpsUpdate;

  SocketService({
    required this.onSpeedUpdate,
    required this.onGpsUpdate,
  });

  void connect({required String serverUrl}) {
    _socket = IO.io(
      serverUrl,
      IO.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .build(),
    );

    _socket!.connect();

    _socket!.onConnect((_) => print('✅ Connected'));
    _socket!.onConnectError((err) => print('❌ Connect error: $err'));
    _socket!.onDisconnect((_) => print('⚠️ Disconnected'));

    _socket!.on('mock_speed_update', (data) {
      final speed = (data['speed'] as num).toDouble(); // must match Flask
      onSpeedUpdate(speed);
    });

    _socket!.on('mock_gps_update', (data) {
      final lat = (data['latitude'] as num).toDouble();
      final lon = (data['longitude'] as num).toDouble();
      onGpsUpdate(lat, lon);
    });
  }

  void dispose() {
    _socket?.disconnect();
    _socket?.dispose();
    _socket = null;
  }
}
