import 'package:flutter/foundation.dart';
import 'package:socket_io_client/socket_io_client.dart' as io;

import '../../models/vehicle_status.dart';
import 'hud_events.dart';

/// The app's Socket.IO link to the HUD's back end (aav_hud): the car's state, live.
class SocketService {
  io.Socket? socket;

  /// What each event does, by name (HudEvents). [handle] runs them.
  final Map<String, void Function(Map<dynamic, dynamic>)> handlers = {};

  /// Connect, and call back for each event. Leave out the callbacks a page doesn't use.
  void initSocketConnection({
    required String serverUrl,
    void Function(double speed)? onSpeedUpdate,
    void Function(double latitude, double longitude)? onGpsUpdate,
    void Function(bool detected, String message)? onStopSignAlert,
    void Function(double distance, String status)? onNavState,
    void Function(VehicleStatus status)? onVehicleStatus,
    void Function(BatteryReading battery)? onBattery,
    void Function(bool connected)? onConnection,
  }) {
    handlers
      ..clear()
      ..[HudEvents.speed] = (data) {
        onSpeedUpdate?.call((data['speed'] as num).toDouble());
      }
      ..[HudEvents.position] = (data) {
        onGpsUpdate?.call(
          (data['latitude'] as num).toDouble(),
          (data['longitude'] as num).toDouble(),
        );
      }
      ..[HudEvents.stopSign] = (data) {
        onStopSignAlert?.call(
          data['detected'] as bool? ?? false,
          data['message'] as String? ?? 'STOP',
        );
      }
      ..[HudEvents.navState] = (data) {
        onNavState?.call(
          (data['distance'] as num).toDouble(),
          data['status'] as String? ?? '',
        );
      }
      ..[HudEvents.vehicleStatus] = (data) {
        onVehicleStatus?.call(VehicleStatus.fromEvent(data));
      }
      ..[HudEvents.battery] = (data) {
        onBattery?.call(BatteryReading.fromEvent(data));
      };
    connect(serverUrl, onConnection);
  }

  /// Open the socket and pass its events to [handle]. Tests replace it.
  @protected
  void connect(String serverUrl, void Function(bool connected)? onConnection) {
    // WebSocket only. On Linux and macOS the package has no polling transport: with
    // 'polling' first it opened a WebSocket on the polling address, and never connected.
    // The back end needs simple-websocket for this (the pixi environment has it).
    final socket = io.io(
      serverUrl,
      io.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .build(),
    );
    this.socket = socket;
    socket.onConnect((_) {
      debugPrint('Connected to the HUD back end at $serverUrl');
      onConnection?.call(true);
    });
    socket.onConnectError((err) => debugPrint('Connection error: $err'));
    socket.onDisconnect((_) {
      debugPrint('Disconnected from the HUD back end');
      onConnection?.call(false);
    });
    for (final event in handlers.keys) {
      socket.on(event, (data) => handle(event, data));
    }
    socket.connect();
  }

  /// Run the callback for one event. A payload it can't read is logged and dropped.
  void handle(String event, dynamic data) {
    final handler = handlers[event];
    if (handler == null) return;
    try {
      handler(data as Map<dynamic, dynamic>);
    } catch (e) {
      debugPrint('$event: could not read $data ($e)');
    }
  }

  void dispose() {
    socket?.dispose();
  }
}
