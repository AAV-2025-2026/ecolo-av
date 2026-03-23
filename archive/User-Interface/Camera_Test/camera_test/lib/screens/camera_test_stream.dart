import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class CameraTestPage extends StatefulWidget {
  const CameraTestPage({super.key});

  @override
  State<CameraTestPage> createState() => _CameraTestPageState();
}

class _CameraTestPageState extends State<CameraTestPage> {
  static const String whepUrl = 'http://192.168.1.118:8889/cam1/whep';

  RTCPeerConnection? _pc;
  final RTCVideoRenderer _renderer = RTCVideoRenderer();

  String _status = 'idle';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _renderer.initialize();

    // Listen to renderer state changes safely on the platform thread
    _renderer.addListener(() {
      if (!mounted) return;
      SchedulerBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() {});
      });
    });

    await _startWhep();
  }

  Future<void> _startWhep() async {
    _safeSetState(() => _status = 'connecting');

    final config = <String, dynamic>{
      'iceServers': [
        {'urls': ['stun:stun.l.google.com:19302']},
      ],
      'sdpSemantics': 'unified-plan',
    };

    final pc = await createPeerConnection(config);
    _pc = pc;

    pc.onConnectionState = (state) {
      print('PC state: $state');
      _safeSetState(() => _status = state.toString());
    };

    pc.onTrack = (RTCTrackEvent event) {
      print('onTrack: kind=${event.track.kind} streams=${event.streams.length}');
      if (event.track.kind == 'video' && event.streams.isNotEmpty) {
        // Use postFrameCallback to set srcObject on the platform thread
        SchedulerBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          _renderer.srcObject = event.streams[0];
          _safeSetState(() => _status = 'playing');
        });
      }
    };

    await pc.addTransceiver(
      kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
      init: RTCRtpTransceiverInit(direction: TransceiverDirection.RecvOnly),
    );

    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    final localSdp = offer.sdp;
    if (localSdp == null) throw Exception('Offer SDP is null');

    print('Posting SDP to $whepUrl');
    final resp = await http.post(
      Uri.parse(whepUrl),
      headers: {
        'Content-Type': 'application/sdp',
        'Accept': 'application/sdp',
      },
      body: localSdp,
    );

    print('WHEP response: ${resp.statusCode}');
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('WHEP HTTP ${resp.statusCode}: ${resp.body}');
    }

    await pc.setRemoteDescription(RTCSessionDescription(resp.body, 'answer'));
    print('Remote description set');
  }

  // Safe setState that marshals to the platform thread
  void _safeSetState(VoidCallback fn) {
    if (!mounted) return;
    SchedulerBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(fn);
    });
  }

  @override
  void dispose() {
    _renderer.dispose();
    _pc?.close();
    _pc = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hasVideo = _renderer.srcObject != null;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Camera Test'),
        backgroundColor: Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
        centerTitle: true,
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: hasVideo
                ? RTCVideoView(
                    _renderer,
                    objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitContain,
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(color: Colors.white),
                        const SizedBox(height: 16),
                        Text(
                          _status,
                          style: const TextStyle(color: Colors.white70),
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