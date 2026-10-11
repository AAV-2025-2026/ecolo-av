"""
hud_server: the back end of the HUD, the car's touchscreen app (hud/flutter_pi).

One process: this ROS node, and a web server (Flask and Socket.IO, web.py) for the app.
It turns the car's topics into the events the app shows, the route the app locks into a
Nav2 goal, and the app's e-stop button into /estop true.

Subscribes  /vehicle/status        aav_interfaces/VehicleStatus  speed, mode, e-stop, faults
            /gps/filtered          sensor_msgs/NavSatFix         the car on the map
            /perception/stop       std_msgs/Bool                 stopping for a stop sign
            /battery_status        sensor_msgs/BatteryState      volts, charge, amps
            /camera/image_raw      sensor_msgs/Image             only while someone watches
Publishes   /estop                 std_msgs/Bool                 only true: the app's e-stop
Calls       /follow_gps_waypoints  nav2_msgs/action/FollowGPSWaypoints  the locked route
Serves      HTTP and Socket.IO on 127.0.0.1:5000 (parameters host, port)

The e-stop: POST /estop publishes /estop true at once, then every 0.1 s, five times in
all (as `pixi run estop` does), so one lost message can't keep the car going. It also
cancels the HUD's route, so clearing the e-stop doesn't restart the trip. If nothing
subscribes to /estop, the request fails (503), so the app never says "sent" to nobody.
The HUD never publishes false: clearing the e-stop stays a person's deliberate act, from
a laptop (`pixi run estop-clear`, Foxglove), never a tap on this touchscreen.

The conversions live in events.py (messages to events), route.py (the route to GPS
waypoints), trip.py (the action's progress to nav_state) and png.py (camera pictures).

Camera pictures are big (about 1 MB each, several a second), and each one goes to every
subscriber, across the network too. So the node only subscribes while someone fetches
/camera/latest.png or /camera/stream, and stops camera_idle_timeout seconds after.

Try it without a car:
  ros2 launch aav_hud hud.launch.py
  ros2 topic pub -r 10 /vehicle/status aav_interfaces/msg/VehicleStatus "{speed: 1.5}"
  curl http://127.0.0.1:5000/
"""

from functools import partial
import signal
import threading
import time

from aav_hud import events, png
from aav_hud.route import quaternion
from aav_hud.trip import NO_NAV2, Trip
from aav_hud.web import HudWeb
from aav_interfaces.msg import VehicleStatus
from geographic_msgs.msg import GeoPose
from nav2_msgs.action import FollowGPSWaypoints
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, qos_profile_sensor_data, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Image, NavSatFix
from std_msgs.msg import Bool

# Best effort takes both kinds of publisher: ublox publishes /gps/fix best effort,
# the others are reliable. These messages are small, so losing one costs nothing.
SMALL = qos_profile_sensor_data
# Pictures: reliable, as best effort loses most big messages over UDP (aav_yolo measured
# it on a Mac), and only the newest one.
PICTURES = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                      reliability=ReliabilityPolicy.RELIABLE)
# /estop: what its subscribers use. spine_bridge and legacy_uart_bridge subscribe reliable,
# volatile, depth 10 (ROS's default); twist_mux 4.5.0 with SystemDefaultsQoS, which takes
# a reliable publisher too. A best-effort publisher would reach twist_mux only.
ESTOP = QoSProfile(depth=10, history=HistoryPolicy.KEEP_LAST,
                   reliability=ReliabilityPolicy.RELIABLE)
ESTOP_REPEATS = 5       # messages for one press: the first at once, then one every
ESTOP_PERIOD = 0.1      # s, for half a second in all


def geo_pose(waypoint):
    """Make a GeoPose for Nav2 from a route.Waypoint."""
    pose = GeoPose()
    pose.position.latitude = waypoint.lat
    pose.position.longitude = waypoint.lon
    # Not NaN ("unknown"): navsat_transform's fromLL transforms the altitude with the
    # position, and a NaN would spoil the whole map point. navsat.yaml zeroes it anyway.
    pose.position.altitude = 0.0
    q = pose.orientation
    q.x, q.y, q.z, q.w = quaternion(waypoint.yaw)
    return pose


