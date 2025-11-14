#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from flask import Flask
from threading import Thread
from flask_socketio import SocketIO

from std_msgs.msg import Float32
from sensor_msgs.msg import NavSatFix

# creates flask app
flask_app = Flask(__name__)

#SocketIO setup
socketio = SocketIO(flask_app, cors_allowed_origins="*")

# variables
mock_speed = 0

mock_gps_altitude = 0

# home page test
@flask_app.route('/')
def home():
    return "Flask from ros2! Speed is: "+str(mock_speed)

# gps page test
@flask_app.route('/gps')
def gps_page():
    return "Flask from ros2! GPS coords are: "+str(mock_gps_altitude)


def run_flask():
    # run Flask server. 0.0.0.0 means listen to all machines on same "network"
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


class FlaskNode(Node):
    def __init__(self):
        super().__init__("flask_ros2_node")
        # starts flask in seperate thread
        self.flask_thread = Thread(target=run_flask)
        self.flask_thread.start()

        # makes the flask node a subscriber to speed topic
        self.subscriber_mock_speed = self.create_subscription(Float32, "/mock_speed", self.callback_function_mock_speed_fetch, 10)
        self.subscriber_mock_gps = self.create_subscription(NavSatFix, "/mock_gps", self.callback_function_mock_gps_fetch, 10)

        self.get_logger().info("Flask node is now hosting a Flask server using ros2 by threading")


    # callback functions
    def callback_function_mock_speed_fetch(self, msg:Float32):
        # "global" means to use global variable "speed"
        global mock_speed
        
        mock_speed = round(float(msg.data), 2)
        self.get_logger().info("mock speed: "+str(msg))  # prints received msg
        # can do whatever you want with the message

        socketio.emit("mock_speed_update", {"mock_speed": mock_speed})


    def callback_function_mock_gps_fetch(self, msg:NavSatFix):

        global mock_gps_altitude

        mock_gps_altitude = msg.altitude

        latitude = msg.latitude
        longitude = msg.longitude
        altitude = msg.altitude

        self.get_logger().info("Mock Latitude: "+str(latitude)+", Mock Longitude: "+str(longitude)+", Mock Altitude: "+str(altitude))  # prints received msg
        # can do whatever you want with the message

        socketio.emit("mock_gps_update", {"latitude": latitude, "longitude": longitude})


def main(args=None):
    rclpy.init(args=args)
    node = FlaskNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("Shutting down Flask ros2 node")
        rclpy.shutdown



if __name__ == "__main__":
    main()
