#!/usr/bin/env python3
"""
This node constantly sends mock data to the UI front end (flutter) for testing purposes:

it sends:
    mock "Float32" speed
    mock "NavSatFix" GPS data
    mock "Bool" stop sign detection (0-no sign,  1-sign)


 value every second as mock data.
It is for the UI (Flask server) to fetch and display for testing purposes.
Pretend the mocked data is car speed.
"""

import rclpy
from rclpy.node import Node
import random

from std_msgs.msg import Float32, Bool
from sensor_msgs.msg import NavSatFix

# from geometry_msgs.msg import Twist


class MockNode(Node):
    
    def __init__(self):
        super().__init__("mock_sensors_node")
        self.coord_set = 0

        # we want this node to publish to topics reserved for mock data
        # self.create_publisher(type_of_msg, topic_name, queue_size)
        
        # creates publisher
        self.cmd_vel_pub_ = self.create_publisher(Float32,          # msg type
                                                  "/mock_speed",    # topic name
                                                  10)               # QoS profile
        
        self.cmd_gps_pub_ = self.create_publisher(NavSatFix,        # msg type
                                            "/mock_gps",            # topic name
                                            10)                     # QoS profile
        
        self.pub_mock_sign_detection_bool = self.create_publisher(Bool,
                                                             "/mock_stop_sign_detected",
                                                             10)
        

        # set call function every x seconds
        self.timer_vel = self.create_timer(0.5,                                   # Period (in seconds)  every 0.5 seconds (2 Hz)  
                                        self.send_mock_data)     # callback-function to call
        

        self.get_logger().info("This node now sends a mock speed (Float32) to topic /mock_speed, and mock gps data to topic /mock_gps")


    def send_mock_data(self):

        # === Mock Data for Speed ===
          # creates mock velocity between 4.0 and 6.0
        msg = Float32()

        
        msg.data = random.uniform(4.0, 6.0)
        self.get_logger().info("Sending Mock Speed...")
        self.cmd_vel_pub_.publish(msg)  # publishes speed message

        # === Mock Data for GPS  ===

        # canada parliament: 45.42410246146506, -75.69894697494593   (0.00001 decimal places for degrees for 1.11 m)
        # carleton university parking: 45.38382089559656, -75.69658483653251
        msgGPS = NavSatFix()

        if (self.coord_set <= 2):

            msgGPS.latitude = 45.42410
            msgGPS.longitude = -75.69895
            msgGPS.altitude = 1.0

        elif (self.coord_set <= 5):

            msgGPS.latitude = 45.38382
            msgGPS.longitude = -75.69658
            msgGPS.altitude = 2.0

        #latitude = msg.latidude

        self.cmd_gps_pub_.publish(msgGPS) # publishes to /mock_gps
        self.coord_set += 1
        if (self.coord_set > 5): self.coord_set = 0
        self.get_logger().info("Sending Mock GPS... (coord set: +"+str(self.coord_set)+")")


        # === Mock Data for Sign Detection ===
        msgBool = Bool() 
        randomVal = random.uniform(0.0, 2.0)
        if (randomVal >= 1.0):
            msgBool.data = True
        else:
            msgBool.data = False

        self.pub_mock_sign_detection_bool.publish(msgBool)




def main(args=None):
    rclpy.init(args=args)

    node = MockNode()
    rclpy.spin(node) # keeps node alive until CTRL+C command is used

    rclpy.shutdown()