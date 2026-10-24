import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_typeahead/flutter_typeahead.dart';

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

  // Photon base (adjust if you run Photon on another host/port or use a proxy)
  String photonBaseUrl = 'http://localhost:2322/api/';

  final MapController mapController = MapController();
  LatLng? currentLocation;
  LatLng? destination;
  List<LatLng> routePoints = [];
  bool routing = false;
  final TextEditingController lonController = TextEditingController();
  final TextEditingController latController = TextEditingController();

  // Search controller for the address bar
  final TextEditingController searchController = TextEditingController();

  // Lock/tracking state
  bool routeLocked = false;
  List<LatLng> lockedRoutePoints = [];
  String? lockedRouteCoordsJson;
  StreamSubscription<Position>? positionStreamSub;

  final Distance distanceCalc = const Distance();

  @override
  void initState() {
    super.initState();
    // Delay position attempt until after first frame so ScaffoldMessenger is available
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _determinePosition();
    });
  }

  @override
  void dispose() {
    positionStreamSub?.cancel();
    super.dispose();
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
        Position pos = await Geolocator.getCurrentPosition(
            desiredAccuracy: LocationAccuracy.best, timeLimit: const Duration(seconds: 8));
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
    if (routeLocked) {
      if (mounted) showAppMessage(context, 'Route is locked. Clear/unlock to set a new route.');
      return;
    }

    setState(() {
      routing = true;
      destination = dest;
      routePoints = [];
    });

    final src = '${currentLocation!.longitude},${currentLocation!.latitude}';
    final dst = '${dest.longitude},${dest.latitude}';
    final url = Uri.parse(
        '$osrmBaseUrl/route/v1/driving/$src;$dst?overview=full&geometries=geojson&steps=true');

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

  /// Query Photon for suggestions. Returns a list of maps:
  /// { 'display': String, 'lat': double, 'lon': double, 'raw': Map }
  Future<List<Map<String, dynamic>>> _getPhotonSuggestions(String pattern) async {
    if (pattern.trim().isEmpty) return [];
    try {
      final uri = Uri.parse('$photonBaseUrl?q=${Uri.encodeComponent(pattern)}&limit=6');
      final resp = await http.get(uri).timeout(const Duration(seconds: 5));
      if (resp.statusCode != 200) return [];
      final jsonBody = json.decode(resp.body) as Map<String, dynamic>;
      final features = (jsonBody['features'] as List<dynamic>? ?? []);
      final List<Map<String, dynamic>> results = [];
      for (final f in features) {
        try {
          final feature = f as Map<String, dynamic>;
          final props = feature['properties'] as Map<String, dynamic>? ?? {};
          final geom = feature['geometry'] as Map<String, dynamic>?;
          double? lat;
          double? lon;
          if (geom != null && geom['coordinates'] is List && (geom['coordinates'] as List).length >= 2) {
            final coords = geom['coordinates'] as List;
            lon = (coords[0] as num).toDouble();
            lat = (coords[1] as num).toDouble();
          } else {
            // fallback: some Photon builds may include extent or lat/lon in properties
            if (props.containsKey('extent') && props['extent'] is List) {
              final extent = props['extent'] as List;
              // extent is [minLon, minLat, maxLon, maxLat] — use center
              final minLon = (extent[0] as num).toDouble();
              final minLat = (extent[1] as num).toDouble();
              final maxLon = (extent[2] as num).toDouble();
              final maxLat = (extent[3] as num).toDouble();
              lon = (minLon + maxLon) / 2.0;
              lat = (minLat + maxLat) / 2.0;
            } else if (props.containsKey('lat') && props.containsKey('lon')) {
              lat = (props['lat'] as num).toDouble();
              lon = (props['lon'] as num).toDouble();
            }
          }

          final display = props['name'] ??
              props['label'] ??
              [
                if (props['housenumber'] != null) props['housenumber'],
                if (props['street'] != null) props['street'],
                if (props['city'] != null) props['city'],
                if (props['state'] != null) props['state']
              ].where((e) => e != null).join(', ');

          if (lat != null && lon != null) {
            results.add({
              'display': display ?? 'Unknown',
              'lat': lat,
              'lon': lon,
              'raw': feature,
            });
          }
        } catch (_) {
          // ignore malformed feature
        }
      }
      return results;
    } catch (_) {
      return [];
    }
  }

  /// Lock the current routePoints. Copies routePoints to lockedRoutePoints,
  /// exports JSON, zooms to current position, and starts tracking/pruning.
  void _lockRoute() {
    if (routePoints.isEmpty) {
      showAppMessage(context, 'No route to lock');
      return;
    }
    if (routeLocked) {
      showAppMessage(context, 'Route already locked');
      return;
    }

    setState(() {
      routeLocked = true;
      lockedRoutePoints = List<LatLng>.from(routePoints);
      lockedRouteCoordsJson = jsonEncode(lockedRoutePoints
          .map((p) => {'lat': p.latitude.toDouble(), 'lon': p.longitude.toDouble()})
          .toList());
    });

    showAppMessage(context, 'Route locked. Exported ${lockedRoutePoints.length} points.');
    // ignore: avoid_print
    print('Locked route coordinates JSON: $lockedRouteCoordsJson');

    // Zoom to current position if available
    if (currentLocation != null) {
      try {
        mapController.move(currentLocation!, 15.0);
      } catch (_) {}
    }

    // Start listening to position updates to prune the route behind the user
    positionStreamSub?.cancel();
    positionStreamSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 2,
      ),
    ).listen((pos) {
      if (!mounted) return;
      final newLoc = LatLng(pos.latitude, pos.longitude);
      setState(() {
        currentLocation = newLoc;
      });

      if (lockedRoutePoints.isEmpty) {
        positionStreamSub?.cancel();
        positionStreamSub = null;
        if (mounted) showAppMessage(context, 'Route exhausted.');
        return;
      }

      // Find nearest index on lockedRoutePoints to currentLocation
      int nearestIndex = 0;
      double nearestDist = double.infinity;
      for (int i = 0; i < lockedRoutePoints.length; i++) {
        final d = distanceCalc(
            LatLng(lockedRoutePoints[i].latitude, lockedRoutePoints[i].longitude),
            newLoc);
        if (d < nearestDist) {
          nearestDist = d;
          nearestIndex = i;
        }
      }

      // Prune logic: if nearest point is within pruneThresholdMeters, remove up to it
      const double pruneThresholdMeters = 10.0;
      if (nearestDist <= pruneThresholdMeters) {
        setState(() {
          if (nearestIndex + 1 < lockedRoutePoints.length) {
            lockedRoutePoints = lockedRoutePoints.sublist(nearestIndex + 1);
          } else {
            lockedRoutePoints = [];
          }
        });
      } else {
        // Optionally remove points that are clearly behind (e.g., > behindThresholdMeters)
        const double behindThresholdMeters = 30.0;
        int firstKeep = 0;
        for (int i = 0; i < lockedRoutePoints.length; i++) {
          final d = distanceCalc(
              LatLng(lockedRoutePoints[i].latitude, lockedRoutePoints[i].longitude),
              newLoc);
          if (d <= behindThresholdMeters) {
            firstKeep = i;
            break;
          }
          if (i == lockedRoutePoints.length - 1) {
            firstKeep = 0;
          }
        }
        if (firstKeep > 0) {
          setState(() {
            lockedRoutePoints = lockedRoutePoints.sublist(firstKeep);
          });
        }
      }

      // Keep map centered on current location while locked
      if (currentLocation != null) {
        try {
          mapController.move(currentLocation!, 15.0);
        } catch (_) {}
      }

      // If close to destination, stop tracking
      if (destination != null) {
        final distToDest = distanceCalc(destination!, newLoc);
        if (distToDest <= 8.0) {
          positionStreamSub?.cancel();
          positionStreamSub = null;
          if (mounted) {
            showAppMessage(context, 'Arrived at destination.');
            setState(() {
              lockedRoutePoints = [];
            });
          }
        }
      }
    });
  }

  /// Unlock and clear everything, stop tracking
  void _unlockAndClear() {
    positionStreamSub?.cancel();
    positionStreamSub = null;
    setState(() {
      routeLocked = false;
      lockedRoutePoints = [];
      routePoints = [];
      destination = null;
      lockedRouteCoordsJson = null;
      lonController.clear();
      latController.clear();
    });
    showAppMessage(context, 'Route cleared and unlocked.');
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
    if (routeLocked) {
      if (lockedRoutePoints.isNotEmpty) {
        polylines.add(Polyline(
          points: lockedRoutePoints,
          strokeWidth: 5.0,
          color: Colors.greenAccent,
        ));
      }
    } else {
      if (routePoints.isNotEmpty) {
        polylines.add(Polyline(
          points: routePoints,
          strokeWidth: 5.0,
          color: Colors.blueAccent,
        ));
      }
    }

    return Scaffold(
      appBar: AppBar(title: const Text('OSRM Flutter GPS')),
      body: Stack(
        children: [
          // Full-screen map
          Positioned.fill(
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

          // Top-left search box (SafeArea + small width)
          Positioned(
            top: 12,
            left: 12,
            child: SafeArea(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.65),
                child: Material(
                  elevation: 6,
                  borderRadius: BorderRadius.circular(8),
                  color: Colors.white,
                  child: Padding(
                    padding: const EdgeInsets.all(6.0),
                    child: TypeAheadField<Map<String, dynamic>>(
                      textFieldConfiguration: TextFieldConfiguration(
                        controller: searchController,
                        decoration: InputDecoration(
                          hintText: 'Search address or place',
                          prefixIcon: const Icon(Icons.search),
                          suffixIcon: IconButton(
                            icon: const Icon(Icons.clear),
                            onPressed: () {
                              searchController.clear();
                            },
                          ),
                          border: InputBorder.none,
                          isDense: true,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                        ),
                      ),
                      suggestionsCallback: (pattern) => _getPhotonSuggestions(pattern),
                      itemBuilder: (context, suggestion) {
                        return ListTile(
                          title: Text(suggestion['display'] ?? ''),
                          subtitle: Text(
                              '${(suggestion['lat'] as double).toStringAsFixed(5)}, ${(suggestion['lon'] as double).toStringAsFixed(5)}'),
                        );
                      },
                      onSuggestionSelected: (suggestion) {
                        final lat = suggestion['lat'] as double;
                        final lon = suggestion['lon'] as double;
                        searchController.text = suggestion['display'] ?? '';
                        _routeTo(LatLng(lat, lon));
                      },
                      debounceDuration: const Duration(milliseconds: 300),
                      noItemsFoundBuilder: (context) => Container(
                        padding: const EdgeInsets.all(12),
                        child: const Text('No results'),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Bottom controls (keep them visible above the map)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: Colors.grey[100],
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(children: [
                    Expanded(
                      child: TextField(
                        controller: lonController,
                        decoration: const InputDecoration(labelText: 'Longitude'),
                        keyboardType:
                            const TextInputType.numberWithOptions(decimal: true, signed: true),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: latController,
                        decoration: const InputDecoration(labelText: 'Latitude'),
                        keyboardType:
                            const TextInputType.numberWithOptions(decimal: true, signed: true),
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
                          _unlockAndClear();
                        },
                        icon: const Icon(Icons.clear),
                        label: Text(routeLocked ? 'Clear & Unlock' : 'Clear'),
                      ),
                      const SizedBox(width: 12),
                      if (routing)
                        const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                      const SizedBox(width: 8),
                      if (!routeLocked && routePoints.isNotEmpty)
                        ElevatedButton.icon(
                          onPressed: _lockRoute,
                          icon: const Icon(Icons.lock),
                          label: const Text('Lock Route'),
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.green),
                        ),
                      const SizedBox(width: 8),
                      if (currentLocation != null)
                        Text('You: ${currentLocation!.latitude.toStringAsFixed(5)}, ${currentLocation!.longitude.toStringAsFixed(5)}'),
                    ],
                  ),
                  if (routeLocked && lockedRouteCoordsJson != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6.0),
                      child: Text(
                        'Locked route points: ${lockedRoutePoints.length}',
                        style: const TextStyle(fontSize: 12, color: Colors.black54),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

