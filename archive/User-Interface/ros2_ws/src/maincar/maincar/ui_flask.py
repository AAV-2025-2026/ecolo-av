#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from flask import Flask, request, jsonify
from threading import Thread
from flask_socketio import SocketIO

from std_msgs.msg import Float32, Bool, UInt8, String
from sensor_msgs.msg import NavSatFix, Image
from geometry_msgs.msg import Point

# =========================
# MediaMTX config (LAN)
# =========================
MEDIAMTX_IP = "192.168.1.101"       # MediaMTX host (your streaming Pi)
MEDIAMTX_WEBRTC_PORT = 8889         # MediaMTX WebRTC HTTP port
MEDIAMTX_RTSP_PORT = 8554           # MediaMTX RTSP port (default)
STREAM_PATH = "cam1"                # stream path (cam1)

def build_stream_info():
    return {
        "name": STREAM_PATH,
        "base_url": f"http://{MEDIAMTX_IP}:{MEDIAMTX_WEBRTC_PORT}/{STREAM_PATH}/",
        "whep_url": f"http://{MEDIAMTX_IP}:{MEDIAMTX_WEBRTC_PORT}/{STREAM_PATH}/whep",
        "rtsp_url": f"rtsp://{MEDIAMTX_IP}:{MEDIAMTX_RTSP_PORT}/{STREAM_PATH}",
    }

# =========================
# Flask + Socket.IO setup
# =========================
flask_app = Flask(__name__)
socketio = SocketIO(flask_app, cors_allowed_origins="*", async_mode="threading")

# =========================
# Shared one-way variables (ROS2 -> Flask -> Flutter)
# =========================

usingMockData = False   # if true, display mock data... If false, display real car data TODO: to implement it.

mock_speed = 0.0

mock_gps_x = 0.0
mock_gps_y = 0.0
mock_gps_z = 0.0

mock_gear = 0   

mock_stop_sign_detection = False

# real values (from actual car, not mock)
real_speed = 0

real_gps_x = 0
real_gps_y = 0
real_gps_z = 0

real_gear = 0   

real_stop_sign_detection = False




# =========================
# Shared one-way variables (Flutter -> Flask -> ROS2)
# =========================
tuple_destinationCoordinateLatLon = (0.0, 0.0) # default is 0.0, 0.0 until updated
tuple_startingCoordinateLatLon = (0.0, 0.0) # default is 0.0, 0.0 until updated
list_lastestRoute = ""
list_latestRoutePoints = []    # like list_latestRoute, except it's a list that contains Point() types only, but I think I'll make this a list of tuples, x,y with no z, more memory efficient.


# =========================
# HTTP routes
# =========================
@flask_app.route("/")
def home():
    return "Flask from ROS2! Speed is: " + str(mock_speed)

@flask_app.route("/gps")
def gps_page():
    return "Flask from ROS2! GPS altitude is: " + str(mock_gps_altitude)

@flask_app.route("/stream-info")
def stream_info():
    """
    UI can call this to discover the MediaMTX URLs.
    """
    return jsonify(build_stream_info())
    
@flask_app.route('/receive', methods=['POST'])
def receive_data():
    # parses incoming HTTP request (the JSON) into a Python object:
    global list_latestRoute
    data = request.json   					
    print("Received from Flutter:", data)
    list_lastestRoute = data
    getDestination(data)
    # print("Type: "+ str(type(data)) )
    return jsonify({"status": "success", "received": data})

# =========================
# Socket.IO events
# =========================
@socketio.on("connect")
def on_connect():
    # Send stream info to the UI as soon as it connects
    socketio.emit("stream_info", build_stream_info())
    print("✅ Socket.IO client connected; sent stream_info")

@socketio.on("disconnect")
def on_disconnect():
    print("⚠️ Socket.IO client disconnected")


# =========================
# Flask runner (threaded with ROS2)
# =========================
def run_flask():
    socketio.run(
        flask_app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
    )


