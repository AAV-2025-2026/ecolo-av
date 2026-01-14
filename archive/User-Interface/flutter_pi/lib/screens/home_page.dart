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
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(widget.title),
        backgroundColor: Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'Vehicle Status Module',
              style: TextStyle(
                color: Colors.white,
                fontSize: 26,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 40),

            // Speed Display
            Card(
              color: Colors.deepPurple.shade300,
              margin: const EdgeInsets.symmetric(horizontal: 50, vertical: 10),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Text(
                  'Speed: ${speed.toStringAsFixed(2)} m/s',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),

            // GPS Display
            Card(
              color: Colors.deepPurple.shade300,
              margin: const EdgeInsets.symmetric(horizontal: 50, vertical: 10),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  children: [
                    Text(
                      'Latitude: ${latitude.toStringAsFixed(5)}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Longitude: ${longitude.toStringAsFixed(5)}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 30),
            const Text(
              "Reading ROS2 Mock Data",
              style: TextStyle(color: Colors.white70, fontSize: 16),
            ),
            const SizedBox(height: 10),
            // ElevatedButton.icon(
            //   onPressed: () {
            //     Navigator.of(context).push(MaterialPageRoute(builder: (_) => const MapPage()));
            //   },
            //   icon: const Icon(Icons.map),
            //   label: const Text('Open Map'),
            // ),
          ],
        ),
      ),
    );
  }
}
