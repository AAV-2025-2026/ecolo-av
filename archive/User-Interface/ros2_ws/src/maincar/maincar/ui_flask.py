#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from flask import Flask
from threading import Thread

from std_msgs.msg import Float32

# creates flask app
flask_app = Flask(__name__)

# variables
speed = 0

# home page test
@flask_app.route('/')
def home():
    return "Flask from ros2! Speed is: "+str(speed)

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
        self.subscriber_speed = self.create_subscription(Float32, "/mock_speed", self.callback_function_speed_fetch, 10)

        self.get_logger().info("Flask node is now hosting a Flask server using thread")

    # callback functions
    def callback_function_speed_fetch(self, msg:Float32):
        # "global" means to use global variable "speed"
        global speed
        
        speed = round(float(msg.data), 2)
        self.get_logger().info(str(msg))  # prints received msg
        # can do whatever you want with the message


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
