"""
The node in one process with a fake car and a fake Nav2: topics in, events out.

Needs ROS sourced (rclpy, aav_interfaces, nav2_msgs): `colcon test` runs it. It uses
absolute topic names, so give the run its own ROS_DOMAIN_ID on a shared machine.
"""

import math
import threading
import time

import pytest

# Not pytest.importorskip: ROS's launch_testing pytest plugin turns a module-level skip
# into a skip of every test in the folder, and it also overrides collect_ignore.
try:
    from aav_hud import events
    from aav_hud.hud_server import HudServer
    from aav_interfaces.msg import VehicleStatus
    from nav2_msgs.action import FollowGPSWaypoints
    import rclpy
    from rclpy.action import ActionServer, CancelResponse
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.parameter import Parameter
    from rclpy.qos import qos_profile_system_default, ReliabilityPolicy
    from sensor_msgs.msg import BatteryState, Image, NavSatFix
    from std_msgs.msg import Bool
except ImportError:
    HudServer = None

pytestmark = pytest.mark.skipif(HudServer is None, reason='needs ROS sourced: colcon test')

START = (45.3860, -75.6960)
EAST_50 = (45.3860, -75.6960 + math.degrees(50 / (6371008.8 * math.cos(math.radians(45.386)))))
ROUTE = [{'lat': START[0], 'lon': START[1]}, {'lat': EAST_50[0], 'lon': EAST_50[1]}]


class Ros:
    """The HUD node and a fake car node, spun by one executor in a thread."""

    def __init__(self, **params):
        # Without its web server: Flask's and Flask-SocketIO's test clients instead.
        self.hud = HudServer(parameter_overrides=[Parameter(k, value=v)
                                                  for k, v in params.items()])
        self.car = rclpy.create_node('fake_car')
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.hud)
        self.executor.add_node(self.car)
        self.thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.thread.start()
        self.http = self.hud.web.app.test_client()
        self.socket = self.hud.web.socketio.test_client(self.hud.web.app)
        self.received = []

    def events(self, name):
        """Payloads of every `name` event the Socket.IO client has received."""
        self.received += self.socket.get_received()
        return [m['args'][0] for m in self.received if m['name'] == name]

    def close(self):
        self.executor.shutdown()
        self.thread.join(timeout=5)
        self.hud.destroy_node()
        self.car.destroy_node()


@pytest.fixture
def ros(request):
    rclpy.init()
    try:
        r = Ros(**getattr(request, 'param', {}))
        yield r
        r.close()
    finally:
        rclpy.try_shutdown()


