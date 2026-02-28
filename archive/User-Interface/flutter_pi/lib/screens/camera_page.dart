import 'dart:async';

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

  Timer? _watchdogTimer;
  bool _reconnecting = false;

  // watchdog parameters
  static const Duration _watchdogTick = Duration(seconds: 2);
  static const Duration _stallThreshold = Duration(seconds: 6); // no frames for 6s => reconnect

  int _lastFrames = -1;
  DateTime _lastFrameProgressAt = DateTime.fromMillisecondsSinceEpoch(0);

  // reconnection backoff
  int _retryCount = 0;

  String _status = 'idle';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _renderer.initialize();
    await _connectFresh();
    _startWatchdog();
  }

  void _startWatchdog() {
    _watchdogTimer?.cancel();
    _watchdogTimer = Timer.periodic(_watchdogTick, (_) async {
      if (!mounted) return;
      final pc = _pc;
      if (pc == null) return;

      // If we are already reconnecting, don't stack reconnects.
      if (_reconnecting) return;

      try {
        final frames = await _getInboundVideoFrames(pc);
        if (frames != null) {
          if (_lastFrames == -1) {
            // first measurement
            _lastFrames = frames;
            _lastFrameProgressAt = DateTime.now();
            return;
          }

          if (frames > _lastFrames) {
            _lastFrames = frames;
            _lastFrameProgressAt = DateTime.now();
          } else {
            // no progress
            final stalledFor = DateTime.now().difference(_lastFrameProgressAt);
            if (stalledFor >= _stallThreshold) {
              await _reconnect(reason: 'watchdog: stalled for ${stalledFor.inSeconds}s');
            }
          }
        } else {
          // If we can't read frames stats, fall back to connection state.
          final state = pc.connectionState;
          if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
              state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected ||
              state == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
            await _reconnect(reason: 'watchdog: bad state $state');
          }
        }
      } catch (_) {
        // Stats calls can throw if PC is closing; ignore.
      }
    });
  }

  /// Returns framesDecoded/framesReceived from inbound-rtp(video). Null if not found.
Future<int?> _getInboundVideoFrames(RTCPeerConnection pc) async {
  final stats = await pc.getStats();

  for (final report in stats) {
    if (report.type != 'inbound-rtp') continue;

    final values = report.values;

    final kind =
        (values['kind'] ?? values['mediaType'])?.toString();
    if (kind != 'video') continue;

    final fd = values['framesDecoded'];
    final fr = values['framesReceived'];

    int? frames;

    if (fd is int) frames = fd;
    if (frames == null && fd is num) frames = fd.toInt();

    if (frames == null && fr is int) frames = fr;
    if (frames == null && fr is num) frames = fr.toInt();

    if (frames != null) {
      return frames;
    }
  }

  return null;
}

  Future<void> _connectFresh() async {
    setState(() => _status = 'connecting');

    // Reset stall detection
    _lastFrames = -1;
    _lastFrameProgressAt = DateTime.now();

    // Clear the renderer so we don't keep showing the last frozen frame.
    _renderer.srcObject = null;

    // Create new peer connection
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

        // frames are likely flowing now
        _lastFrameProgressAt = DateTime.now();
      }
    };

    // Recvonly transceiver for video
    await pc.addTransceiver(
      kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
      init: RTCRtpTransceiverInit(direction: TransceiverDirection.RecvOnly),
    );

    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    final localSdp = offer.sdp;
    if (localSdp == null) throw Exception('Offer SDP is null');

    final resp = await http
        .post(
          Uri.parse(whepUrl),
          headers: {
            'Content-Type': 'application/sdp',
            'Accept': 'application/sdp',
          },
          body: localSdp,
        )
        .timeout(const Duration(seconds: 5));

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('WHEP HTTP ${resp.statusCode}: ${resp.body}');
    }

    final answer = RTCSessionDescription(resp.body, 'answer');
    await pc.setRemoteDescription(answer);

    // connection succeeded
    _retryCount = 0;
  }

  Future<void> _reconnect({required String reason}) async {
    if (_reconnecting) return;
    _reconnecting = true;

    // ignore: avoid_print
    print('🔄 Reconnecting ($reason)');

    if (mounted) setState(() => _status = 'reconnecting');

    // Close old connection cleanly
    try {
      await _pc?.close();
    } catch (_) {}
    _pc = null;

    // Clear renderer so frozen frame disappears immediately
    _renderer.srcObject = null;
    if (mounted) setState(() {});

    // Exponential-ish backoff (capped)
    final delayMs = (500 * (1 << _retryCount)).clamp(500, 5000);
    _retryCount = (_retryCount + 1).clamp(0, 6);

    await Future.delayed(Duration(milliseconds: delayMs));

    try {
      await _connectFresh();
    } catch (e) {
      // If server is still down, we'll try again on next watchdog tick.
      // ignore: avoid_print
      print('Reconnect failed: $e');
    } finally {
      _reconnecting = false;
    }
  }

  @override
  void dispose() {
    _watchdogTimer?.cancel();
    _watchdogTimer = null;

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

          // Optional: make visible if you want to debug
          Positioned(
            left: 12,
            bottom: 12,
            child: Opacity(
              opacity: 0.0, // set to 0.8 for debugging
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