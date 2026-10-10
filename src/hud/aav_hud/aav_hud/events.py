"""
What the HUD's Flutter app receives over Socket.IO: one dict per event.

No ROS imports, so the tests run anywhere. Each function takes a ROS message, or
anything with the same fields, and returns the payload of one event.

The event names are the ones hud/flutter_pi listens for (socket_services.dart). Three of
them still say "mock": the 2025-26 app only ever showed mock data. They now carry real
data. Rename them only together with the app.
"""

import math

# Event names. The app reads the keys shown; it ignores any others.
SPEED = 'mock_speed_update'          # {'mock_speed': m/s}
POSITION = 'mock_gps_update'         # {'mock_latitude': deg, 'mock_longitude': deg}
STOP_SIGN = 'mock_stop_sign_alert'   # {'mock_sign_detected': bool, 'message': 'STOP'}
NAV_STATE = 'nav_state'              # {'distance': m, 'status': text} (see trip.py)
VEHICLE = 'vehicle_status'           # new: mode, armed, e-stop, gear, faults. No screen yet
STREAM_INFO = 'stream_info'          # MediaMTX addresses, sent to each new client

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


def speed_event(status):
    """Measured speed from /vehicle/status: m/s, negative in reverse."""
    return {'mock_speed': round(float(status.speed), 2)}


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
    return {'mock_latitude': lat, 'mock_longitude': lon}


def stop_sign_event(msg):
    """/perception/stop: true while the car stops for a stop sign."""
    return {'mock_sign_detected': bool(msg.data), 'message': 'STOP'}


def stream_info(host, webrtc_port, rtsp_port, path):
    """Where MediaMTX serves the video that the app's camera page plays (WebRTC)."""
    return {
        'name': path,
        'base_url': f'http://{host}:{webrtc_port}/{path}/',
        'whep_url': f'http://{host}:{webrtc_port}/{path}/whep',
        'rtsp_url': f'rtsp://{host}:{rtsp_port}/{path}',
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
