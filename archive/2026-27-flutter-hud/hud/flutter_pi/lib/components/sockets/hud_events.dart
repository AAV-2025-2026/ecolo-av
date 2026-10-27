/// The Socket.IO events the HUD's back end sends (aav_hud's events.py).
///
/// The back end's tests (test_events.py) read this file and check that the names
/// match its own. Rename an event in both at once.
abstract final class HudEvents {
  /// The measured speed: {'speed': m/s, negative in reverse}.
  static const speed = 'speed';

  /// The car on the map: {'latitude': degrees, 'longitude': degrees}.
  static const position = 'position';

  /// Stopping for a stop sign: {'detected': bool, 'message': 'STOP'}.
  static const stopSign = 'stop_sign';

  /// The locked route's progress: {'distance': m, 'status': text, ...}.
  static const navState = 'nav_state';

  /// Mode, armed, e-stop, gear and faults, from /vehicle/status.
  static const vehicleStatus = 'vehicle_status';

  /// The battery: {'voltage': V, 'percentage': 0-100, 'current': A}, null if unmeasured.
  static const battery = 'battery';
}
