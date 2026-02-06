import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class CameraTestPage extends StatefulWidget {
  const CameraTestPage({super.key});

  @override
  State<CameraTestPage> createState() => _CameraTestPageState();
}

class _CameraTestPageState extends State<CameraTestPage> {
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

    // Minimal ICE config for LAN (usually OK). If needed, add STUN.
    final config = <String, dynamic>{
      "iceServers": [
        // LAN-only often works without STUN, but leaving a STUN is fine:
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

    // Create a "recvonly" transceiver for video
    await pc.addTransceiver(
      kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
      init: RTCRtpTransceiverInit(direction: TransceiverDirection.RecvOnly),
    );

    // Offer/answer via WHEP
    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    final localSdp = offer.sdp;
    if (localSdp == null) {
      throw Exception('Offer SDP is null');
    }

    // POST SDP to WHEP endpoint
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

    final answerSdp = resp.body;
    final answer = RTCSessionDescription(answerSdp, 'answer');
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
      ),
      body: Stack(
        children: [
          // Camera view (blank until track arrives)
          Positioned.fill(
            child: (_renderer.srcObject == null)
                ? const SizedBox.expand() // blank background as requested
                : RTCVideoView(_renderer, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitContain),
          ),

          // Optional tiny status in a corner (remove if you want strictly no overlay)
          Positioned(
            left: 12,
            bottom: 12,
            child: Opacity(
              opacity: 0.0, // set to 0.8 if you want to see status
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
