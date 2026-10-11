import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_pi/util/ipc.dart';

import '../services/backend.dart';

/// The camera: the back end's newest picture of /camera/image_raw, fetched from
/// /camera/latest.png a few times a second. The back end subscribes to the camera only
/// while someone fetches, so it costs nothing while this page is closed.
class CameraPage extends StatefulWidget {
  const CameraPage({
    super.key,
    this.backend,
    this.period = const Duration(milliseconds: 200),
  });

  /// For tests. Null: the real back end, at kBackendUrl.
  final HudBackend? backend;

  /// How often to fetch: 5 a second, as the back end's camera_fps.
  final Duration period;

  @override
  State<CameraPage> createState() => _CameraPageState();
}

class _CameraPageState extends State<CameraPage> {
  late final HudBackend _backend = widget.backend ?? HudBackend();
  Timer? _timer;
  bool _fetching = false;

  Uint8List? _picture;
  String _status = 'connecting';

  @override
  void initState() {
    super.initState();
    _fetch();
    _timer = Timer.periodic(widget.period, (_) => _fetch());
  }

  Future<void> _fetch() async {
    if (_fetching) return; // the last one is still on its way
    _fetching = true;
    final picture = await _backend.cameraPicture();
    _fetching = false;
    if (!mounted) return;
    setState(() {
      if (picture.png != null) _picture = picture.png;
      _status = picture.status;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    if (widget.backend == null) _backend.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final picture = _picture;
    final live = _status == 'live';

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Camera'),
        backgroundColor: Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            sendCommand('map');
          },
        ),
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child:
                picture != null
                    ? Image.memory(
                      picture,
                      fit: BoxFit.contain,
                      gaplessPlayback: true,
                    )
                    : Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const CircularProgressIndicator(color: Colors.white),
                          const SizedBox(height: 16),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 32),
                            child: Text(
                              _status,
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: Colors.white70),
                            ),
                          ),
                        ],
                      ),
                    ),
          ),
          // An old picture must not pass for a live one.
          if (picture != null && !live)
            Positioned(
              left: 12,
              right: 12,
              bottom: 12,
              child: Container(
                padding: const EdgeInsets.all(8),
                color: Colors.red.shade900,
                child: Text(
                  'Not live: $_status',
                  style: const TextStyle(color: Colors.white, fontSize: 16),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
