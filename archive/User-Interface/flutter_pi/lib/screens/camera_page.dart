import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class CameraPage extends StatefulWidget {
  const CameraPage({super.key});

  @override
  State<CameraPage> createState() => _CameraPageState();
}

class _CameraPageState extends State<CameraPage> {
  static const String whepUrl = 'http://192.168.1.101:8889/cam1/whep';

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
    await _startWhep();
  }

  Future<void> _startWhep() async {
    setState(() => _status = 'connecting');

    final config = <String, dynamic>{
      "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
      ],
      "sdpSemantics": "unified-plan",
    };

    final pc = await createPeerConnection(config);
    _pc = pc;

    pc.onConnectionState = (state) {
      // ignore: avoid_print
      print('PC state: $state');
      if (!mounted) return;
      setState(() => _status = state.toString());
    };

    pc.onTrack = (RTCTrackEvent event) {
      if (event.track.kind == 'video' && event.streams.isNotEmpty) {
        _renderer.srcObject = event.streams[0];
        if (!mounted) return;
        setState(() => _status = 'playing');
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

    final resp = await http.post(
      Uri.parse(whepUrl),
      headers: {
        'Content-Type': 'application/sdp',
        'Accept': 'application/sdp',
      },
      body: localSdp,
    );

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('WHEP HTTP ${resp.statusCode}: ${resp.body}');
    }

    final answer = RTCSessionDescription(resp.body, 'answer');
    await pc.setRemoteDescription(answer);
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
    return Scaffold(
      backgroundColor: Colors.grey.shade100,
      appBar: AppBar(
        title: const Text('Camera Test'),
        backgroundColor: Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: (_renderer.srcObject == null)
                ? const SizedBox.expand()
                : RTCVideoView(
                    _renderer,
                    objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitContain,
                  ),
          ),

          // keep invisible (or delete)
          Positioned(
            left: 12,
            bottom: 12,
            child: Opacity(
              opacity: 0.0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _status,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
