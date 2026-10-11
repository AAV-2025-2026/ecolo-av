import 'package:flutter/material.dart';
import 'package:flutter_pi/util/ipc.dart';

import '../components/estop_button.dart';
import '../components/sockets/socket_services.dart';
import '../components/vehicle_status_strip.dart';
import '../data/constants.dart';
import '../models/vehicle_status.dart';
import '../services/backend.dart';

class MyHomePage extends StatefulWidget {
  const MyHomePage({
    super.key,
    required this.title,
    this.socketService,
    this.backend,
  });

  final String title;

  /// For tests: a socket and a back end that need no network. Null: the real ones.
  final SocketService? socketService;
  final HudBackend? backend;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  late final SocketService socketService =
      widget.socketService ?? SocketService();
  late final HudBackend backend = widget.backend ?? HudBackend();

  double speed = 0.0;
  double latitude = 0.0;
  double longitude = 0.0;

  bool _cameraOpen = false;
  bool stopSignDetected = false;
  String stopMessage = "STOP";

  bool connected = false;
  VehicleStatus? vehicle;
  BatteryReading? battery;

  @override
  void initState() {
    super.initState();

    socketService.initSocketConnection(
      serverUrl: kBackendUrl,
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
      onStopSignAlert: (detected, message) {
        setState(() {
          stopSignDetected = detected;
          stopMessage = message;
        });
      },
      onVehicleStatus: (status) => setState(() => vehicle = status),
      onBattery: (reading) => setState(() => battery = reading),
      onConnection: (isConnected) {
        if (!mounted) return;
        setState(() {
          connected = isConnected;
          if (!isConnected) {
            // Old values could say the car is stopped when it isn't.
            vehicle = null;
            battery = null;
          }
        });
      },
    );
  }

  @override
  void dispose() {
    socketService.dispose();
    if (widget.backend == null) backend.close();
    super.dispose();
  }

  /// The e-stop button: ask the back end for /estop true, and say whether it was sent.
  Future<void> _estop() async {
    final reply = await backend.estop();
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(
      reply.ok
          ? const SnackBar(
            content: Text(
              'E-stop sent: the car brakes. Clear it from a laptop.',
            ),
            duration: Duration(seconds: 4),
          )
          : SnackBar(
            backgroundColor: Colors.red.shade900,
            duration: const Duration(seconds: 10),
            content: Text(
              "E-STOP NOT SENT: ${reply.message}. Press the car's red e-stop button.",
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
    );
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
      body: Stack(
        children: [
          Column(
            children: [
              VehicleStatusStrip(
                connected: connected,
                status: vehicle,
                battery: battery,
              ),
              Expanded(
                child: Row(
                  children: [
                    Expanded(
                      // Scaled down, never cut off, when the status strip takes two lines.
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
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
                            const SizedBox(height: 20),
                            Card(
                              color: Colors.deepPurple.shade300,
                              margin: const EdgeInsets.symmetric(
                                horizontal: 24,
                                vertical: 10,
                              ),
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
                            Card(
                              color: Colors.deepPurple.shade300,
                              margin: const EdgeInsets.symmetric(
                                horizontal: 24,
                                vertical: 10,
                              ),
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
                          ],
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          EstopButton(onPressed: _estop),
                          const SizedBox(height: 24),
                          ElevatedButton.icon(
                            onPressed: () {
                              setState(() => _cameraOpen = !_cameraOpen);
                              sendCommand(_cameraOpen ? 'camera' : 'map');
                            },
                            icon: Icon(
                              _cameraOpen ? Icons.videocam_off : Icons.videocam,
                            ),
                            label: Text(
                              _cameraOpen ? 'Close Camera' : 'Open Camera',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          if (stopSignDetected)
            Positioned(
              top: 60,
              left: 20,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.75),
                  border: Border.all(color: Colors.red, width: 2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  stopMessage,
                  style: const TextStyle(
                    color: Colors.red,
                    fontSize: 30,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
