import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_pi/screens/camera_page.dart';
import 'package:flutter_pi/util/ipc.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_onscreen_keyboard/flutter_onscreen_keyboard.dart';
import 'package:flutter_typeahead/flutter_typeahead.dart';
import '../data/constants.dart';

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

class MapPage extends StatefulWidget {
  const MapPage({super.key});
  @override
  State<MapPage> createState() => _MapPageState();
}

class _MapPageState extends State<MapPage> {
  String osrmBaseUrl = kOsrmBaseUrl;

  // Photon base (adjust if you run Photon on another host/port or use a proxy)
  // If testing on Android emulator and Photon runs on host, use 'http://10.0.2.2:2322/api/'
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

  // New fields for locking and GPS tracking
  bool routeLocked = false;
  StreamSubscription<Position>? _positionSub;
  List<LatLng> lockedRoutePoints = []; // original route when locked
  String? lastRouteJson; // exported JSON of lat/lon for ROS2 later

  // Simulation fields
  List<LatLng> _simPoints = [];
  int _simIndex = 0;
  Timer? _simTimer;
  bool _simPlaying = false;
  double _simSpeedMultiplier = 1.0; // 1x, 2x, etc.
  int _simBaseIntervalMs = 1000; // base interval between points (ms)

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _determinePosition();
    });
  }

  @override
  void dispose() {
    _positionSub?.cancel();
    _simTimer?.cancel();
    lonController.dispose();
    latController.dispose();
    searchController.dispose();
    super.dispose();
  }

  Future<void> _determinePosition() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        if (mounted)
          showAppMessage(
            context,
            'Location services disabled - using fallback',
          );
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          if (mounted)
            showAppMessage(
              context,
              'Location permission denied - using fallback',
            );
        }
      }
      if (permission == LocationPermission.deniedForever) {
        if (mounted)
          showAppMessage(
            context,
            'Location permission denied forever - using fallback',
          );
      }

      try {
        Position pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.best,
          timeLimit: const Duration(seconds: 8),
        );
        if (mounted) {
          setState(() {
            currentLocation = LatLng(pos.latitude, pos.longitude);
          });
          try {
            mapController.move(currentLocation!, 15.0);
          } catch (_) {}
        }
        return;
      } catch (e) {
        if (mounted)
          showAppMessage(context, 'Could not get position (provider): $e');
      }
    } catch (e) {
      if (mounted) showAppMessage(context, 'Location check failed: $e');
    }

    if (mounted && currentLocation == null) {
      setState(() {
        currentLocation = LatLng(45.385007, -75.698293);
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
      // When a new route is requested, ensure it's not locked
      routeLocked = false;
      lockedRoutePoints = [];
      lastRouteJson = null;
    });

    final src = '${currentLocation!.longitude},${currentLocation!.latitude}';
    final dst = '${dest.longitude},${dest.latitude}';
    final url = Uri.parse(
      '$osrmBaseUrl/route/v1/driving/$src;$dst?overview=full&geometries=geojson&steps=true',
    );

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
      final List<LatLng> pts =
          coords.map((p) {
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
        final avgLat =
            pts.map((p) => p.latitude).reduce((a, b) => a + b) / pts.length;
        final avgLon =
            pts.map((p) => p.longitude).reduce((a, b) => a + b) / pts.length;
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

  // New helper to lock the route
  void _lockRoute() {
    print("LOCK ROUTE CALLED");  // debug line
    showAppMessage(context, 'debug: _lockRoute() called');
  
    if (routePoints.isEmpty) {
      showAppMessage(context, 'No route to lock');
      return;
    }
    if (currentLocation == null) {
      showAppMessage(context, 'Current location unknown');
      return;
    }

    // Save the route as lockedRoutePoints (immutable copy)
    lockedRoutePoints = List<LatLng>.from(routePoints);
    routeLocked = true;

    // Export the route as JSON array of {lat, lon}
    final export = lockedRoutePoints
        .map((p) => {'lat': p.latitude, 'lon': p.longitude})
        .toList();
    lastRouteJson = json.encode(export);

    // Print and show a short message with the JSON (for debugging / later ROS2)
    // ignore: avoid_print
    print('Locked route JSON: $lastRouteJson');
    showAppMessage(context, 'Route locked and exported (${lockedRoutePoints.length} points)');

    // send the new route to Flask
    sendRouteToFlask(lastRouteJson!);
    
    // Zoom to current position and start tracking
    try {
      mapController.move(currentLocation!, 16.0);
    } catch (_) {}

    _startTrackingAndPrune();
    setState(() {});
  }
  
  // Helper function to send the new route obtained from _lockRoute() to Flask 
  Future<void> sendRouteToFlask(String jsonString) async {
    // TODO: remove all "debug" lines in this function when done
    // TODO: remove all Future.delayed() functions, the pauses were to help with debugging
    
    // request to send Flask (on port 5000, on this machine) some data
    final url = Uri.parse('http://localhost:5000/receive');  
    
    // prompts on screen (for myself to debug)
    showAppMessage(context, 'debug: sendRouteToFlask() called');        // debug
    await Future.delayed(Duration(seconds: 3)); 			// debug
    
    try {
    	showAppMessage(context, 'trying now...');			// debug
    	await Future.delayed(Duration(seconds: 3)); 			// debug
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonString,
      );
  	
  	showAppMessage(context, 'trying worked..');			 // debug
  	await Future.delayed(Duration(seconds: 3));			 // debug
  	
      if (response.statusCode == 200) {
        print("Successfully sent route to Flask: ${response.body}");
        showAppMessage(context, "debug: Successfully sent route to Flask: ${response.body}");
      } else {
        print("Failed to send route. Status code: ${response.statusCode}");
        showAppMessage(context, "debug: Failed to send route. Status code: ${response.statusCode}");
      }
    } catch (e) {
      print("Error sending route to Flask: $e");
      showAppMessage(context, "debug: Error sending route to Flask: $e");
    }
  }

  // Unlock route and stop tracking
  void _unlockRoute() {
    print('_unlockRoute() was called'); // debug line
  
    routeLocked = false;
    _positionSub?.cancel();
    _positionSub = null;
    // restore routePoints to the lockedRoutePoints so user can re-lock or re-route
    routePoints = List<LatLng>.from(lockedRoutePoints);
    lockedRoutePoints = [];
    showAppMessage(context, 'Route unlocked');
    setState(() {});
  }

  // Start a position stream and prune routePoints behind current location
  void _startTrackingAndPrune() {
    _positionSub?.cancel();

    // Use a distance filter to reduce updates; adjust as needed
    const int distanceFilterMeters = 3;

    _positionSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.best,
        distanceFilter: distanceFilterMeters,
      ),
    ).listen((Position pos) {
      if (!mounted) return;
      setState(() {
        currentLocation = LatLng(pos.latitude, pos.longitude);
      });

      // If route is locked and we have route points, prune points behind current location
      if (routeLocked && routePoints.isNotEmpty) {
        _pruneRouteBehindCurrent();
      }

      // If we are within a small threshold of destination, clear and stop tracking
      if (destination != null) {
        final distToDest = Distance().distance(currentLocation!, destination!);
        if (distToDest <= 8.0) {
          // reached destination
          showAppMessage(context, 'Destination reached');
          _positionSub?.cancel();
          _positionSub = null;
          setState(() {
            routeLocked = false;
            routePoints = [];
            lockedRoutePoints = [];
            destination = null;
          });
        }
      }
    }, onError: (e) {
      // ignore stream errors but notify
      showAppMessage(context, 'GPS stream error: $e');
    });
  }

  // Remove route points that are behind the current location
  void _pruneRouteBehindCurrent() {
    if (currentLocation == null || routePoints.isEmpty) return;

    // Find the index of the nearest route point to currentLocation
    int nearestIndex = 0;
    double nearestDist = double.infinity;
    final distCalc = Distance();

    for (int i = 0; i < routePoints.length; i++) {
      final d = distCalc.distance(currentLocation!, routePoints[i]);
      if (d < nearestDist) {
        nearestDist = d;
        nearestIndex = i;
      }
    }

    // If nearestIndex is not the first point, drop all points before it
    if (nearestIndex > 0) {
      setState(() {
        routePoints = routePoints.sublist(nearestIndex);
      });
    }
  }

  /// Parse CSV-like text. Accepts lines with latitude,longitude anywhere in the line.
  /// Returns list of LatLng in order.
  List<LatLng> _parseCsvToLatLng(String csvText) {
    final lines = csvText.split(RegExp(r'[\r\n]+'));
    final List<LatLng> pts = [];
    for (final raw in lines) {
      final line = raw.trim();
      if (line.isEmpty) continue;
      // Try to find two numeric columns that look like lat,lon
      final cols = line.split(',');
      for (int i = 0; i < cols.length - 1; i++) {
        final a = cols[i].trim();
        final b = cols[i + 1].trim();
        final lat = double.tryParse(a);
        final lon = double.tryParse(b);
        if (lat != null && lon != null) {
          if (lat.abs() <= 90 && lon.abs() <= 180) {
            pts.add(LatLng(lat, lon));
            break;
          }
        } else {
          final lon2 = double.tryParse(a);
          final lat2 = double.tryParse(b);
          if (lat2 != null && lon2 != null && lat2.abs() <= 90 && lon2.abs() <= 180) {
            pts.add(LatLng(lat2, lon2));
            break;
          }
        }
      }
    }
    return pts;
  }

  /// Start simulation from _simPoints at _simIndex
  void _startSimulation() {
    if (_simPoints.isEmpty) {
      showAppMessage(context, 'No simulation points loaded');
      return;
    }
    _simTimer?.cancel();
    _simPlaying = true;
    final interval = (_simBaseIntervalMs / _simSpeedMultiplier).round();
    _simTimer = Timer.periodic(Duration(milliseconds: interval), (t) {
      if (!mounted) return;
      if (_simIndex >= _simPoints.length) {
        _stopSimulation();
        showAppMessage(context, 'Simulation finished');
        return;
      }
      final p = _simPoints[_simIndex++];
      setState(() {
        currentLocation = p;
      });
      try {
        mapController.move(currentLocation!, 15.0);
      } catch (_) {}
      // If route is locked, prune behind current
      if (routeLocked && routePoints.isNotEmpty) {
        _pruneRouteBehindCurrent();
      }
    });
    setState(() {});
  }

  void _pauseSimulation() {
    _simTimer?.cancel();
    _simTimer = null;
    _simPlaying = false;
    setState(() {});
  }

  void _stopSimulation() {
    _simTimer?.cancel();
    _simTimer = null;
    _simPlaying = false;
    _simIndex = 0;
    setState(() {});
  }

  /// Load CSV text into simulation buffer and reset index
  void _loadSimulationFromCsv(String csvText) {
    final pts = _parseCsvToLatLng(csvText);
    if (pts.isEmpty) {
      showAppMessage(context, 'No valid lat/lon found in pasted data');
      return;
    }
    _simPoints = pts;
    _simIndex = 0;
    showAppMessage(context, 'Loaded ${_simPoints.length} simulation points');
    try {
      mapController.move(_simPoints.first, 15.0);
    } catch (_) {}
    setState(() {});
  }

  /// Step one point forward (useful for debugging)
  void _stepSimulation() {
    if (_simPoints.isEmpty) return;
    if (_simIndex >= _simPoints.length) {
      showAppMessage(context, 'End of simulation');
      return;
    }
    final p = _simPoints[_simIndex++];
    setState(() {
      currentLocation = p;
    });
    try {
      mapController.move(currentLocation!, 15.0);
    } catch (_) {}
    if (routeLocked && routePoints.isNotEmpty) _pruneRouteBehindCurrent();
  }

  @override
  Widget build(BuildContext context) {
    final markers = <Marker>[];
    if (currentLocation != null) {
      markers.add(
        Marker(
          point: currentLocation!,
          width: 40,
          height: 40,
          builder:
              (ctx) =>
                  const Icon(Icons.my_location, color: Colors.white, size: 28),
        ),
      );
    }
    if (destination != null) {
      markers.add(
        Marker(
          point: destination!,
          width: 40,
          height: 40,
          builder:
              (ctx) => Icon(
                Icons.location_on,
                color: Colors.deepPurple.shade300,
                size: 36,
              ),
        ),
      );
    }

    final polylines = <Polyline>[];
    if (routePoints.isNotEmpty) {
      polylines.add(
        Polyline(
          points: routePoints,
          strokeWidth: 5.0,
          color: Colors.deepPurple.shade300,
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('OSRM Map'),
        backgroundColor: Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          // Full-screen map
          Positioned.fill(
            child: FlutterMap(
              mapController: mapController,
              options: MapOptions(
                center: currentLocation ?? LatLng(45.385007, -75.698293),
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
                        style: const TextStyle(color: Colors.black87),
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
                        final raw = suggestion['raw'] as Map<String, dynamic>? ?? {};
                        final props = raw['properties'] as Map<String, dynamic>? ?? {};
                        final street = props['street'];
                        final housenumber = props['housenumber'];
                        final city = props['city'] ?? props['locality'] ?? props['district'];
                        final state = props['state'];
                        final subtitleParts = [
                          if (housenumber != null) housenumber,
                          if (street != null) street,
                          if (city != null) city,
                          if (state != null) state
                        ].where((e) => e != null).join(', ');

                        return ListTile(
                          title: Text(suggestion['display'] ?? ''),
                          subtitle: Text(subtitleParts.isNotEmpty
                              ? subtitleParts
                              : '${(suggestion['lat'] as double).toStringAsFixed(5)}, ${(suggestion['lon'] as double).toStringAsFixed(5)}'),
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
              color: Colors.black,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: OnscreenKeyboardTextField(
                          controller: lonController,
                          keyboardType: const TextInputType.numberWithOptions(
                            signed: true,
                            decimal: true,
                          ),
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            labelText: 'Longitude',
                            labelStyle: const TextStyle(color: Colors.white70),
                            enabledBorder: OutlineInputBorder(
                              borderSide: BorderSide(
                                color: Colors.deepPurple.shade300,
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderSide: BorderSide(
                                color: Colors.deepPurple.shade700,
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OnscreenKeyboardTextField(
                          controller: latController,
                          keyboardType: const TextInputType.numberWithOptions(
                            signed: true,
                            decimal: true,
                          ),
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            labelText: 'Latitude',
                            labelStyle: const TextStyle(color: Colors.white70),
                            enabledBorder: OutlineInputBorder(
                              borderSide: BorderSide(
                                color: Colors.deepPurple.shade300,
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderSide: BorderSide(
                                color: Colors.deepPurple.shade700,
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.deepPurple.shade300,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _onSetFromInput,
                        child: const Text('Go'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.deepPurple.shade300,
                          foregroundColor: Colors.white,
                        ),
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
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.deepPurple.shade700,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: () {
                          setState(() {
                            routePoints = [];
                            destination = null;
                            lonController.clear();
                            latController.clear();
                            // also cancel any lock/tracking
                            _positionSub?.cancel();
                            _positionSub = null;
                            routeLocked = false;
                            lockedRoutePoints = [];
                            lastRouteJson = null;
                          });
                        },
                        icon: const Icon(Icons.clear),
                        label: const Text('Clear'),
                      ),
                      const SizedBox(width: 12),
                      if (routing)
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.deepPurple.shade300,
                          ),
                        ),
                      const SizedBox(width: 8),
                      if (currentLocation != null)
                        Text(
                          'You: ${currentLocation!.latitude.toStringAsFixed(5)}, ${currentLocation!.longitude.toStringAsFixed(5)}',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                      const SizedBox(width: 8),
                      // Lock / Unlock button
                      if (routePoints.isNotEmpty && !routeLocked)
                        ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green.shade600,
                            foregroundColor: Colors.white,
                          ),
                          onPressed: _lockRoute,
                          icon: const Icon(Icons.lock),
                          label: const Text('Lock Route'),
                        ),
                      if (routeLocked)
                        ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.orange.shade700,
                            foregroundColor: Colors.white,
                          ),
                          onPressed: _unlockRoute,
                          icon: const Icon(Icons.lock_open),
                          label: const Text('Unlock'),
                        ),
                      const SizedBox(width: 8),
                      // Simulation controls (small icons)
                      IconButton(
                        icon: Icon(_simPlaying ? Icons.pause_circle : Icons.play_circle, color: Colors.white),
                        onPressed: () {
                          if (_simPlaying) {
                            _pauseSimulation();
                          } else {
                            _startSimulation();
                          }
                        },
                      ),
                      IconButton(
                        icon: const Icon(Icons.stop, color: Colors.white),
                        onPressed: _stopSimulation,
                      ),
                      IconButton(
                        icon: const Icon(Icons.skip_next, color: Colors.white),
                        onPressed: _stepSimulation,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Colors.deepPurple.shade300,
        icon: const Icon(Icons.playlist_play),
        label: const Text('Simulate Trace'),
        onPressed: () {
          showDialog(
            context: context,
            builder: (ctx) {
              final TextEditingController csvController = TextEditingController();
              return StatefulBuilder(builder: (ctx2, setStateDialog) {
                return AlertDialog(
                  title: const Text('Paste CSV / trace lines'),
                  content: SizedBox(
                    width: double.maxFinite,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        TextField(
                          controller: csvController,
                          maxLines: 10,
                          decoration: const InputDecoration(
                            hintText: 'Paste CSV lines here (type,date time,lat,lon,...)',
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            const Text('Speed'),
                            Expanded(
                              child: Slider(
                                value: _simSpeedMultiplier,
                                min: 0.25,
                                max: 8.0,
                                divisions: 31,
                                label: '${_simSpeedMultiplier.toStringAsFixed(2)}x',
                                onChanged: (v) {
                                  setStateDialog(() {
                                    _simSpeedMultiplier = v;
                                  });
                                  setState(() {}); // update outer state too
                                  // If playing, restart timer with new interval
                                  if (_simPlaying) {
                                    _pauseSimulation();
                                    _startSimulation();
                                  }
                                },
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text('Points loaded: ${_simPoints.length}'),
                      ],
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () {
                        // load CSV into sim buffer
                        _loadSimulationFromCsv(csvController.text);
                        setStateDialog(() {});
                      },
                      child: const Text('Load'),
                    ),
                    TextButton(
                      onPressed: () {
                        Navigator.of(ctx).pop();
                      },
                      child: const Text('Close'),
                    ),
                  ],
                );
              });
            },
          );
        },
      ),
    );
  }
}

class MapPageController extends StatefulWidget {
  const MapPageController({super.key});
  @override
  State<MapPageController> createState() => _MapPageControllerState();
}

class _MapPageControllerState extends State<MapPageController> {
  bool _showCamera = false;
  late Timer _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 300), (_) {
      final cmd = readAndClearCommand();
      if (cmd == 'camera') setState(() => _showCamera = true);
      if (cmd == 'map') setState(() => _showCamera = false);
    });
  }

  @override
  void dispose() { _timer.cancel(); super.dispose(); }

  @override
  Widget build(BuildContext context) => IndexedStack(
    index: _showCamera ? 1 : 0,
    children: const [
      MapPage(),
      CameraPage(),
    ],
  );
}
