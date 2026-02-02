import 'package:flutter/material.dart';
import '../components/sockets/socket_services.dart';
import 'map_page.dart';

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  late SocketService socketService;
  double speed = 0.0;
  double latitude = 0.0;
  double longitude = 0.0;

  @override
  void initState() {
    super.initState();
    socketService = SocketService();
    socketService.initSocketConnection(
      serverUrl: 'http://127.0.0.1:5000',
      onSpeedUpdate: (newSpeed) {
        setState(() {
          speed = newSpeed;
        });
      },
      onGpsUpdate: (lat, lon) {
        setState(() {
          latitude = lat;
          longitude = lon;
        });
      },
    );
  }

  @override
  void dispose() {
    socketService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
  return Scaffold(
    backgroundColor: Colors.grey.shade100, // darker white
    appBar: AppBar(
      title: const Text('Camera Test'),
      backgroundColor: Colors.deepPurple.shade700,
      foregroundColor: Colors.grey,
      centerTitle: true,
    ),
    body: const SizedBox.expand(), // completely empty body
  );
}
}
