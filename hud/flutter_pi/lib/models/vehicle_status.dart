/// What the back end says about the car: its vehicle_status and battery events.
library;

/// The vehicle_status event: how the car is driven, and whether it may move.
class VehicleStatus {
  const VehicleStatus({
    required this.mode,
    required this.armed,
    required this.estop,
    required this.gear,
    this.faults = const [],
  });

  /// Reads the event. Without 'armed' or 'estop' it throws: better no news than a guess.
  factory VehicleStatus.fromEvent(Map<dynamic, dynamic> data) => VehicleStatus(
    mode: data['mode'] as String? ?? 'unknown',
    armed: data['armed'] as bool,
    estop: data['estop'] as bool,
    gear: data['gear'] as String? ?? 'P',
    faults: [for (final fault in data['faults'] as List? ?? const []) '$fault'],
  );

  /// Who drives: 'manual', 'rc', 'computer' or 'unknown'.
  final String mode;

  /// Whether the spine takes drive commands.
  final bool armed;

  /// Whether the e-stop is on: the car brakes until someone clears it.
  final bool estop;

  /// 'D', 'R' or 'P'. The car has no gearbox: the back end picks the letter.
  final String gear;

  /// The faults the spine reports, by name ('cmd_timeout', 'steering_driver', ...).
  final List<String> faults;
}

/// The battery event. A value the battery monitor doesn't measure is null.
class BatteryReading {
  const BatteryReading({this.voltage, this.percentage, this.current});

  factory BatteryReading.fromEvent(Map<dynamic, dynamic> data) =>
      BatteryReading(
        voltage: (data['voltage'] as num?)?.toDouble(),
        percentage: (data['percentage'] as num?)?.toDouble(),
        current: (data['current'] as num?)?.toDouble(),
      );

  /// Volts.
  final double? voltage;

  /// The charge, 0 to 100.
  final double? percentage;

  /// Amps.
  final double? current;

  /// For the screen, e.g. '75 % · 49.5 V'.
  String get label {
    final parts = [
      if (percentage != null) '${percentage!.round()} %',
      if (voltage != null) '${voltage!.toStringAsFixed(1)} V',
    ];
    return parts.isEmpty ? 'no reading' : parts.join(' · ');
  }
}
