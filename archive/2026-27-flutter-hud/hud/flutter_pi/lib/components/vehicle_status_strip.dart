import 'package:flutter/material.dart';

import '../models/vehicle_status.dart';

/// A strip across the top of the home screen: the e-stop, armed, mode, gear, battery
/// and faults, as the back end's vehicle_status and battery events say. It takes a
/// second line when one isn't enough.
class VehicleStatusStrip extends StatelessWidget {
  const VehicleStatusStrip({
    super.key,
    required this.connected,
    this.status,
    this.battery,
  });

  /// Whether the app hears the back end. Without it, nothing else is shown: old values
  /// could say the car is stopped when it isn't.
  final bool connected;
  final VehicleStatus? status;
  final BatteryReading? battery;

  static final _grey = Colors.grey.shade700;
  static final _purple = Colors.deepPurple.shade400;

  @override
  Widget build(BuildContext context) {
    final s = status;
    final chips = <Widget>[
      if (!connected)
        _chip('No back end', _grey)
      else if (s == null)
        _chip('Waiting for the car', _grey)
      else ...[
        s.estop
            ? _chip('E-STOP ON', Colors.red.shade700)
            : _chip('E-stop off', Colors.green.shade800),
        s.armed
            ? _chip('Armed', Colors.orange.shade800)
            : _chip('Not armed', _grey),
        _chip('Mode: ${s.mode}', _purple),
        _chip('Gear ${s.gear}', _purple),
      ],
      if (connected)
        _chip(
          'Battery: ${battery?.label ?? 'no reading'}',
          Colors.blueGrey.shade600,
        ),
      if (connected && s != null)
        s.faults.isEmpty
            ? _chip('No faults', Colors.green.shade800)
            : _chip('Faults: ${s.faults.join(', ')}', Colors.amber.shade900),
    ];
    return Container(
      width: double.infinity,
      color: Colors.black,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      child: Wrap(spacing: 6, runSpacing: 6, children: chips),
    );
  }

  static Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 15,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
