import 'package:flutter/material.dart';
import '../services/socket_service.dart';

class BlankCameraPage extends StatefulWidget {
  const BlankCameraPage({super.key});

  @override
  State<BlankCameraPage> createState() => _BlankCameraPageState();
}

class _BlankCameraPageState extends State<BlankCameraPage> {
  SocketService? _socketService;

  // Just to confirm the connection works:
  double _speed = 0.0;
  double _lat = 0.0;
  double _lon = 0.0;

  // IMPORTANT:
  // - If Flutter runs on the SAME machine as Flask: use 127.0.0.1
  // - If Flutter runs on another device: use your PC’s LAN IP, like http://192.168.1.10:5000
  static const String serverUrl = 'http://127.0.0.1:5000';

  @override
  void initState() {
    super.initState();

    _socketService = SocketService(
      onSpeedUpdate: (speed) {
        if (!mounted) return;
        setState(() => _speed = speed);
      },
      onGpsUpdate: (lat, lon) {
        if (!mounted) return;
        setState(() {
          _lat = lat;
          _lon = lon;
        });
      },
    );

    _socketService!.connect(serverUrl: serverUrl);
  }

  @override
  void dispose() {
    _socketService?.dispose();
    super.dispose();
  }

  @override
  @override
Widget build(BuildContext context) {
  return Scaffold(
    backgroundColor: Colors.grey.shade100, // darker white
    appBar: AppBar(
      title: const Text('Camera Test'),
      backgroundColor: Colors.deepPurple.shade700,
      foregroundColor: Colors.white,
      centerTitle: true,
    ),
    body: const SizedBox.expand(), // completely empty body
  );
}

}
