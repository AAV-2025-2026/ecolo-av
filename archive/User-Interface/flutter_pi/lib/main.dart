import 'package:flutter/material.dart';
import 'package:socket_io_client/socket_io_client.dart' as IO;
import 'package:window_manager/window_manager.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  WindowOptions windowOptions = const WindowOptions(
    size: Size(1920, 1080),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.hidden,
  );

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.setFullScreen(true);
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ROS2 + Flask + Flutter Demo',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const MyHomePage(title: 'UI Dashboard'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  IO.Socket? socket;

  double speed = 0.0;
  double latitude = 0.0;
  double longitude = 0.0;

  @override
  void initState() {
    super.initState();
    initSocketConnection();
  }

  /// Initializes connection to Flask Socket.IO server
  void initSocketConnection() {
    socket = IO.io(
      'http://127.0.0.1:5000', // Change to your Flask server IP if not local
      IO.OptionBuilder()
          .setTransports(['websocket']) // Use WebSocket transport
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

    // Listen for speed updates
    socket!.on('mock_speed_update', (data) {
      setState(() {
        speed = (data['speed'] as num).toDouble();
      });
      print("📡 Received mock speed: $speed");
    });

    // Listen for GPS updates
    socket!.on('mock_gps_update', (data) {
      setState(() {
        latitude = (data['latitude'] as num).toDouble();
        longitude = (data['longitude'] as num).toDouble();
      });
      print("📍 Received GPS: $latitude, $longitude");
    });
  }

  @override
  void dispose() {
    socket?.dispose();
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
          ],
        ),
      ),
    );
  }
}
