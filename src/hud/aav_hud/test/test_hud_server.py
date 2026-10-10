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
    from sensor_msgs.msg import Image, NavSatFix
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
    assert ros.events(events.SPEED)[-1] == {'mock_speed': 1.5}
    assert ros.events(events.POSITION)[-1] == {'mock_latitude': START[0],
                                               'mock_longitude': START[1]}
    vehicle = ros.events(events.VEHICLE)[-1]
    assert (vehicle['mode'], vehicle['armed'], vehicle['gear']) == ('computer', True, 'D')


def test_the_stop_sign_is_sent_when_it_changes(ros):
    pub = ros.car.create_publisher(Bool, '/perception/stop', 10)
    wait_for(lambda: ros.events(events.STOP_SIGN), every=lambda: pub.publish(Bool(data=True)))
    for _ in range(5):
        pub.publish(Bool(data=True))
    wait_for(lambda: len(ros.events(events.STOP_SIGN)) > 1,
             every=lambda: pub.publish(Bool(data=False)))
    assert [e['mock_sign_detected'] for e in ros.events(events.STOP_SIGN)] == [True, False]


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
