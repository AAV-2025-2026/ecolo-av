#!/usr/bin/env python3
"""
This node constantly sends a Float32 value every second as mock data.
It is for the UI (Flask server) to fetch and display for testing purposes.
Pretend the mocked data is car speed.
"""

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
# from geometry_msgs.msg import Twist


class MyNode(Node):
    
    def __init__(self):
        super().__init__("mock_car_speed_node")
        
        # we want this node to publish to topic called /mock_speed
        # self.create_publisher(type_of_msg, topic_name, queue_size)
        
        # creates publisher
        self.cmd_vel_pub_ = self.create_publisher(Float32,          # msg type
                                                  "/mock_speed",    # topic name
                                                  10)               # QoS profile
        

        self.get_logger().info("This node now sends a mock Float32 value each second at topic /mock_speed")

        # set call function every x seconds
        self.timer_ = self.create_timer(1,                                   # amount of seconds to wait 
                                        self.send_mock_velocity_command)     # callback-function to call



    def send_mock_velocity_command(self):

        msg = Float32()
        msg.data = 5.0  # mock 5.0 velocity in m/s
        self.get_logger().info("Sending Mock...")


        self.cmd_vel_pub_.publish(msg)  # publishes message


def main(args=None):
    rclpy.init(args=args)

    node = MyNode()
    rclpy.spin(node) # keeps node alive until CTRL+C command is used

    rclpy.shutdown()