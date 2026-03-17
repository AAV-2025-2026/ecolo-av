import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class CameraPage extends StatefulWidget {
  const CameraPage({super.key});

  @override
  State<CameraPage> createState() => _CameraPageState();
}

class _CameraPageState extends State<CameraPage> {
  static const String whepUrl =
      'http://192.168.1.117:8889/cam1/whep'; // ✅ correct IP

  static const double _debugOpacity = 0.0; // set 0.8 to debug

  RTCPeerConnection? _pc;
  final RTCVideoRenderer _renderer = RTCVideoRenderer();

  Timer? _watchdogTimer;
  bool _reconnecting = false;

  static const Duration _watchdogTick = Duration(seconds: 2);
  static const Duration _stallThreshold = Duration(seconds: 6);

  int _lastFrames = -1;
  DateTime _lastFrameProgressAt = DateTime.now();

  int _retryCount = 0;

  String _status = 'idle';
  String _lastError = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await _renderer.initialize();
    await _safeConnect();
    _startWatchdog();
  }

  Future<void> _safeConnect() async {
    try {
      await _connect();
    } catch (e) {
      setState(() {
        _status = 'connect_failed';
        _lastError = e.toString();
      });
      _reconnect(reason: 'initial failure');
    }
  }

  // ----------------------------------------------------
  // CONNECT
  // ----------------------------------------------------

  Future<void> _connect() async {
    if (!mounted) return;

    setState(() {
      _status = 'connecting';
      _lastError = '';
    });

    _renderer.srcObject = null;

    try {
      await _pc?.close();
    } catch (_) {}
    _pc = null;

    final config = <String, dynamic>{
      "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
      ],
      "sdpSemantics": "unified-plan",
    };

    final pc = await createPeerConnection(config);
    _pc = pc;

    pc.onConnectionState = (state) {
      if (!mounted) return;
      setState(() => _status = state.toString());

      if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
          state ==
              RTCPeerConnectionState.RTCPeerConnectionStateDisconnected) {
        _reconnect(reason: 'bad connection state');
      }
    };

    pc.onTrack = (event) {
      if (event.track.kind == 'video' && event.streams.isNotEmpty) {
        _renderer.srcObject = event.streams[0];
        if (!mounted) return;
        setState(() => _status = 'playing');
        _lastFrameProgressAt = DateTime.now();
      }
    };

    await pc.addTransceiver(
      kind: RTCRtpMediaType.RTCRtpMediaTypeVideo,
      init: RTCRtpTransceiverInit(
        direction: TransceiverDirection.RecvOnly,
      ),
    );

    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    await _waitForIce(pc);

    // 🔴 IMPORTANT: Compatible way for older flutter_webrtc
    final localDesc = await pc.getLocalDescription();
    final sdpToSend = localDesc?.sdp ?? offer.sdp;

    if (sdpToSend == null || sdpToSend.isEmpty) {
      throw Exception('SDP empty');
    }

    final resp = await http
        .post(
          Uri.parse(whepUrl),
          headers: const {
            'Content-Type': 'application/sdp',
            'Accept': 'application/sdp',
          },
          body: sdpToSend,
        )
        .timeout(const Duration(seconds: 8));

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw HttpException(
          'WHEP HTTP ${resp.statusCode}: ${resp.body}');
    }

    final answer = RTCSessionDescription(resp.body, 'answer');
    await pc.setRemoteDescription(answer);

    _retryCount = 0;

    if (!mounted) return;
    setState(() => _status = 'connected');
  }

  Future<void> _waitForIce(RTCPeerConnection pc) async {
    final start = DateTime.now();
    while (pc.iceGatheringState !=
        RTCIceGatheringState.RTCIceGatheringStateComplete) {
      if (DateTime.now().difference(start) >
          const Duration(seconds: 3)) {
        return;
      }
      await Future.delayed(const Duration(milliseconds: 50));
    }
  }

  // ----------------------------------------------------
  // RECONNECT
  // ----------------------------------------------------

  Future<void> _reconnect({required String reason}) async {
    if (_reconnecting) return;
    _reconnecting = true;

    setState(() {
      _status = 'reconnecting';
      _lastError = reason;
    });

    try {
      await _pc?.close();
    } catch (_) {}
    _pc = null;

    _renderer.srcObject = null;

    final delay =
        (500 * (1 << _retryCount)).clamp(500, 5000);
    _retryCount = (_retryCount + 1).clamp(0, 6);

    await Future.delayed(Duration(milliseconds: delay));

    try {
      await _connect();
    } catch (e) {
      setState(() => _lastError = e.toString());
    } finally {
      _reconnecting = false;
    }
  }

  // ----------------------------------------------------
  // WATCHDOG
  // ----------------------------------------------------

  void _startWatchdog() {
    _watchdogTimer?.cancel();
    _watchdogTimer =
        Timer.periodic(_watchdogTick, (_) async {
      if (!mounted || _pc == null || _reconnecting) return;

      try {
        final frames =
            await _getInboundFrames(_pc!);

        if (frames != null) {
          if (_lastFrames == -1) {
            _lastFrames = frames;
            _lastFrameProgressAt = DateTime.now();
            return;
          }

          if (frames > _lastFrames) {
            _lastFrames = frames;
            _lastFrameProgressAt = DateTime.now();
            return;
          }

          final stalled =
              DateTime.now().difference(_lastFrameProgressAt);

          if (stalled >= _stallThreshold) {
            await _reconnect(
                reason: 'video stalled');
          }
        }
      } catch (_) {}
    });
  }

  Future<int?> _getInboundFrames(
      RTCPeerConnection pc) async {
    final stats = await pc.getStats();

    for (final report in stats) {
      if (report.type != 'inbound-rtp') continue;

      final values = report.values;
      final kind =
          (values['kind'] ?? values['mediaType'])
              ?.toString();
      if (kind != 'video') continue;

      final fd = values['framesDecoded'];
      final fr = values['framesReceived'];

      if (fd is int) return fd;
      if (fr is int) return fr;
    }

    return null;
  }

  // ----------------------------------------------------
  // CLEANUP
  // ----------------------------------------------------

  @override
  void dispose() {
    _watchdogTimer?.cancel();
    _pc?.close();
    _renderer.dispose();
    super.dispose();
  }

  // ----------------------------------------------------
  // UI
  // ----------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final hasVideo =
        _renderer.srcObject != null;

    return Scaffold(
      backgroundColor: Colors.grey.shade100,
      appBar: AppBar(
        title: const Text('Camera'),
        backgroundColor:
            Colors.deepPurple.shade700,
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () =>
              Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                _reconnect(reason: 'manual'),
          ),
        ],
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: hasVideo
                ? RTCVideoView(
                    _renderer,
                    objectFit:
                        RTCVideoViewObjectFit
                            .RTCVideoViewObjectFitContain,
                  )
                : const SizedBox.expand(),
          ),
          Positioned(
            left: 12,
            bottom: 12,
            child: Opacity(
              opacity: _debugOpacity,
              child: Container(
                padding:
                    const EdgeInsets.all(8),
                color: Colors.black,
                child: Text(
                  'Status: $_status\nError: $_lastError',
                  style: const TextStyle(
                      color: Colors.white),
                ),
              ),
            ),
          )
        ],
      ),
    );
  }
}
