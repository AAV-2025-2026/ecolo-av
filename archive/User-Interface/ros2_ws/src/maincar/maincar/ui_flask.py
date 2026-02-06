#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from flask import Flask, jsonify
from threading import Thread
from flask_socketio import SocketIO

from std_msgs.msg import Float32
from sensor_msgs.msg import NavSatFix

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
# Shared variables (ROS2 -> Flask routes)
# =========================
mock_speed = 0.0
mock_gps_altitude = 0.0


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

        self.get_logger().info("✅ Flask node hosting Flask-SocketIO server in a thread")

    def callback_function_mock_speed_fetch(self, msg: Float32):
        global mock_speed

        mock_speed = round(float(msg.data), 2)
        self.get_logger().info("mock speed: " + str(mock_speed))

        # IMPORTANT: your Flutter expects data['speed']
        socketio.emit("mock_speed_update", {"speed": mock_speed})

    def callback_function_mock_gps_fetch(self, msg: NavSatFix):
        global mock_gps_altitude

        mock_gps_altitude = float(msg.altitude)
        latitude = float(msg.latitude)
        longitude = float(msg.longitude)

        self.get_logger().info(
            f"Mock Latitude: {latitude}, Mock Longitude: {longitude}, Mock Altitude: {mock_gps_altitude}"
        )

        socketio.emit("mock_gps_update", {"latitude": latitude, "longitude": longitude})


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