def wait_for(check, timeout=10.0, every=None):
    """Poll until check() is truthy; call every() first each time (a publish)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if every:
            every()
        value = check()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('timed out')


def fake_nav2(ros, finish='succeed'):
    """Start a fake Nav2: it drives every waypoint, or waits to be canceled."""
    goals = []

    def execute(handle):
        goals.append(handle.request)
        for i in range(len(handle.request.gps_poses)):
            handle.publish_feedback(FollowGPSWaypoints.Feedback(current_waypoint=i))
            time.sleep(0.1)
        while finish == 'wait' and not handle.is_cancel_requested:
            time.sleep(0.05)
        if handle.is_cancel_requested:
            handle.canceled()
        else:
            handle.succeed()
        return FollowGPSWaypoints.Result()

    server = ActionServer(ros.car, FollowGPSWaypoints, '/follow_gps_waypoints', execute,
                          cancel_callback=lambda _: CancelResponse.ACCEPT,
                          callback_group=ReentrantCallbackGroup())
    return server, goals


def test_status_and_position_become_the_apps_events(ros):
    status_pub = ros.car.create_publisher(VehicleStatus, '/vehicle/status', 10)
    fix_pub = ros.car.create_publisher(NavSatFix, '/gps/filtered', 10)
    status = VehicleStatus(mode=VehicleStatus.MODE_COMPUTER, armed=True, speed=1.5)
    fix = NavSatFix(latitude=START[0], longitude=START[1])

    def publish():
        status_pub.publish(status)
        fix_pub.publish(fix)

    wait_for(lambda: ros.events(events.SPEED) and ros.events(events.POSITION), every=publish)
    assert ros.events(events.SPEED)[-1] == {'speed': 1.5}
    assert ros.events(events.POSITION)[-1] == {'latitude': START[0], 'longitude': START[1]}
    vehicle = ros.events(events.VEHICLE)[-1]
    assert (vehicle['mode'], vehicle['armed'], vehicle['gear']) == ('computer', True, 'D')


def test_the_stop_sign_is_sent_when_it_changes(ros):
    pub = ros.car.create_publisher(Bool, '/perception/stop', 10)
    wait_for(lambda: ros.events(events.STOP_SIGN), every=lambda: pub.publish(Bool(data=True)))
    for _ in range(5):
        pub.publish(Bool(data=True))
    wait_for(lambda: len(ros.events(events.STOP_SIGN)) > 1,
             every=lambda: pub.publish(Bool(data=False)))
    assert [e['detected'] for e in ros.events(events.STOP_SIGN)] == [True, False]


def test_the_battery_becomes_the_apps_event(ros):
    pub = ros.car.create_publisher(BatteryState, '/battery_status', 10)
    msg = BatteryState(voltage=49.5, percentage=0.75, current=math.nan)
    wait_for(lambda: ros.events(events.BATTERY), every=lambda: pub.publish(msg))
    assert ros.events(events.BATTERY)[-1] == {'voltage': 49.5, 'percentage': 75.0,
                                              'current': None}


def listen_for_estop(ros, qos=10):
    """Subscribe to /estop as the car does; return the list the values arrive in."""
    values = []
    ros.car.create_subscription(Bool, '/estop', lambda m: values.append(m.data), qos)
    return values


def a_backend_listens(ros):
    """Subscribe to /estop as spine_bridge does, and wait until the HUD sees it."""
    values = listen_for_estop(ros)
    wait_for(lambda: ros.hud.estop_pub.get_subscription_count() == 1)
    return values


def test_the_estop_button_reaches_the_backends_and_twist_mux(ros):
    assert ros.hud.estop_pub.qos_profile.reliability == ReliabilityPolicy.RELIABLE
    backends = listen_for_estop(ros, 10)    # spine_bridge, legacy_uart_bridge: depth 10
    mux = listen_for_estop(ros, qos_profile_system_default)    # twist_mux's locks
    wait_for(lambda: ros.hud.estop_pub.get_subscription_count() == 2)
    reply = ros.http.post('/estop')
    assert reply.status_code == 200
    wait_for(lambda: len(backends) == 5 and len(mux) == 5)
    time.sleep(0.5)     # and no more after the five
    assert backends == [True] * 5
    assert mux == [True] * 5


def test_the_estop_also_cancels_the_route(ros):
    a_backend_listens(ros)
    server, goals = fake_nav2(ros, finish='wait')
    assert ros.hud.nav.wait_for_server(timeout_sec=5.0)
    assert ros.http.post('/receive', json=ROUTE).status_code == 200
    wait_for(lambda: ros.hud.web.latest()[events.NAV_STATE]['status'] == 'navigating')
    assert ros.http.post('/estop').status_code == 200
    wait_for(lambda: ros.hud.web.latest()[events.NAV_STATE]['status'] == 'canceled')
    server.destroy()


def test_the_estop_without_a_route(ros):
    a_backend_listens(ros)
    assert ros.http.post('/estop').status_code == 200
    assert events.NAV_STATE not in ros.hud.web.latest()     # nothing to cancel


def test_an_estop_that_nothing_hears_is_an_error(ros):
    # No backend, no twist_mux: "sent" would be a lie, so the app must say it failed.
    reply = ros.http.post('/estop')
    assert reply.status_code == 503
    assert 'nothing on the car subscribes to /estop' in reply.get_json()['message']


def test_a_locked_route_drives_through_nav2(ros):
    server, goals = fake_nav2(ros)
    assert ros.hud.nav.wait_for_server(timeout_sec=5.0)
    reply = ros.http.post('/receive', json=ROUTE)
    assert reply.status_code == 200, reply.get_json()
    wait_for(lambda: ros.hud.web.latest().get(events.NAV_STATE, {}).get('status')
             == 'goal_reached')
    [goal] = goals
    [pose] = goal.gps_poses     # the start is dropped: the car is already there
    assert (pose.position.latitude, pose.position.longitude) == pytest.approx(EAST_50)
    assert pose.position.altitude == 0.0
    assert (pose.orientation.z, pose.orientation.w) == pytest.approx((0.0, 1.0))  # east
    statuses = [e['status'] for e in ros.events(events.NAV_STATE)]
    assert statuses[0] == 'sending_goal'
    assert 'navigating' in statuses
    assert statuses[-1] == 'goal_reached'
    server.destroy()


def test_cancel_stops_the_goal(ros):
    server, goals = fake_nav2(ros, finish='wait')
    assert ros.hud.nav.wait_for_server(timeout_sec=5.0)
    assert ros.http.post('/receive', json=ROUTE).status_code == 200
    wait_for(lambda: ros.hud.web.latest()[events.NAV_STATE]['status'] == 'navigating')
    assert ros.http.post('/cancel').status_code == 200
    wait_for(lambda: ros.hud.web.latest()[events.NAV_STATE]['status'] == 'canceled')
    assert ros.http.post('/cancel').status_code == 409     # nothing left to cancel
    server.destroy()


def test_without_nav2_the_route_is_refused(ros):
    reply = ros.http.post('/receive', json=ROUTE)
    assert reply.status_code == 503
    assert ros.hud.web.latest()[events.NAV_STATE]['status'] == 'nav2_not_running'


@pytest.mark.parametrize('ros', [{'camera_idle_timeout': 1.0}], indirect=True)
def test_the_camera_is_received_only_while_someone_watches(ros):
    pub = ros.car.create_publisher(Image, '/camera/image_raw', 1)
    assert pub.get_subscription_count() == 0
    assert ros.http.get('/camera/latest.png').status_code == 503
    picture = Image(width=2, height=1, encoding='bgr8', step=6, data=[255, 0, 0, 0, 0, 255])

    def fetch():
        pub.publish(picture)
        reply = ros.http.get('/camera/latest.png')
        return reply if reply.status_code == 200 else None

    reply = wait_for(fetch)
    assert reply.mimetype == 'image/png'
    assert reply.data.startswith(b'\x89PNG')
    assert pub.get_subscription_count() == 1
    wait_for(lambda: pub.get_subscription_count() == 0)     # nobody watches any more


@pytest.mark.parametrize('ros', [{'camera_stale_after': 0.5}], indirect=True)
def test_an_old_picture_is_not_served(ros):
    pub = ros.car.create_publisher(Image, '/camera/image_raw', 1)
    picture = Image(width=1, height=1, encoding='mono8', step=1, data=[128])

    def fetch():
        pub.publish(picture)
        return ros.http.get('/camera/latest.png').status_code == 200

    wait_for(fetch)
    time.sleep(1.0)     # the camera stops
    reply = ros.http.get('/camera/latest.png')
    assert reply.status_code == 503
    assert b'is the camera running' in reply.data
