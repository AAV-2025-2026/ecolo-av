import 'package:flutter_pi/components/sockets/hud_events.dart';
import 'package:flutter_pi/models/vehicle_status.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  late FakeSocketService socket;
  final got = <String, Object?>{};

  setUp(() {
    got.clear();
    socket =
        FakeSocketService()..initSocketConnection(
          serverUrl: 'http://hud.test',
          onSpeedUpdate: (speed) => got['speed'] = speed,
          onGpsUpdate: (lat, lon) => got['position'] = [lat, lon],
          onStopSignAlert:
              (detected, message) => got['stop'] = [detected, message],
          onNavState: (distance, status) => got['nav'] = [distance, status],
          onVehicleStatus: (status) => got['vehicle'] = status,
          onBattery: (battery) => got['battery'] = battery,
        );
  });

  test('it listens for the back end\'s six events, by their real names', () {
    expect(socket.handlers.keys.toSet(), {
      'speed',
      'position',
      'stop_sign',
      'nav_state',
      'vehicle_status',
      'battery',
    });
    expect(socket.serverUrl, 'http://hud.test');
  });

  test('the old mock_* names do nothing', () {
    socket.handle('mock_speed_update', {'mock_speed': 3.0});
    socket.handle('mock_gps_update', {
      'mock_latitude': 45.0,
      'mock_longitude': -75.0,
    });
    expect(got, isEmpty);
  });

  test('each event reaches its callback', () {
    socket.handle(HudEvents.speed, {'speed': -0.5});
    socket.handle(HudEvents.position, {
      'latitude': 45.386,
      'longitude': -75.696,
    });
    socket.handle(HudEvents.stopSign, {'detected': true, 'message': 'STOP'});
    socket.handle(HudEvents.navState, {'distance': 12, 'status': 'navigating'});
    expect(got['speed'], -0.5);
    expect(got['position'], [45.386, -75.696]);
    expect(got['stop'], [true, 'STOP']);
    expect(got['nav'], [12.0, 'navigating']);
  });

  test('vehicle_status, as events.py sends it', () {
    socket.handle(HudEvents.vehicleStatus, {
      'mode': 'computer',
      'armed': true,
      'estop': false,
      'gear': 'D',
      'speed': 1.5,
      'steering_angle': 0.1,
      'throttle': 0.3,
      'brake': 0.0,
      'faults': ['cmd_timeout', 'steering_driver'],
    });
    final status = got['vehicle'] as VehicleStatus;
    expect(status.mode, 'computer');
    expect(status.armed, isTrue);
    expect(status.estop, isFalse);
    expect(status.gear, 'D');
    expect(status.faults, ['cmd_timeout', 'steering_driver']);
  });

  test('the battery, with what the monitor does not measure as null', () {
    socket.handle(HudEvents.battery, {
      'voltage': 49.5,
      'percentage': 75.0,
      'current': null,
    });
    final battery = got['battery'] as BatteryReading;
    expect(battery.voltage, 49.5);
    expect(battery.current, isNull);
    expect(battery.label, '75 % · 49.5 V');
    expect(const BatteryReading().label, 'no reading');
  });

  test('a payload it cannot read is dropped, not guessed', () {
    // No 'armed', no 'estop': nothing is better than a guess.
    socket.handle(HudEvents.vehicleStatus, {'mode': 'computer'});
    socket.handle(HudEvents.speed, 'not a map');
    socket.handle(HudEvents.position, {'latitude': 'north'});
    expect(got, isEmpty);
  });
}
