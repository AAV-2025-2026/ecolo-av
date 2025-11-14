import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

void showAppMessage(BuildContext? context, String message) {
  if (context == null) {
    // fallback to console when no BuildContext available
    // (useful during init)
    // ignore: avoid_print
    print(message);
    return;
  }
  ScaffoldMessenger.of(context).clearSnackBars();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message), duration: const Duration(seconds: 2)),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OSRM Flutter GPS',
      theme: ThemeData(primarySwatch: Colors.blue),
      home: const MapPage(),
    );
  }
}

class MapPage extends StatefulWidget {
  const MapPage({super.key});
  @override
  State<MapPage> createState() => _MapPageState();
}

class _MapPageState extends State<MapPage> {
  // If the app runs on the same Ubuntu VM as OSRM -> use http://localhost:5000
  // If running on an Android emulator and OSRM runs on the host -> use http://10.0.2.2:5000
  String osrmBaseUrl = 'http://localhost:5000';

  final MapController mapController = MapController();
  LatLng? currentLocation;
  LatLng? destination;
  List<LatLng> routePoints = [];
  bool routing = false;
  final TextEditingController lonController = TextEditingController();
  final TextEditingController latController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Delay position attempt until after first frame so ScaffoldMessenger is available
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _determinePosition();
    });
  }

  Future<void> _determinePosition() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        if (mounted) showAppMessage(context, 'Location services disabled - using fallback');
        // continue to try permissions but allow fallback below
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          if (mounted) showAppMessage(context, 'Location permission denied - using fallback');
          // fallback below
        }
      }
      if (permission == LocationPermission.deniedForever) {
        if (mounted) showAppMessage(context, 'Location permission denied forever - using fallback');
        // fallback below
      }

      try {
        Position pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.best, timeLimit: const Duration(seconds: 8));
        if (mounted) {
          setState(() {
            currentLocation = LatLng(pos.latitude, pos.longitude);
          });
          mapController.move(currentLocation!, 15.0);
        }
        return;
      } catch (e) {
        if (mounted) showAppMessage(context, 'Could not get position (provider): $e');
      }
    } catch (e) {
      // platform plugin might be unavailable on some desktop setups
      if (mounted) showAppMessage(context, 'Location check failed: $e');
    }

    // Fallback development location (Ottawa) if real location not available
    if (mounted && currentLocation == null) {
      setState(() {
        currentLocation = LatLng(45.4215, -75.6919);
      });
      try {
        mapController.move(currentLocation!, 13.0);
      } catch (_) {}
    }
  }

  Future<void> _routeTo(LatLng dest) async {
    if (currentLocation == null) {
      if (mounted) showAppMessage(context, 'Current location unknown');
      return;
    }
    setState(() {
      routing = true;
      destination = dest;
      routePoints = [];
    });

    final src = '${currentLocation!.longitude},${currentLocation!.latitude}';
    final dst = '${dest.longitude},${dest.latitude}';
    final url = Uri.parse('$osrmBaseUrl/route/v1/driving/$src;$dst?overview=full&geometries=geojson&steps=true');

    try {
      final res = await http.get(url).timeout(const Duration(seconds: 10));
      if (res.statusCode != 200) {
        if (mounted) showAppMessage(context, 'OSRM error: ${res.statusCode}');
        setState(() => routing = false);
        return;
      }
      final body = json.decode(res.body) as Map<String, dynamic>;
      if (body['routes'] == null || (body['routes'] as List).isEmpty) {
        if (mounted) showAppMessage(context, 'No route found');
        setState(() => routing = false);
        return;
      }
      final route = body['routes'][0] as Map<String, dynamic>;
      final geom = route['geometry'] as Map<String, dynamic>;
      final coords = geom['coordinates'] as List<dynamic>;
      final List<LatLng> pts = coords.map((p) {
        final lon = (p[0] as num).toDouble();
        final lat = (p[1] as num).toDouble();
        return LatLng(lat, lon);
      }).toList();

      if (mounted) {
        setState(() {
          routePoints = pts;
        });
      }

      if (pts.isNotEmpty) {
        final avgLat = pts.map((p) => p.latitude).reduce((a, b) => a + b) / pts.length;
        final avgLon = pts.map((p) => p.longitude).reduce((a, b) => a + b) / pts.length;
        try {
          mapController.move(LatLng(avgLat, avgLon), 14.0);
        } catch (_) {}
      }
    } catch (e) {
      if (mounted) showAppMessage(context, 'Routing error: $e');
    } finally {
      if (mounted) setState(() => routing = false);
    }
  }

  void _onMapTap(TapPosition tapPos, LatLng latlng) {
    lonController.text = latlng.longitude.toStringAsFixed(6);
    latController.text = latlng.latitude.toStringAsFixed(6);
    _routeTo(latlng);
  }

  void _onSetFromInput() {
    final lon = double.tryParse(lonController.text.trim());
    final lat = double.tryParse(latController.text.trim());
    if (lon == null || lat == null) {
      if (mounted) showAppMessage(context, 'Invalid coordinates');
      return;
    }
    _routeTo(LatLng(lat, lon));
  }

  @override
  Widget build(BuildContext context) {
    final markers = <Marker>[];
    if (currentLocation != null) {
      markers.add(Marker(
        point: currentLocation!,
        width: 40,
        height: 40,
        builder: (ctx) => const Icon(Icons.my_location, color: Colors.blue, size: 28),
      ));
    }
    if (destination != null) {
      markers.add(Marker(
        point: destination!,
        width: 40,
        height: 40,
        builder: (ctx) => const Icon(Icons.location_on, color: Colors.red, size: 36),
      ));
    }

    final polylines = <Polyline>[];
    if (routePoints.isNotEmpty) {
      polylines.add(Polyline(
        points: routePoints,
        strokeWidth: 5.0,
        color: Colors.blueAccent,
      ));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('OSRM Flutter GPS')),
      body: Column(
        children: [
          Expanded(
            child: FlutterMap(
              mapController: mapController,
              options: MapOptions(
                center: currentLocation ?? LatLng(45.4215, -75.6919),
                zoom: 13.0,
                onTap: _onMapTap,
                keepAlive: true,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'org.example.osrm_flutter_gps',
                ),
                PolylineLayer(polylines: polylines),
                MarkerLayer(markers: markers),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: Colors.grey[100],
            child: Column(
              children: [
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: lonController,
                      decoration: const InputDecoration(labelText: 'Longitude'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: latController,
                      decoration: const InputDecoration(labelText: 'Latitude'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(onPressed: _onSetFromInput, child: const Text('Go')),
                ]),
                const SizedBox(height: 6),
                Row(
                  children: [
                    ElevatedButton.icon(
                      onPressed: () async {
                        await _determinePosition();
                        if (currentLocation != null) {
                          try {
                            mapController.move(currentLocation!, 15.0);
                          } catch (_) {}
                        }
                      },
                      icon: const Icon(Icons.my_location),
                      label: const Text('Center on Me'),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      onPressed: () {
                        setState(() {
                          routePoints = [];
                          destination = null;
                          lonController.clear();
                          latController.clear();
                        });
                      },
                      icon: const Icon(Icons.clear),
                      label: const Text('Clear'),
                    ),
                    const SizedBox(width: 12),
                    if (routing) const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                    const SizedBox(width: 8),
                    if (currentLocation != null) Text('You: ${currentLocation!.latitude.toStringAsFixed(5)}, ${currentLocation!.longitude.toStringAsFixed(5)}'),
                  ],
                )
              ],
            ),
          )
        ],
      ),
    );
  }
}

