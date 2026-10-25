"""
What the HUD's Flutter app receives over Socket.IO: one dict per event.

No ROS imports, so the tests run anywhere. Each function takes a ROS message, or
anything with the same fields, and returns the payload of one event.

The app listens for the same names (hud/flutter_pi/lib/components/sockets/hud_events.dart).
test_events.py checks that the two lists match. Rename an event in both at once.
"""

import math

# Event names, and the keys the app reads. It ignores any others.
SPEED = 'speed'                  # {'speed': m/s, negative in reverse}
POSITION = 'position'            # {'latitude': deg, 'longitude': deg}
STOP_SIGN = 'stop_sign'          # {'detected': bool, 'message': 'STOP'}
NAV_STATE = 'nav_state'          # {'distance': m, 'status': text, ...} (see trip.py)
VEHICLE = 'vehicle_status'       # mode, armed, estop, gear, faults: see vehicle_event()
BATTERY = 'battery'              # {'voltage': V, 'percentage': 0-100, 'current': A}

EVENTS = (SPEED, POSITION, STOP_SIGN, NAV_STATE, VEHICLE, BATTERY)

# The constants of aav_interfaces/msg/VehicleStatus (test_events checks them).
MODE_COMPUTER = 2
MODE_NAMES = {0: 'manual', 1: 'rc', MODE_COMPUTER: 'computer'}
FAULT_NAMES = {
    1: 'cmd_timeout',
    2: 'bad_checksum',
    4: 'bad_counter',
    8: 'steering_driver',
    16: 'brake_driver',
    32: 'throttle_dac',
    64: 'wheel_encoder',
    128: 'can_bus',
    256: 'rc_signal_lost',
    512: 'overspeed',
}

NO_FIX = -1      # sensor_msgs/NavSatStatus.STATUS_NO_FIX
MOVING = 0.05    # m/s: slower than this counts as standing still, for the gear letter


def _number(value, digits):
    """Round a reading for JSON: None when it's NaN or infinite (not measured)."""
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def speed_event(status):
    """Measured speed from /vehicle/status: m/s, negative in reverse."""
    return {'speed': round(float(status.speed), 2)}


def gear(mode, armed, estop, speed):
    """
    Pick a gear letter for the screen: 'D', 'R' or 'P'. The car has no gearbox.

    Moving: the direction. Standing still: 'D' only when the computer drives and may
    move (armed, no e-stop), otherwise 'P'.
    """
    if speed < -MOVING:
        return 'R'
    if speed > MOVING:
        return 'D'
    if mode == MODE_COMPUTER and armed and not estop:
        return 'D'
    return 'P'


def fault_names(bits):
    """Name the fault bits that are set; unknown bits as one hex number."""
    names = [name for bit, name in sorted(FAULT_NAMES.items()) if bits & bit]
    unknown = bits & ~sum(FAULT_NAMES)
    if unknown:
        names.append(f'0x{unknown:04x}')
    return names


def vehicle_event(status):
    """Everything in /vehicle/status, in plain words."""
    return {
        'mode': MODE_NAMES.get(status.mode, 'unknown'),
        'armed': bool(status.armed),
        'estop': bool(status.estop_active),
        'gear': gear(status.mode, status.armed, status.estop_active, status.speed),
        'speed': round(float(status.speed), 2),
        'steering_angle': round(float(status.steering_angle), 3),
        'throttle': round(float(status.throttle), 2),
        'brake': round(float(status.brake), 2),
        'faults': fault_names(status.faults),
    }


def fix_position(fix):
    """
    (lat, lon) in degrees from a NavSatFix, or None when it has no position.

    No fix, NaN or off the globe: the map would jump to (0, 0) or fail. An unknown
    status (-2, Jazzy's default) still counts, as it does for navsat_transform.
    """
    if fix.status.status == NO_FIX:
        return None
    lat, lon = float(fix.latitude), float(fix.longitude)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if abs(lat) > 90.0 or abs(lon) > 180.0:
        return None
    return lat, lon


def position_event(lat, lon):
    """Put the car on the map."""
    return {'latitude': lat, 'longitude': lon}


def stop_sign_event(msg):
    """/perception/stop_sign: true while the car stops for a stop sign."""
    return {'detected': bool(msg.data), 'message': 'STOP'}


def battery_event(msg):
    """
    /vehicle/battery (sensor_msgs/BatteryState): volts, percent and amps.

    BatteryState gives the charge from 0 to 1; the app shows percent. A reading the
    battery monitor doesn't measure is NaN in the message, None here: JSON has no NaN.
    """
    percentage = _number(msg.percentage, 3)
    return {
        'voltage': _number(msg.voltage, 2),
        'percentage': None if percentage is None else round(100.0 * percentage, 1),
        'current': _number(msg.current, 2),
    }


class Throttle:
    """At most `rate` events a second for each key. A rate of 0 or less: no limit."""

    def __init__(self, rate):
        self.period = 1.0 / rate if rate > 0 else 0.0
        self._last = {}

    def ready(self, key, now):
        """Say whether an event for `key` may go out at time `now` (seconds)."""
        last = self._last.get(key)
        if last is not None and now - last < self.period:
            return False
        self._last[key] = now
        return True