class HudServer(Node):

    def __init__(self, **kwargs):
        super().__init__('hud_server', **kwargs)
        param = self.declare_parameter
        self.host = param('host', '127.0.0.1').value
        self.port = param('port', 5000).value
        self.throttle = events.Throttle(param('max_event_rate', 10.0).value)
        self.web = HudWeb(self, param('route_tolerance', 1.0).value,
                          param('waypoint_spacing', 5.0).value, param('camera_fps', 5.0).value)
        self.camera_idle = param('camera_idle_timeout', 5.0).value
        self.camera_stale = param('camera_stale_after', 2.0).value

        # The web server's threads call follow() and cancel(); the executor the rest.
        self.lock = threading.Lock()
        self.position = None    # (lat, lon) of the car, once known
        self.stop_sign = None
        self.trip = Trip()
        self.trip_id = 0        # which goal is the newest; older answers are ignored
        self.goal = None        # the newest goal's handle, once Nav2 took it
        self.web_failed = False
        self.camera = None              # the subscription, while someone watches
        self.camera_wanted = None       # when the web side last asked for a picture
        self.picture = None             # the newest Image
        self.picture_time = 0.0         # when it came (time.monotonic)
        self.picture_png = (None, None)     # (Image, its PNG), so each is encoded once
        self.estop_left = 0     # /estop true messages still to send for the last press

        self.create_subscription(VehicleStatus, '/vehicle/status', self.on_status, SMALL)
        self.create_subscription(NavSatFix, '/gps/filtered', self.on_fix, SMALL)
        self.create_subscription(Bool, '/perception/stop', self.on_stop, SMALL)
        self.create_subscription(BatteryState, '/battery_status', self.on_battery, SMALL)
        # Made now, not when the button is pressed: by then discovery has matched it with
        # the subscribers, so the first message isn't lost.
        self.estop_pub = self.create_publisher(Bool, '/estop', ESTOP)
        self.nav = ActionClient(self, FollowGPSWaypoints, '/follow_gps_waypoints')
        self.create_timer(0.5, self.check_camera)
        self.create_timer(ESTOP_PERIOD, self.repeat_estop)

    def start_web(self):
        """Start the web server in a thread. If it fails, the node shuts down."""
        self.get_logger().info(f'HUD back end on http://{self.host}:{self.port}')
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        try:
            self.web.run(self.host, self.port)
        except (OSError, SystemExit) as e:
            # Werkzeug calls sys.exit(1) when the port is taken, and a thread swallows
            # that: without this the node would run on with no web server.
            self.get_logger().fatal(f'no web server ({e!r}). Is port {self.port} taken? '
                                    'On a Mac, AirPlay Receiver uses 5000 on 0.0.0.0.')
        self.web_failed = True
        self.context.try_shutdown()

    # --- car -> app ---

    def on_status(self, msg):
        if self.throttle.ready('status', time.monotonic()):
            self.web.send(events.SPEED, events.speed_event(msg))
            self.web.send(events.VEHICLE, events.vehicle_event(msg))

    def on_fix(self, msg):
        position = events.fix_position(msg)
        if position is None:
            return
        due = self.throttle.ready('position', time.monotonic())
        if due:
            self.web.send(events.POSITION, events.position_event(*position))
        with self.lock:
            self.position = position
            if due and self.trip.active:
                self._send_nav_state()      # the distance left changed

    def on_stop(self, msg):
        # Only changes: the stop-sign watcher publishes it 10 times a second.
        if bool(msg.data) != self.stop_sign:
            self.stop_sign = bool(msg.data)
            self.web.send(events.STOP_SIGN, events.stop_sign_event(msg))

    def on_battery(self, msg):
        if self.throttle.ready('battery', time.monotonic()):
            self.web.send(events.BATTERY, events.battery_event(msg))

    def on_image(self, msg):
        with self.lock:
            self.picture = msg
            self.picture_time = time.monotonic()

    def check_camera(self):
        """Subscribe to the camera while someone watches; stop when nobody does."""
        with self.lock:
            wanted = (self.camera_wanted is not None
                      and time.monotonic() - self.camera_wanted < self.camera_idle)
        if wanted and self.camera is None:
            self.camera = self.create_subscription(Image, '/camera/image_raw', self.on_image,
                                                   PICTURES)
            self.get_logger().info('someone watches the camera: subscribed')
        elif not wanted and self.camera is not None:
            self.destroy_subscription(self.camera)
            self.camera = None
            with self.lock:
                self.picture, self.picture_png = None, (None, None)
            self.get_logger().info('nobody watches the camera: unsubscribed')

    def camera_png(self):
        """
        Return the newest picture as PNG (web threads). Raise ValueError.

        None before the first picture, or when the newest is older than
        camera_stale_after: the camera stopped, and an old picture mustn't pass for a live
        one.
        """
        with self.lock:
            now = time.monotonic()
            self.camera_wanted = now
            picture, (encoded_for, encoded) = self.picture, self.picture_png
            fresh = picture is not None and now - self.picture_time < self.camera_stale
        if not fresh:
            return None
        if picture is encoded_for:
            return encoded
        encoded = png.encode(picture.width, picture.height, picture.encoding, picture.step,
                             picture.data)
        with self.lock:
            self.picture_png = (picture, encoded)
        return encoded

    def _send_nav_state(self):
        # Call with self.lock held: the executor and the web threads both send this
        # event, and the lock keeps the events in the order the trip changed.
        self.web.send(events.NAV_STATE, self.trip.event(self.position))

    # --- the app's e-stop button (web threads), and its repeats (executor) ---

    def estop(self):
        """
        Set the e-stop: /estop true now, then repeated. Never false.

        Return None when something subscribes to /estop, or why the press can't work:
        the app then tells the driver to use the car's red e-stop button.
        """
        # The lock also keeps this thread and the executor's from publishing at once.
        with self.lock:
            self.estop_pub.publish(Bool(data=True))
            self.estop_left = ESTOP_REPEATS - 1
        self.get_logger().warning('e-stop pressed on the HUD: /estop true')
        self.cancel()       # 'no route is being followed' is fine: nothing to stop
        if self.estop_pub.get_subscription_count() == 0:
            # Still published, and repeated: a subscriber may join. But none heard it.
            self.get_logger().error('nothing subscribes to /estop: the e-stop reached nobody')
            return 'nothing on the car subscribes to /estop (no backend, no twist_mux)'
        return None

    def repeat_estop(self):
        with self.lock:
            if self.estop_left > 0:
                self.estop_left -= 1
                self.estop_pub.publish(Bool(data=True))

    # --- app -> Nav2 (called from the web server's threads) ---

    def follow(self, waypoints):
        """Send the route to Nav2. None when sent, or why it wasn't."""
        if not self.nav.server_is_ready():
            with self.lock:
                self.trip_id += 1       # any answer to an older goal is now stale
                self.trip = Trip(waypoints, status=NO_NAV2)
                self.goal = None
                self._send_nav_state()
            return 'Nav2 is not running: nobody serves /follow_gps_waypoints'
        goal = FollowGPSWaypoints.Goal()
        goal.gps_poses = [geo_pose(w) for w in waypoints]
        with self.lock:
            # A newer goal replaces the old one: Nav2 aborts the old one itself.
            self.trip_id += 1
            trip_id = self.trip_id
            self.trip = Trip(waypoints)
            self.goal = None
            self._send_nav_state()      # before sending: Nav2 may answer at once
        sent = self.nav.send_goal_async(goal, feedback_callback=partial(self.on_feedback, trip_id))
        sent.add_done_callback(partial(self.on_answer, trip_id))
        self.get_logger().info(f'route sent to Nav2: {len(waypoints)} GPS waypoints')
        return None

    def cancel(self):
        """Stop following the route. None when asked, or why not."""
        with self.lock:
            if not self.trip.cancel():
                return 'no route is being followed'
            goal = self.goal
            self._send_nav_state()
        if goal is not None:
            goal.cancel_goal_async()
        self.get_logger().info('route canceled from the HUD')
        return None

    # --- Nav2's answers (executor thread) ---

    def on_answer(self, trip_id, future):
        goal = future.result()
        with self.lock:
            if trip_id != self.trip_id:
                return
            keep = self.trip.answered(goal.accepted)
            if goal.accepted:
                self.goal = goal
            self._send_nav_state()
        if not goal.accepted:
            self.get_logger().warning('Nav2 rejected the route')
            return
        if not keep:
            goal.cancel_goal_async()    # canceled while it was on its way
        goal.get_result_async().add_done_callback(partial(self.on_result, trip_id))

    def on_feedback(self, trip_id, msg):
        with self.lock:
            if trip_id != self.trip_id:
                return
            changed = self.trip.feedback(msg.feedback.current_waypoint)
            # Nav2 sends feedback at 20 Hz, mostly the same.
            if changed or self.throttle.ready('nav', time.monotonic()):
                self._send_nav_state()

    def on_result(self, trip_id, future):
        response = future.result()
        result = response.result
        with self.lock:
            if trip_id != self.trip_id:
                return
            self.trip.finished(response.status, len(result.missed_waypoints), result.error_msg)
            self.goal = None
            self._send_nav_state()
            status, message = self.trip.status, self.trip.message
        self.get_logger().info(f'route finished: {status} {message}'.rstrip())


def main(args=None):
    rclpy.init(args=args)
    node = HudServer()
    # The executor first: if the web server fails at once, its shutdown then ends spin().
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    node.start_web()
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # Ctrl-C reaches a launched node twice (terminal and launch), and Jazzy can then
        # raise RCLError ("context is not valid"). Only a live context means a real error.
        if rclpy.ok():
            raise
    finally:
        # Ctrl-C reaches a launched node twice (the terminal, then launch): ignore the
        # second, so it can't interrupt the clean-up with a traceback.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        rclpy.try_shutdown()
    return 1 if node.web_failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