# =========================
# ROS2 Node
# =========================
class FlaskNode(Node):
    def __init__(self):
        super().__init__("flask_ros2_node")

        # Start Flask server in a separate thread
        self.flask_thread = Thread(target=run_flask, daemon=True)
        self.flask_thread.start()

        # ROS2 subscribers
        self.subscriber_mock_speed = self.create_subscription(
            Float32, "/mock_speed", self.callback_function_mock_speed_fetch, 10
        )

        self.subscriber_mock_gps = self.create_subscription(
            NavSatFix, "/mock_gps", self.callback_function_mock_gps_fetch, 10
        )

        self.subscriber_real_stop_sign_detector = self.create_subscription(
            Bool, "/aav/stop_sign_detected", self.callback_real_stop_sign, 10
        )

        self.subscriber_mock_stop_sign_detector = self.create_subscription(
            Bool, "/mock_stop_sign_detected", self.callback_mock_stop_sign, 10
        )

        """
        self.subscriber_cam1 = self.create_subscription(
            Image, "/camera/cam1/image_raw", self.callback_cam1, 10
        )

        self.subscriber_cam2 = self.create_subscription(
            Image, "/camera/cam2/image_raw", self.callback_cam2, 10
        )
        """

        self.subscriber_gear = self.create_subscription(
            UInt8, "/rtos/gear", self.callback_sub_gear, 10
        )

        self.subscriber_speed = self.create_subscription(
            Float32, "/rtos/speed", self.callback_sub_speed, 10
        )

        self.subscriber_gps = self.create_subscription(
            NavSatFix, "/rtos/gps", self.callback_sub_gps, 10
        )

        # ROS2 publishers
        self.publisher_destinationCoord = self.create_publisher(Point, '/ui/destination_point', 10)
        self.publisher_osrmRoute = self.create_publisher(String, "/ui/route", 10)

        # timers
        # subscription to topics are "event-driven"--subscribes when a msg is available. It's automatic.
        # publishing to topics are "timer-driven". We have to create timers to execute a timer callback function that publish msgs

        self.timer1 = self.create_timer(0.5, self.timer1_callback) # timer1 will execute timer1_callback() every 0.5 seconds (2 Hz)
        
        self.get_logger().info("✅ Flask node hosting Flask-SocketIO server in a thread")


    # ----- callback functions for subscribers -------

    def callback_function_mock_speed_fetch(self, msg: Float32):
        global mock_speed

        mock_speed = round(float(msg.data), 2)
        self.get_logger().info("mock speed: " + str(mock_speed))

        # IMPORTANT: Flutter expects data['mock_speed']
        socketio.emit("mock_speed_update", {"mock_speed": mock_speed})


    def callback_function_mock_gps_fetch(self, msg: NavSatFix):
        global mock_gps_x
        global mock_gps_y
        global mock_gps_z

        
        mock_gps_x = float(msg.latitude)
        mock_gps_y = float(msg.longitude)
        mock_gps_z = float(msg.altitude)

        self.get_logger().info(
            f"Mock Latitude: {mock_gps_x}, Mock Longitude: {mock_gps_y}, Mock Altitude: {mock_gps_z}"
        )

        socketio.emit("mock_gps_update", {"mock_latitude": mock_gps_x, "mock_longitude": mock_gps_y})
    
    def callback_mock_stop_sign(self, msg: Bool):
        if (msg.data == True):
            self.get_logger().info(f"mock stopsign detected!")
        socketio.emit("mock_stop_sign_alert", {"mock_sign_detected": bool(msg.data), "message": "mock STOP"})
    
    def callback_real_stop_sign(self, msg: Bool):
        if (msg.data == True):
            self.get_logger().info(f"stopsign detected!")
        socketio.emit("real_stop_sign_alert", {"real_sign_detected": bool(msg.data), "message": "STOP"})

    """
    def callback_cam1(self, msg: Image):
        self.get_logger().info(f"Cam1 image received: {msg.width}x{msg.height}, encoding: {msg.encoding}")

    def callback_cam2(self, msg: Image):
        self.get_logger().info(f"Cam2 image received: {msg.width}x{msg.height}, encoding: {msg.encoding}")
    """

    def callback_sub_gear(self, msg: UInt8):
        global real_gear
        real_gear = -1  #  if -1 then data is invalid

        if (msg.data == 0):    # 0 means "drive".
            real_gear = 0
        elif (msg.data == 1):    # 1 means "parked" 
            real_gear = 1
        elif (msg.data == 2):    # 2 means "reversed"
            real_gear = 2
        else:
            self.get_logger().warn(f"Non-valid gear value: Gear value is currently {msg.data}")

        # Flutter expects data['real_gear']
        socketio.emit("real_gear_update", {"real_gear": real_gear})


    def callback_sub_speed(self, msg: Float32):
        global real_speed

        real_speed = msg.data
        self.get_logger().info("real speed: " + str(real_speed))

        # IMPORTANT: Flutter expects data['real_speed']
        socketio.emit("real_speed_update", {"real_speed": real_speed})



    def callback_sub_gps(self, msg: NavSatFix):
        global real_gps_x
        global real_gps_y
        global real_gps_z

        
        real_gps_x = float(msg.latitude)
        real_gps_y = float(msg.longitude)
        real_gps_z = float(msg.altitude)

        self.get_logger().info(
            f"Mock Latitude: {real_gps_x}, Mock Longitude: {real_gps_y}, Mock Altitude: {real_gps_z}"
        )

        socketio.emit("real_gps_update", {"real_latitude": real_gps_x, "real_longitude": real_gps_y})



    # ----  timer functions for publishers -----
    def timer1_callback(self):

        #          ----  destination_point ----
        # publishes destination coordinate as a geometry_msg Point
        global tuple_destinationCoordinateLatLon
        
        # Create Point message
        point_msg = Point()
        point_msg.x = tuple_destinationCoordinateLatLon[0] # latitude
        point_msg.y = tuple_destinationCoordinateLatLon[1] # longitude
        point_msg.z = 0.0
        
        print("debug: publishing DestinationCoordinate (" + str(point_msg.x)+", "+str(point_msg.y)+")")
        # Publish
        self.publisher_destinationCoord.publish(point_msg) # publishes "point_msg"


        #              ---- user input osrm route -----


        


# =========================
# Helper Functions
# =========================
def getDestination(route: list):
    """
    Takes a route (list of {'lat': ..., 'lon': ...})
    and and takes last element and returns it as as a tuple (lat, lon)
    """
    global tuple_destinationCoordinateLatLon
    if not route:  # empty list safety check
        print("Route list is empty. getDestination() returns None.")
        return None

    last = route[-1]  # get last element of route

    
    point = (last["lat"], last["lon"])
    print("Destination coordinate as a tuple (Latitude, Longitude):")
    tuple_destinationCoordinateLatLon = point
    print(point)
    return point

#TODO: implement def getRouteArrayFromRouteList() to be sent to Nav

#Main
def main(args=None):
    rclpy.init(args=args)
    node = FlaskNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("Shutting down Flask ROS2 node")
        rclpy.shutdown()


if __name__ == "__main__":
    main()
